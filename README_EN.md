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
config_local.json (local secrets, never commit)
        ↓
  steam_collect.py  →  steam_library.json
        ↓
  classify_steam_games.py →  steam_library_classified.json
        ↓
  steam_picker.py --serve  →  local web UI

(optional) classify_games.py → game_library_classified.csv / .md
```

---

## 1. Local config (do not commit)

1. Copy `config_local.example.json` to `config_local.json`
2. Fill in:
   - **steam_api_key**: get one at https://steamcommunity.com/dev/apikey
   - **steam_id**: your 64-bit Steam ID
3. `config_local.json` is ignored by `.gitignore`

---

## 2. Collect library data

```bash
pip install -r requirements.txt
python steam_collect.py
```

- Default mode calls Steam Store API to enrich metadata (slower)
- Fast mode: `python steam_collect.py --no-store`

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
