"""Loopback-only picker with explicit routes and generation-consistent reads."""
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from steam_library_toolkit.classification import classify_one
from steam_runs import manifest_path, resolve_artifact, load_library
from steam_sources import select_for_classification
from steam_membership import trusted_current_membership
from steam_library_toolkit.view_model import field_evidence, normalized_games

ROOT = Path(__file__).resolve().parent


class PickerLibrary:
    def __init__(self, source=None, allow_candidates=False):
        self.source = Path(source) if source else ROOT / "steam_library.json"
        self.legacy = source is None
        self.allow_candidates = allow_candidates

    def read(self):
        pointer = self.source if self.source.name.endswith(".current.json") else manifest_path(self.source)
        if pointer.exists():
            # Resolve exactly once: another collector may switch the pointer after this call.
            path = resolve_artifact(pointer)
            directory = path.parent
            audit = json.loads((directory / "steam_library.audit.json").read_text(encoding="utf-8"))
            if not trusted_current_membership(audit) and not self.allow_candidates:
                raise ValueError("CANDIDATE_LIBRARY")
            games = normalized_games(json.loads((directory / "steam_library_classified.json").read_text(encoding="utf-8")))
            rows = json.loads(path.read_text(encoding="utf-8"))
            from steam_schema import validate_artifacts
            validate_artifacts(rows, audit)
            if ({int(g["appid"]) for g in games} != {r["appid"] for r in select_for_classification(rows)}
                    or any(g["run_id"] != audit.get("run_id") for g in games)):
                raise ValueError("GENERATION_MISMATCH")
            account = audit.get("steam_id")
            run = {"run_id": audit["run_id"], "generated_at": audit.get("generated_at"),
                   "status": audit.get("status"), "membership": audit.get("membership"),
                   "account": "***" + account[-4:] if isinstance(account, str) else None,
                   "count": len(games)}
        elif self.legacy and (ROOT / "steam_library_classified.json").exists():
            games = normalized_games(json.loads((ROOT / "steam_library_classified.json").read_text(encoding="utf-8")))
            run = {"run_id": None, "status": "legacy_unverified", "count": len(games)}
        else:
            rows = load_library(self.source)
            if not self.allow_candidates and any(r.get("membership", {}).get("state") == "candidate" for r in rows):
                raise ValueError("CANDIDATE_LIBRARY")
            from classification_overrides import load_overrides
            overrides = load_overrides()
            games = normalized_games([{**classify_one(r, overrides), "run_id": r.get("run_id")} for r in select_for_classification(rows)])
            run = {"run_id": None, "status": "legacy_unverified", "count": len(games)}
        return {"games": games, "run": run}


def create_server(library, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Paths/headers from requests do not belong in credential-safe logs.

        def respond(self, status, body, content_type="application/json; charset=utf-8"):
            payload = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        def do_GET(self):
            host = self.headers.get("Host", "")
            if host not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
                return self.respond(403, '{"error":"HOST_REJECTED"}')
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + host:
                return self.respond(403, '{"error":"ORIGIN_REJECTED"}')
            route = urlsplit(self.path).path
            if route in ("/", "/index.html"):
                return self.respond(200, (ROOT / "steam_picker.html").read_bytes(), "text/html; charset=utf-8")
            if route not in ("/api/library", "/api/run"):
                return self.respond(404, '{"error":"NOT_FOUND"}')
            try:
                data = library.read()
            except (OSError, ValueError, KeyError, TypeError):
                return self.respond(503, '{"error":"LIBRARY_UNAVAILABLE","message":"库缺失、候选未授权或运行校验失败；请检查采集结果和 --input。"}')
            return self.respond(200, json.dumps(data if route == "/api/library" else data["run"], ensure_ascii=False))

        do_HEAD = do_GET

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)
