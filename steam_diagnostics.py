"""Environment-only diagnostics: no token/cache reads and no network probes."""
import importlib.metadata
import json
import platform
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request


def environment_report():
    root = Path(__file__).resolve().parent
    versions = {}
    for name in ("requests", "keyring", "vdf", "jsonschema"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    node = shutil.which("node")
    node_version = None
    if node:
        try:
            raw = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5).stdout.strip()
            node_version = raw if re.fullmatch(r"v\d+\.\d+\.\d+", raw) else None
        except (OSError, subprocess.TimeoutExpired):
            pass
    packages = {}
    for name in ("steam-user", "steam-session", "undici"):
        try:
            packages[name] = json.loads((root / "node_modules" / name / "package.json").read_text(encoding="utf-8"))["version"]
        except (OSError, ValueError, KeyError):
            packages[name] = None
    return {"schema_version": 1, "os": platform.system(), "python_version": platform.python_version(),
            "node_version": node_version, "python_packages": versions, "node_packages": packages,
            "proxy_detected": bool(urllib.request.getproxies().get("https")),
            "account_binding": "not_checked", "steam_client_version": None, "network_probed": False}
