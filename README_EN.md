# Steam Library Local Collection & Auto Classification

## Recommended workflow

This repo keeps all classification locally and does not modify Steam by default.

| Step | Command | Notes |
|------|---------|------|
| 1. Get library data | `python steam_collect.py --local-session --no-store --strict` | Windows with Steam signed in; see setup for other authorization methods |
| 2. Classify | Collection generates classifications | Stored in the same verified generation |
| 3. Pick by category | `python steam_picker.py --serve` | Open the local web UI |

**Start the picker UI (after classification):**

```bash
cd /path/to/steam-library-toolkit
python steam_picker.py --serve
```

**If library data changed:**

```bash
python steam_picker.py --serve
```

---

## Overview

```
QR authorization / explicit local session / optional API config
        ↓
  steam_collect.py  →  steam_library.json
        ↓
  classify_steam_games.py →  steam_library_classified.json
        ↓
  steam_picker.py --serve  →  local web UI

(optional) classify_games.py → game_library_classified.csv / .md
```

---

## 1. Install and authorize

Requires Python 3.10+ and Node.js 18+:

```bash
python -m pip install -r requirements.txt
npm ci
# Keep desktop Steam online; scan with the Steam mobile app
python steam_collect.py --login --no-store
```

QR authorization is stored only in Windows Credential Manager, macOS Keychain or a supported Linux system keyring. Later runs reuse it. Unavailable or plaintext keyrings are rejected.

