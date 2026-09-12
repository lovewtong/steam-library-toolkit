import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import steam_collect


ROOT = Path(__file__).resolve().parents[1]


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "apps.txt"

    def write_apps(self, text="10 API Game\n20 未游玩免费游戏\n30 下架游戏\n", encoding="utf-8"):
        self.path.write_text(text, encoding=encoding)
        return self.path

    @patch("steam_collect.requests.get")
    def test_api_filters_are_explicit_on_wire(self, get):
        get.return_value = Mock(status_code=200)
        get.return_value.json.return_value = {"response": {"games": [{"appid": 10}]}}
        for expanded in (True, False):
            with self.subTest(expanded=expanded):
                self.assertEqual(steam_collect.get_owned_games("test-key", "test-id", expanded), [{"appid": 10}])
                params = get.call_args.kwargs["params"]
                self.assertEqual(params["include_played_free_games"], "true" if expanded else "false")
                self.assertEqual(params["include_free_sub"], "true" if expanded else "false")
                self.assertEqual(params["skip_unvetted_apps"], "false" if expanded else "true")
        steam_collect.get_owned_games("unused-key", "test-id", access_token="private-access")
        params = get.call_args.kwargs["params"]
        self.assertNotIn("key", params)
        self.assertEqual(params["access_token"], "private-access")
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    @patch("steam_collect.requests.get")
    def test_invalid_api_response_is_not_silently_an_empty_library(self, get):
        get.return_value = Mock(status_code=200)
        for data in ({}, [], {"response": {}}, {"response": {"games": {}}},
                     {"response": {"games": [None]}}, {"response": {"game_count": 3, "games": []}}):
            with self.subTest(data=data):
                get.return_value.json.return_value = data
                with self.assertRaises(ValueError):
                    steam_collect.get_owned_games("test-key", "test-id")
        get.return_value.json.return_value = {"response": {"game_count": 0}}
        self.assertEqual(steam_collect.get_owned_games("test-key", "test-id"), [])

    def test_windows_encodings_and_duplicate_ids(self):
        for encoding in ("utf-8", "utf-8-sig", "utf-16"):
            with self.subTest(encoding=encoding):
                self.write_apps("\n10 名称 含空格\n10 duplicate\n20\tAnother Game\n", encoding)
                self.assertEqual(steam_collect.load_apps_file(self.path), [
                    {"appid": 10, "name": "名称 含空格"}, {"appid": 20, "name": "Another Game"},
                ])

    def test_bad_or_empty_export_fails(self):
        for text in ("", "   \n", "Login failed", "10", "0 Invalid", "4294967296 Invalid", "10 Fine\nWARNING"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    steam_collect.load_apps_file(self.write_apps(text))

    @patch("steam_collect.get_owned_games")
    @patch("steam_collect.load_config", return_value={"api_key": "test-key", "steam_id": "test-id"})
    def test_merge_preserves_playtime_and_adds_unplayed_and_delisted_apps(self, config, api):
        api.return_value = [
            {"appid": 10, "name": "API Name", "playtime_forever": 123,
             "playtime_2weeks": 7, "rtime_last_played": 1700000000},
            {"appid": 40, "name": "API only", "playtime_forever": 0},
        ]
        with contextlib.redirect_stdout(io.StringIO()):
            games = steam_collect.collect(fetch_store=False, apps_file=self.write_apps(), allow_candidate_membership=True)
        by_id = {game["appid"]: game for game in games}
        self.assertEqual(set(by_id), {10, 20, 30, 40})
        self.assertEqual(by_id[10]["name"], "API Name")
        self.assertEqual(by_id[10]["playtime_minutes"], 123)
        self.assertEqual(by_id[10]["playtime_2weeks_minutes"], 7)
        self.assertEqual(by_id[10]["last_played_iso"], "2023-11-14T22:13:20Z")
        self.assertEqual(set(by_id[10]["sources"]), {"web_api", "license_file"})
        self.assertTrue(by_id[40]["playtime_available"])
        self.assertFalse(by_id[20]["playtime_available"])
        self.assertIsNone(by_id[30]["last_played_at"])
        self.assertNotIn("sources", api.return_value[0])

    @patch("steam_collect.get_owned_games", side_effect=ValueError("private"))
    @patch("steam_collect.load_config", return_value={"api_key": "test-key", "steam_id": "test-id"})
    def test_private_api_still_uses_export(self, config, api):
        with contextlib.redirect_stdout(io.StringIO()):
            games = steam_collect.collect(fetch_store=False, apps_file=self.write_apps())
        self.assertEqual(len(games), 3)

    @patch("steam_collect.time.sleep")
    @patch("steam_collect.get_store_result", return_value={"status": "not_found", "details": None})
    @patch("steam_collect.load_config", side_effect=AssertionError("must not read credentials"))
    def test_no_api_and_unavailable_store_keep_license_entries(self, config, store, sleep):
        with contextlib.redirect_stdout(io.StringIO()):
            games = steam_collect.collect(apps_file=self.write_apps(), use_api=False, cache_dir=Path(self.temp.name)/"cache")
        self.assertEqual([g["appid"] for g in games], [10, 20, 30])
        self.assertTrue(all(g["genres"] == [] for g in games))

    def run_cli(self, script, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / script), *map(str, args)],
            cwd=self.temp.name, capture_output=True, encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=20,
        )

    def test_collection_and_classification_entrypoints_end_to_end(self):
        library = Path(self.temp.name) / "library.json"
        csv = Path(self.temp.name) / "classified.csv"
        md = Path(self.temp.name) / "classified.md"
        result = self.run_cli("steam_collect.py", "--apps-file", self.write_apps(), "--no-api", "--no-store", "--allow-candidates", "-o", library)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(library.read_text(encoding="utf-8"))), 3)
        result = self.run_cli("classify_games.py", "-i", library, "--csv", csv, "--md", md, "--include-unknown", "--allow-candidates")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("下架游戏", csv.read_text(encoding="utf-8-sig"))
        self.assertIn("未游玩免费游戏", md.read_text(encoding="utf-8"))
        self.assertIn("未知", md.read_text(encoding="utf-8"))

    def test_invalid_options_and_export_do_not_overwrite_output(self):
        output = Path(self.temp.name) / "library.json"
        output.write_text("existing", encoding="utf-8")
        for args in (("--no-api", "--no-client"), ("--owned-only", "--apps-file", self.write_apps()),
                     ("--apps-file", self.write_apps("Invalid export"), "--no-api")):
            with self.subTest(args=args):
                result = self.run_cli("steam_collect.py", *args, "-o", output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
