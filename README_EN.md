# Steam Library Local Collection & Auto Classification

## Recommended workflow

This repo keeps all classification locally and does not modify Steam by default.

| Step | Command | Notes |
|------|---------|------|
| 1. Get library data | `python steam_collect.py` or reuse `steam_library.json` | Skip if you already have it |
| 2. Classify | `python classify_steam_games.py` | Generates `steam_library_classified.json` |
| 3. Pick by category | `python steam_picker.py --serve` | Open the local web UI |

**Start the picker UI (after classification):**

```bash
cd /path/to/steam-collections
python steam_picker.py --serve
```

**If library data changed:**

```bash
python classify_steam_games.py && python steam_picker.py --serve
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
pip install -r requirements.txt
npm ci
# Keep desktop Steam online; scan with the Steam mobile app
python steam_collect.py --login --no-store
```

QR authorization is stored only in Windows Credential Manager, macOS Keychain or a supported Linux system keyring. Later runs reuse it. Unavailable or plaintext keyrings are rejected.

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

The output remains a top-level JSON array, defaulting to `steam_library.json`, with an adjacent `steam_library.audit.json`. Custom `-o` paths get a same-name `.audit.json` sidecar.

Both Python classification entrypoints now select known `game` types by default. Use `--include-demo`, `--include-non-game` (all known types), or `--include-unknown` as needed. Old JSON/TXT without `app_type` requires `--include-unknown` or recollection. Unselected records remain in the source JSON. Unknown time renders as “未知”, rather than `0h`.

### Sources and limits

| Source | Role |
|--------|------|
| `web_api` | `GetOwnedGames` supplies names/playtime; free-game and free-subscription flags are enabled and unvetted filtering disabled, but omissions remain possible |
| `client_library` | `IClientCommService` reads the selected online desktop; a successful response determines this run's membership |
| `licenses` | `steam-user` client licenses and PICS metadata supply types, account/shared entitlement evidence and audit differences; include DLC/tools and are not equivalent to a game library |
| `license_file` | Account-bound JSON snapshot or legacy TXT; historical evidence, not current ownership |

An isolated experimental `Player.ClientGetLastPlayedTimes` protocol adapter also attempts to fill missing playtime. Its failure never aborts membership collection; `client_playtime_status` records the outcome. Web API time wins; unavailable values remain `null`.

With a live client list, extra snapshot/API/license IDs appear only in audit differences, preventing historical records from resurrecting removed members. Without the client, successful sources are unioned as candidates and marked `degraded`. `--strict` requires the live desktop and all enabled membership sources to succeed, preserving existing output otherwise. It does not require store enrichment or experimental time enrichment to succeed. Total source failure, account mismatch and malformed input preserve the library too. Individual JSON files are atomically replaced; multiple output files are not one transaction.

`status=ok` means source calls succeeded, not a universal completeness guarantee. Client filters, shared entitlements, free apps and profile counts have different scopes. The desktop must be online and third-party protocols can change.

Store metadata is cached for 7 days in `.steam_cache`; override with `--cache-dir`, refresh with `--refresh-metadata`. Initial requests are spaced by 1.5 seconds. Store failures/delisting never remove membership. `--no-store` skips enrichment entirely.

### Other modes and snapshots

```bash
python steam_collect.py --source api --no-store
python steam_collect.py --owned-only --no-store
python steam_collect.py --source client --local-session --no-store
python steam_collect.py --local-session --no-store --snapshot-out library.snapshot.json
# Fully offline: no credentials/config read and no network
python steam_collect.py --apps-file library.snapshot.json --no-api --no-store
```

JSON snapshot format: `{"schema_version":2,"steam_id":"17-digit ID","generated_at":"ISO timestamp with timezone","apps":[{"appid":10,"name":"Name","app_type":"game"}]}`. Identity must match. Without a live desktop, snapshot output is explicitly degraded. Historical snapshot time is not treated as newly collected time.

Legacy TXT accepts `AppID Name` per line, UTF-8, UTF-8 BOM or UTF-16 BOM. It cannot verify account or age and emits a warning. Use only an export from your confirmed account. Login/error text and empty exports are rejected. `--apps-file` conflicts with `--owned-only`. API/TXT with `--no-store` may lack types, requiring `--include-unknown` for classification.

### Output fields

| Field | Meaning |
|-------|---------|
| `appid`, `name`, `app_type` | Identity and type, including `unknown` |
| `playtime_minutes`, `playtime_2weeks_minutes` | Minutes; unknown is `null`, confirmed zero is `0` |
| `playtime_available` | Whether total playtime is available |
| `last_played_at`, `last_played_iso` | Unix/UTC timestamps, nullable |
| `sources`, `provenance` | Record and field-level sources |
| `membership_source`, `membership_status` | Current desktop observation or unverified candidate completeness |
| `ownership` | License evidence: `account_license`, `shared`, or `unknown` |
| `genres`, `categories`, `is_multiplayer`, `is_controller` | Optional store information, `[]`/`null` if unavailable |

Audit contains identity, timestamps, source statuses, type/time counts and AppID differences, but no tokens. Secrets travel through private child pipes, never command arguments or collection output. QR credentials persist only in the system keyring; local-session credentials are not saved.

Offline tests:

```bash
python -m unittest discover -s tests -v
node --test tests/test_steam_client.cjs
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
3. Run:
   ```bash
   node import_script.js
   ```

Notes:
- The script tries LevelDB first; if no namespace is found, it falls back to `cloud-storage-namespace-1.json` and writes a `.bak` backup.
- After import, reopen Steam and verify in Library → Collections.
