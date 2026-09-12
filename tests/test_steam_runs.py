import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from steam_sources import SourceResult, reconcile, AccountMismatchError
from steam_runs import publish_run, load_library, manifest_path, resolve_artifact, check_previous

ACCOUNT = "76561198000000001"


def bundle(run, ids=(10, 20), candidate=False):
    source = SourceResult("web_api" if candidate else "client_library",
                          [{"appid": i, "name": "Game", "app_type": "game"} for i in ids],
                          steam_id=ACCOUNT, completeness={"verified": True})
    rows, audit = reconcile([source], ACCOUNT)
    audit.update(run_id=run, producer={"git_commit": "test", "dirty": False})
    for r in rows:
        r.update(run_id=run, playtime_minutes=None, playtime_available=False)
    return rows, audit


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)/"library.json"

    def publish(self, run, **kwargs):
        rows, audit = bundle(run, **kwargs)
        publish_run(self.output, rows, audit)
        return rows, audit

    def test_failed_render_or_manifest_commit_preserves_entire_previous_generation(self):
        self.publish("first")
        pointer = manifest_path(self.output).read_bytes()
        with patch("classify_games.write_csv", side_effect=OSError("disk full")), self.assertRaises(OSError):
            self.publish("render_failed", ids=(30,))
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)
        from steam_runs import atomic_json
        def fail_pointer(path, data):
            if Path(path) == manifest_path(self.output):
                raise OSError("locked")
            atomic_json(path, data)
        with patch("steam_runs.atomic_json", side_effect=fail_pointer), self.assertRaises(OSError):
            self.publish("pointer_failed", ids=(40,))
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)
        self.assertEqual([g["appid"] for g in load_library(self.output)], [10, 20])

    def test_manifest_controls_reading_even_when_flat_export_is_stale(self):
        self.publish("first")
        self.output.write_text("stale", encoding="utf-8")
        self.assertEqual(len(load_library(self.output)), 2)
        path = resolve_artifact(self.output, "summary.json")
        path.write_text("corrupt", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_library(self.output)

    def test_truncated_csv_is_not_published(self):
        self.publish("first")
        pointer = manifest_path(self.output).read_bytes()
        def truncate(rows, path):
            path.write_text("appid,run_id\n", encoding="utf-8")
        with patch("classify_games.write_csv", side_effect=truncate), self.assertRaises(RuntimeError):
            self.publish("broken_csv")
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)

    def test_candidates_do_not_replace_current_output_or_pointer(self):
        self.publish("first")
        pointer = manifest_path(self.output).read_bytes()
        self.publish("candidate", ids=(30, 40, 50), candidate=True)
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)
        candidates = load_library(self.output.with_suffix(".candidates.json"))
        self.assertEqual(len(candidates), 3)
        self.assertTrue(all(r["membership"]["state"] == "candidate" for r in candidates))

    def test_large_removal_and_account_change_block_current_generation(self):
        self.publish("first", ids=tuple(range(1, 389)))
        rows, audit = bundle("partial", ids=tuple(range(1, 101)))
        pointer = manifest_path(self.output).read_bytes()
        check_previous(self.output, rows, audit)
        self.assertEqual(audit["status"], "suspicious_change")
        self.assertEqual(len(audit["previous_run"]["removed"]), 288)
        self.assertEqual(manifest_path(self.output).read_bytes(), pointer)
        audit["steam_id"] = "76561198000000002"
        with self.assertRaises(AccountMismatchError):
            check_previous(self.output, rows, audit)

    def test_partial_client_never_excludes_successful_candidates(self):
        rows, audit = reconcile([SourceResult("client_library", [{"appid": 10}], state="partial"),
                                 SourceResult("web_api", [{"appid": 20}])])
        self.assertEqual([r["appid"] for r in rows], [20])
        self.assertEqual(audit["membership"], "candidate_union")

    def test_unknown_enum_and_playtime_conflict_keep_evidence(self):
        rows, audit = reconcile([
            SourceResult("client_library", [{"appid": 1, "app_type": 131072}], completeness={"verified": True}),
            SourceResult("web_api", [{"appid": 1, "playtime_forever": 120}]),
            SourceResult("client_last_played_times", [{"appid": 1, "playtime_forever": 118}])])
        r = rows[0]
        self.assertEqual(r["app_type"], "unknown")
        self.assertEqual(r["raw_app_types"]["client_library"], 131072)
        self.assertEqual(r["playtime_forever"], 120)
        evidence = r["playtime_evidence"]["playtime_forever"]
        self.assertTrue(evidence["conflict"])
        self.assertEqual(evidence["evidence"]["client_last_played_times"]["value"], 118)

    def test_account_mismatch_cannot_hide_in_failed_source(self):
        with self.assertRaises(AccountMismatchError):
            reconcile([SourceResult("web_api", [{"appid": 1}], steam_id=ACCOUNT),
                       SourceResult("client_library", state="unavailable", steam_id="76561198000000002")])

    def test_precise_type_selection_shared_by_both_entrypoints(self):
        from steam_classification import load_selected
        from types import SimpleNamespace
        rows, audit = bundle("types")
        rows[1]["app_type"] = "demo"
        publish_run(self.output, rows, audit)
        args = SimpleNamespace(input=self.output, allow_candidates=False, include_type="demo")
        self.assertEqual([r["appid"] for r in load_selected(args)[1]], [20])
        args.include_type = "all"
        self.assertEqual(len(load_selected(args)[1]), 2)

    def test_candidate_classification_requires_explicit_optin(self):
        from steam_classification import load_selected
        from types import SimpleNamespace
        self.publish("candidate", candidate=True)
        args = SimpleNamespace(input=self.output.with_suffix(".candidates.json"), allow_candidates=False, include_type="all")
        with self.assertRaisesRegex(ValueError, "CANDIDATE_LIBRARY"):
            load_selected(args)
        args.allow_candidates = True
        self.assertEqual(len(load_selected(args)[1]), 2)


if __name__ == "__main__":
    unittest.main()