On Windows, an isolated environment avoids mismatched pip/Python installations:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm ci
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict
```

Use `.\.venv\Scripts\python.exe` instead of `python` in subsequent commands. Missing `vdf` reports `PYTHON_DEPENDENCY_MISSING`, which does not mean Steam is logged out. QR persistence also requires `keyring`.

The collector immediately reports credential loading, network mode and its current stage, with a waiting update every 10 seconds. It establishes its own server connection even when desktop Steam is logged in. A connection taking over 60 seconds reports `CM_CONNECT_TIMEOUT`; missing web authorization after authentication reports `WEB_SESSION_TIMEOUT`. Detected HTTP(S) proxy settings apply to CM, QR authentication and subsequent Web requests without logging proxy addresses or passwords. Ctrl+C cleans up the helper and reports cancellation; an older `KeyboardInterrupt` traceback alone does not indicate a failed Steam login.

On Windows, explicitly reuse the currently logged-in desktop account for this run:

```powershell
python steam_collect.py --local-session --no-store
```

This reads Steam's local login cache using the current Windows user's DPAPI. It does not persist the token. Steam cache formats may change; use `--login` if unavailable.

`config_local.json` is optional. For API-only mode, copy `config_local.example.json` and set `steam_api_key` and `steam_id`. Authenticated client collection does not require an API key. `--account STEAMID64` overrides the configured identity; mismatched authentication/snapshot accounts are rejected. `--machine NAME` selects one online desktop, defaulting to this computer.

## 2. Collect library data

```bash
# Reuse saved QR authorization, collect client + licenses + Web API
python steam_collect.py --no-store
# Stop on source degradation, preserving existing output
python steam_collect.py --local-session --no-store --strict
# Optionally enrich store metadata
python steam_collect.py --local-session
```

Enrich an existing `--no-store` generation without authenticating again:

```bash
python steam_enrich.py --input steam_live_test.json -o steam_enriched.json
python steam_picker.py --serve --input steam_enriched.json
# Optional: request metadata only for selected library apps (repeatable)
python steam_enrich.py --input steam_live_test.json -o steam_enriched_sample.json --appid 550
```

Requires a verified generation from client membership collection and a separate output path. Membership, app types, playtime evidence and original collection timestamps stay unchanged; enrichment does not revalidate current ownership. The audit records `operation=metadata_enrichment`, `parent_run`, and per-app store states. `metadata.state=partial` means some requests failed; previous metadata is retained. `--appid` restricts requests, not the output membership. Both classifications are regenerated. `--cache-dir` and `--refresh-metadata` reuse the sequential rate limit, cache and bounded retries. Input and output remain locked during enrichment; a first pass over a large library can take a while.

Each collection writes an immutable `.steam_library.runs/<run_id>/` generation containing the library, audit, snapshot, both classifications, CSV/Markdown, summary and probe status. All files are validated and flushed before atomically replacing `steam_library.current.json`, the sole commit pointer. Old runs are retained.

Flat library/audit files and `--snapshot-out` are compatibility exports. Export failure warns without invalidating the committed generation. Both Python classifiers prefer the adjacent `.current.json` and verify all artifact hashes. External readers of flat files do not get cross-file transactional consistency. `-o custom.json` uses `custom.current.json` and `.custom.runs/`. Do not use a `.current.json` filename as a normal output.

Choose the matching collection target for the picker; a separate flat classification export is no longer required:

```bash
python steam_picker.py --serve --input steam_live_test.json
```

Every request verifies the selected pointer and reads classification plus metadata from one immutable generation. Refreshing the page follows a newly published run. The page shows capture time, status, masked account and run ID. Old flat classification is a compatibility fallback only when the default pointer is absent, labeled legacy_unverified. Independent classification CLIs still support `-i` for exports.

### Membership verification and candidates

ClientComm `GetClientAppList` is a single RPC without AppOverview's streaming completion flags. The adapter requires valid JSON, an explicit apps array, a unique desktop session, matching machine/account in client_info, two identical AppID sets, and an unchanged session afterward. Audit retains state, stable error codes and completeness evidence.

Repeated agreement is a guardrail, not proof against persistent server omissions: `protocol_completion_marker=false`, `semantic_completeness_proven=false`. More than 20% removed members versus the previous same-account live generation blocks publication. After verifying a real change, adjust `--max-unexplained-removal-ratio` (0..1). A different account must use a separate output path. Missing legacy identity metadata prevents baseline comparison and emits a warning.

Only a validated client response determines current membership. Extra API/license/snapshot IDs stay in audit differences. Without it, a matching historical snapshot takes precedence over Web API as a **candidate** collection, saved separately as `steam_library.candidates.json` with its own generation pointer. API-only and offline modes have the same candidate semantics. License evidence alone cannot establish default membership; `--allow-candidate-membership` explicitly enables the experimental union, independently of the `--allow-candidates` output-path override. `--allow-candidates` explicitly permits publishing candidates to the requested path. `--strict` rejects source degradation before committing; optional metadata/playtime failure does not invalidate successful membership providers.

### Evidence and classification

Type precedence: client > PICS > store/cache > historical snapshot > unknown. Unrecognized values become `unknown`, preserving `raw_app_types`. Names never establish a known game type. Package-level license evidence includes own/shared/free/expiring/package_ids; `shared_only`, `free_only`, `expiring_only` describe app-set differences, rather than overlapping entitlements. Missing package metadata is partial.

Time precedence: Web API > ClientGetLastPlayedTimes > legacy client fields > legacy license fields > snapshot. Evidence retains values, source timestamps and conflicts rather than taking a maximum. States are unknown, known_zero, known_nonzero and historical. Historical values remain visibly labeled and are excluded from the current `playtime_known` count. Real protobuf decoding preserves absent versus explicit zero.

Both Python entrypoints share loading, generation validation and type selection while retaining their different classification schemes:

```bash
python classify_games.py
python classify_steam_games.py
python classify_games.py --include-type game,demo
python classify_games.py --include-type all
python classify_games.py -i steam_library.candidates.json --allow-candidates --include-unknown
```

Known games are selected by default. Legacy include-demo/include-non-game/include-unknown switches remain supported; include-unknown-type is an alias. Explicit include-type takes precedence over legacy switches. Unselected rows remain in the source library.

### Snapshots, modes and caching

```bash
python steam_collect.py --source api --no-store
python steam_collect.py --owned-only --no-store
python steam_collect.py --source client --local-session --no-store
python steam_collect.py --local-session --no-store --snapshot-out library.snapshot.json
python steam_collect.py --apps-file library.snapshot.json --no-api --no-store
```

Snapshots retain schema version 2 and add run_id, producer commit/dirty state, identity, capture time, completeness, record count and apps checksum. Imports verify identity/count/hash while supporting old v2 and UTF-8/UTF-16 BOM AppID-name text. TXT identity/age cannot be verified. Freshness includes age, fresh within 24 hours and stale afterward; this does not infer expired ownership.

Store cache TTLs: success 7 days, not_found 6 hours, access_denied 10 minutes, rate_limited/parse_error 60 seconds, transient_error 30 seconds. Refresh or relocate via refresh-metadata/cache-dir; no-store skips enrichment. Metadata failures never remove members.

Access tokens stay in the Node helper, which performs authenticated HTTP requests and returns whitelisted data. Refresh credentials use private pipes and approved OS keyrings; local-session does not persist them. Python relays configured HTTP(S) system proxy settings through the private pipe. Logs use stable codes rather than raw exceptions.

ClientComm does not expose CAppOverview fields. `playtime_probe.json` lists unresolved IDs and explicitly reports `APP_OVERVIEW_NOT_EXPOSED_BY_CLIENTCOMM`; this is not a completed live AppOverview experiment. Windows QR persistence, macOS/Linux keyrings, family-sharing transitions and refunds still require real environment tests. Do not claim those scenarios from unit tests alone.

Audit includes type-grouped set differences, previous-run additions/removals, field provenance and cache status. Generation JSON artifacts/nonempty rows carry run_id; the manifest binds every file, including empty outputs, by hash.

### Verified results (2026-09-12)

A real Windows run using the local Steam session, project virtual environment and HTTP(S) proxy passed `--local-session --no-store --strict`: 388 client records (377 games, 5 applications, 2 demos, 4 betas) versus 358 Web API records. The client restored 30 omitted records (27 games, 2 demos, 1 application). Playtime was known for 361 records and remained unknown for 27. Artifact hashes, classification AppID sets and run IDs were verified. Regression tests passed: 63 Python and 17 Node tests.

This is one account's observed result, not an expected count for other accounts or proof that GetOwnedGames returns the full library. Unknown playtime, protocol-level completeness guarantees and the untested platform/account-change scenarios above remain open.

```bash
python -m unittest discover -s tests -v
node --test tests/test_steam_client.cjs tests/test_steam_web_sources.cjs
```

---

## 3. Classification output

```bash
python classify_games.py
```

- Input: `steam_library.json`
- Output:
  - `game_library_classified.csv`
  - `game_library_classified.md`
- Rules live in `classify_games.py` (`MAIN_CATEGORY_RULES`, `TAG_RULES`)
- More details in `CLASSIFICATION_RULES.md`

---

## 4. Use the picker UI

```bash
python steam_picker.py --serve
```

Use filters (primary/sub/vibe/intensity) in the browser, then open the game in Steam.

---

## 5. Write collections back to Steam (optional)

If you want to import `steam_collections_result.json` into Steam Collections:

1. Fully exit Steam (including tray)
2. Install Node deps:
   ```bash
   npm install
   ```
3. Explicitly select the target account's 32-bit AccountID (not SteamID64), then run:
   ```powershell
   $env:STEAM_ID_32 = "YOUR_32_BIT_ACCOUNT_ID"
   node import_script.js
   ```

Notes:
- The script tries LevelDB first; if no namespace is found, it falls back to `cloud-storage-namespace-1.json` and writes a `.bak` backup.
- After import, reopen Steam and verify in Library → Collections.
- Missing or invalid account configuration exits before writes. This legacy collection path still needs separate persistence validation; collection, enrichment and the picker do not require it.

## Report implementation and migration

- `--strict-membership` requires a verified live client, while allowing auxiliary API degradation. Existing `--strict` retains the stricter enabled-membership-source policy; optional playtime can still fail. `--require-source web_api` adds a required provider.
- `--diagnose` prints environment/dependency versions without reading credentials or probing the network.
- Temporary HTTP failures use at most three attempts and respect Retry-After within the request budget. Authentication and invalid payload failures are not blindly retried. Node audit attempts count actual HTTP attempts across the source's RPCs.
- The CLI holds an OS lock through collection and publication. Another collector targeting the same output fails with OUTPUT_BUSY. Locks release on process death; lock files remain intentionally. Direct Python publication callers must hold the same lock.
- Failed diagnostics are stored separately under `.<output>.failed-runs/`, without raw exception text or credentials. They never replace current. Successful runs add detailed `missing_from_web_api.json` evidence without inventing causes.
- Local JSON Schemas validate v2 arrays, audit and new snapshots before publication. CSV retains the old display column and adds nullable numeric playtime_minutes and playtime_status.
- Missing/malformed store categories preserve null capabilities; an explicit empty list means false. Old caches are invalidated. Broad Action/Indie classification and whitespace filtering are fixed.
- The picker binds only 127.0.0.1 and serves only `/`, `/index.html`, `/api/library`, `/api/run`. No project directory listing, config, Git or snapshot downloads. `--port` and `--no-browser` control startup.
- `npm test` and the existing unittest suite run offline. Windows/Linux/macOS CI jobs have passed; they do not verify real Steam authentication. requirements-tested.txt pins tested direct dependencies, not every transitive dependency. `python tools/check_secrets.py` scans source patterns, not Git history.
- Families, refunds, cross-platform live QR, AppOverview completeness and the remaining unknown times are still unverified/research tasks. No account entitlement changes are automated. See [RELEASE_NOTES.md](RELEASE_NOTES.md).
