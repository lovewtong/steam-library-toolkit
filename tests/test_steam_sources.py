import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import classify_games
import steam_collect
from steam_sources import AccountMismatchError, SourceResult, atomic_json, read_snapshot, reconcile, select_for_classification

ACCOUNT = "76561198000000001"
OTHER = "76561198000000002"


def source(name, records=(), **kwargs):
    return SourceResult(name, list(records), steam_id=ACCOUNT, **kwargs)


class ReconciliationTests(unittest.TestCase):
    def test_live_membership_does_not_resurrect_removed_apps(self):
        rows, audit = reconcile([
            source("web_api", [{"appid": 10, "playtime_forever": 120}, {"appid": 20}]),
            source("client_library", [{"appid": 10, "app_type": "game"}, {"appid": 30, "app_type": "demo"}]),
            source("licenses", [{"appid": 10, "shared_only": False}, {"appid": 40, "app_type": "dlc"}]),
            source("license_file", [{"appid": 50, "name": "Refunded game"}], scope="snapshot"),
        ])
        self.assertEqual([r["appid"] for r in rows], [10, 30])
        self.assertEqual(rows[0]["playtime_forever"], 120)
        self.assertEqual(rows[0]["ownership"], "account_license")
        self.assertEqual(audit["difference"]["snapshot_not_client"], [50])
        self.assertEqual(audit["difference"]["api_not_client"], [20])
        self.assertEqual(audit["difference"]["license_not_client"], [40])
        self.assertEqual(audit["status"], "ok")

    def test_unknown_time_is_not_zero_and_snapshot_time_is_not_fresh(self):
        rows, _ = reconcile([
            source("client_library", [{"appid": 10}, {"appid": 20, "playtime_forever": 0},
                                      {"appid": 30, "playtime_forever": 5}]),
            source("license_file", [{"appid": 10, "playtime_forever": 80}]),
        ])
        self.assertEqual([r["playtime_forever"] for r in rows], [None, 0, 5])
        self.assertEqual(rows[2]["provenance"]["playtime_forever"], "client_library")

    def test_api_failure_does_not_erase_client_games(self):
        rows, audit = reconcile([source("web_api", status="failed"),
                                 source("client_library", [{"appid": 1, "app_type": "game"}])])
        self.assertEqual(len(rows), 1)
        self.assertEqual(audit["status"], "degraded")
        self.assertEqual(audit["membership"], "client_snapshot")

    def test_client_failure_uses_candidates_with_explicit_degradation(self):
        rows, audit = reconcile([source("client_library", status="failed"),
                                 source("web_api", [{"appid": 1}]),
                                 source("licenses", [{"appid": 2, "app_type": "tool"}])])
        self.assertEqual([r["appid"] for r in rows], [1, 2])
        self.assertTrue(audit["warnings"])
        self.assertEqual(audit["status"], "degraded")
        self.assertTrue(all(r["membership_status"] == "unverified_completeness" for r in rows))

    def test_confirmed_empty_client_excludes_historical_api(self):
        rows, audit = reconcile([source("client_library"), source("web_api", [{"appid": 1}])])
        self.assertEqual(rows, [])
        self.assertEqual(audit["membership"], "client_snapshot")

    def test_accounts_cannot_be_mixed(self):
        with self.assertRaises(AccountMismatchError):
            reconcile([source("client_library", [{"appid": 1}]),
                       SourceResult("license_file", [{"appid": 2}], steam_id=OTHER)])

    def test_default_classification_excludes_non_games_but_optins_work(self):
        rows = [{"appid": i, "app_type": kind} for i, kind in enumerate(
            ["game", "demo", "dlc", "tool", "application", "beta", "unknown"], 1)]
        self.assertEqual([r["appid"] for r in select_for_classification(rows)], [1])
        self.assertEqual([r["appid"] for r in select_for_classification(rows, include_demo=True)], [1, 2])
        self.assertEqual(len(select_for_classification(rows, include_non_game=True)), 6)
        self.assertEqual(len(select_for_classification(rows, include_non_game=True, include_unknown=True)), 7)
        self.assertEqual(len(rows), 7)


class FileAndCollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def snapshot(self, **changes):
        data = {"schema_version": 2, "steam_id": ACCOUNT, "generated_at": "2026-09-11T00:00:00Z",
                "apps": [{"appid": 10, "name": "Game", "app_type": "game"}]}
        data.update(changes)
        p = self.path / "snapshot.json"
        atomic_json(p, data)
        return p

    def test_snapshot_checks_identity_schema_and_time(self):
        p = self.snapshot()
        self.assertEqual(read_snapshot(p, ACCOUNT).records[0]["app_type"], "game")
        with self.assertRaises(AccountMismatchError):
            read_snapshot(p, OTHER)
        for change in ({"generated_at": "2026-09-11"}, {"schema_version": 1},
                       {"steam_id": ""}, {"apps": [{"appid": True}]},
                       {"apps": [{"appid": 1, "playtime_forever": -1}]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                read_snapshot(self.snapshot(**change))

    def test_failed_atomic_replace_keeps_old_file(self):
        p = self.path / "library.json"
        p.write_text("old", encoding="utf-8")
        with patch("steam_sources.os.replace", side_effect=OSError("locked")), self.assertRaises(OSError):
            atomic_json(p, [{"appid": 1}])
        self.assertEqual(p.read_text(), "old")
        self.assertEqual(list(self.path.glob("*.tmp")), [])

    @patch("steam_collect.load_config", return_value={"api_key": "", "steam_id": ACCOUNT})
    @patch("steam_collect.collect_client")
    @patch("steam_collect.client_library", return_value=[{"appid": 10, "name": "Game", "app_type": "game"}])
    @patch("steam_collect.get_owned_games", side_effect=steam_collect.requests.Timeout("secret-url"))
    def test_source_failure_isolated_and_strict_mode_preserves_files(self, api, client, helper, config):
        helper.return_value = {"steam_id": ACCOUNT, "access_token": "private-token", "licenses": [],
                               "license_status": "ok", "playtimes": [{"appid": 10, "playtime_forever": 5}],
                               "playtime_status": "ok"}
        audit = {}
        rows = steam_collect.collect(fetch_store=False, use_client=True, audit=audit)
        self.assertEqual(rows[0]["playtime_minutes"], 5)
        self.assertEqual(audit["status"], "degraded")
        self.assertNotIn("secret", json.dumps(audit))
        self.assertNotIn("private-token", json.dumps(rows))
        output = self.path / "snapshot.json"
        output.write_text("old", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            steam_collect.collect(fetch_store=False, use_client=True, strict=True, snapshot_output=output)
        self.assertEqual(output.read_text(), "old")

    @patch("steam_collect.time.sleep")
    @patch("steam_collect.get_store_details")
    def test_metadata_cache_reuses_and_refreshes_without_losing_delisted_app(self, store, sleep):
        details = {"app_type": "game", "genres": [], "categories": [], "is_multiplayer": False, "is_controller": False}
        store.return_value = details
        self.assertEqual(steam_collect.cached_store_details(10, self.path), details)
        self.assertEqual(steam_collect.cached_store_details(10, self.path), details)
        self.assertEqual(store.call_count, 1)
        steam_collect.cached_store_details(10, self.path, refresh=True)
        self.assertEqual(store.call_count, 2)
        store.return_value = None
        rows = steam_collect.collect(apps_file=self.snapshot(), use_api=False, cache_dir=self.path, refresh_metadata=True)
        self.assertEqual(rows[0]["appid"], 10)
        self.assertEqual(rows[0]["genres"], [])

    @patch("steam_collect.requests.get")
    def test_client_rejects_wrong_machine_ambiguous_sessions_and_missing_confirmation(self, get):
        def reply(body):
            response = Mock(status_code=200, headers={})
            response.json.return_value = {"response": body}
            return response
        for sessions in ([], [{"machine_name": "other"}], [{"machine_name": None}],
                         [{"machine_name": "desktop"}, {"machine_name": "desktop"}]):
            get.return_value = reply({"sessions": sessions})
            with self.subTest(sessions=sessions), self.assertRaises(RuntimeError):
                steam_collect.client_library("private-access", "desktop")
        session = reply({"sessions": [{"machine_name": "desktop", "client_instanceid": "123"}]})
        get.side_effect = [session, reply({})]
        with self.assertRaises(ValueError):
            steam_collect.client_library("private-access", "desktop")
        get.side_effect = [session, reply({"client_info": {"machine_name": "desktop"},
                                          "apps": [{"appid": 10, "app": "Game", "app_type": "game"}]})]
        self.assertEqual(steam_collect.client_library("private-access", "DESKTOP")[0]["appid"], 10)

    @patch("steam_collect.requests.get")
    def test_store_bad_json_shapes_are_optional_failures(self, get):
        for data in ([], {"10": None}, {"10": {"success": True, "data": None}}):
            with self.subTest(data=data):
                get.return_value.json.return_value = data
                self.assertIsNone(steam_collect.get_store_details(10))

    def test_unknown_playtime_survives_legacy_zero_and_csv_escaping(self):
        rows = classify_games.classify_library([
            {"appid": 1, "name": 'A, "B"', "playtime_minutes": 0, "playtime_available": False},
            {"appid": 2, "name": "Zero", "playtime_minutes": 0, "playtime_available": True}])
        out = self.path / "out.csv"
        classify_games.write_csv(rows, out)
        data = list(csv.reader(io.StringIO(out.read_text(encoding="utf-8-sig"))))
        self.assertEqual(data[1][1:3], ['A, "B"', "未知"])
        self.assertEqual(data[2][2], "0h")
        self.assertNotIn("单人", rows[0]["tags"])


if __name__ == "__main__":
    unittest.main()
