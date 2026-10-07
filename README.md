# steam-library-toolkit

[![CI](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Collect, audit and organize your Steam library with local browsing and collection-plan exports.

**English** | [简体中文](README.zh.md)

Export your Steam library to local files, add store metadata and browse games by genre, mood, developer or publisher. You can adjust classifications per AppID and export a collection plan.

## Table of Contents

- [Security](#security)
- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Versions](#versions)
- [Limitations](#limitations)
- [Documentation](#documentation)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Security

Account settings belong in `config_local.json`; personal corrections belong in `classification_overrides.local.json`. Both are ignored by Git. Keep credentials, cookies and personal library exports out of bug reports.

The browser interface runs on `127.0.0.1`. Local-session authentication uses your existing Steam credentials for the current process; QR authorization is saved in the OS credential store.

## Background

This started with two problems: `classify_games.py` had no entry point, and `GetOwnedGames` missed some games visible in the Steam client. Collection now uses the online client list alongside licenses, the Web API and snapshots. The audit files record which sources succeeded and where each value came from.

## Install

Use Windows with Steam installed and signed in. The project has been tested with Python 3.12/3.14 and Node.js 22. See the download pages for [Python](https://www.python.org/downloads/), [Node.js](https://nodejs.org/en/download) and [Git](https://git-scm.com/downloads).

From PowerShell:

```powershell
git clone https://github.com/lovewtong/steam-library-toolkit.git
cd steam-library-toolkit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
npm ci
```

The checkout includes developer/publisher filters, first-observation dates and family collection. The package layout described here is a development change after v1.2.0. For the stable release, clone with `--branch v1.2.0` and follow the tag's README and [release notes](https://github.com/lovewtong/steam-library-toolkit/releases/tag/v1.2.0); that tag uses root scripts and has no `pyproject.toml` or installed commands.

You can also install this checkout with `python -m pip install .`, then use `steam-library collect`, `steam-library enrich`, `steam-library picker` and the other commands listed by `steam-library --help`. From a wheel installation, run `steam-library node --install` to prepare the Node dependencies. There is no published PyPI package; `1.3.0.dev0` is development build metadata, not a released version.

In a source checkout, default configuration, cache and output paths remain at the repository root. An installed wheel uses the current working directory. Set `STEAM_LIBRARY_HOME` before starting a command to choose another data directory; explicit `--input` and `--output` paths retain their usual meaning. See [installed usage](USAGE.md#installed-commands-and-data-directories).

## Usage

Run these commands from the project root, with Steam online and signed in.

### Collect and browse

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict-membership -o outputs/library.json
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/enriched.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/enriched.json
```

The first command collects the library and creates its audit and classification files. The second adds store metadata. A large library can take several minutes on the first pass; later runs reuse the cache. The last command opens the browser interface. Press `Ctrl+C` in the terminal to stop the server.

`--strict-membership` requires a live client list and a checked family source. Use `--no-family` with a separate output for client-only collection. If local authentication fails, use `--login` instead of `--local-session` to sign in with a QR code.

### Adjust classifications

Add your rules to `classification_overrides.local.json`, following the [correction guide](docs/guides/CLASSIFICATION_OVERRIDES.md), then rebuild to a new output:

```powershell
.\.venv\Scripts\python.exe steam_reclassify.py --input outputs/enriched.json -o outputs/corrected.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/corrected.json
```

You can also inspect classifications that need review:

```powershell
.\.venv\Scripts\python.exe steam_review_classification.py --input outputs/corrected.json
```

### Export a collection plan

In another terminal, set the SteamID64 of the account you collected:

```powershell
$steamAccount = 'YOUR_STEAMID64'
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --dry-run
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --export-only -o outputs/collections.local.json
```

`--dry-run` previews the plan; `--export-only` saves it as JSON. The tool checks the saved account, library and file hashes before export. It does not write collections to Steam.

Add `--group-by developers publishers` for manufacturer groups, or `--developer "NAME"` / `--publisher "NAME"` to filter by an exact name.

Filter by `--first-seen-year 2026 --first-seen-month 10` and group plans by `first_seen_year` / `first_seen_month`. These dates refer to the first saved observation of a client or family member, not the purchase date. See [time classification](docs/guides/TIME_CLASSIFICATION.md) for history and unknown values.

### Help

Each script supports `--help`. For dependency problems, start with:

```powershell
.\.venv\Scripts\python.exe steam_collect.py --diagnose
```

This check runs offline. See [advanced usage](USAGE.md) for account selection, snapshots, cache settings and troubleshooting. Keep the `.current.json` pointer and its hidden run directory together when backing up results.

## Versions

[v1.2.0](https://github.com/lovewtong/steam-library-toolkit/releases/tag/v1.2.0) is the latest published release, fixed at `044a435`. It adds developer/publisher filters, first-observation history and checked family collection to the existing collection, audit, enrichment, correction, browsing and plan-export workflow.

The package layout and installed commands on `main` are later development changes, outside v1.2.0. See [Releases](https://github.com/lovewtong/steam-library-toolkit/releases) for published versions.

The frozen scope, upgrade acceptance and publication checks are recorded in the [release plan](docs/releases/V1_2_RELEASE_PLAN.md), [release notes](RELEASE_NOTES.md) and [publication record](releases/v1.2.0-publication.json).

## Limitations

- Live collection has been tested on Windows with one account. Linux and macOS have automated tests, but live account login still needs testing.
- Steam sources can disagree or omit entries. API and snapshot fallbacks are marked as candidates; missing playtime and metadata stay unknown.
- Classification rules sometimes need manual correction. Developer and publisher names follow the store listing unless you override them.
- Multi-account switching and expiring access need more testing. The browser's classification labels are currently in Chinese.
- v1.1.0 can miss Steam Families games. v1.2.0 adds a checked family source; see [family collection](docs/guides/STEAM_FAMILIES.md) and the [scenario report](docs/validation/REAL_SCENARIO_VALIDATION.md). This does not guarantee that every family game is collected or playable.
- Plans are export-only. The older Node/LevelDB writers are not part of the supported workflow.
- Exact purchase dates are not available. First-observation dates only describe the saved history available to the tool.

## Documentation

- [Document index](docs/README.md)
- [Advanced usage](USAGE.md) · [进阶用法](USAGE.zh.md)
- [Classification rules](docs/guides/CLASSIFICATION_RULES.md) · [Personal corrections](docs/guides/CLASSIFICATION_OVERRIDES.md) · [Review queue](docs/guides/CLASSIFICATION_REVIEW_QUEUE.md)
- [Metadata enrichment](docs/guides/METADATA_ENRICHMENT.md) · [Developers and publishers](docs/guides/MANUFACTURER_FACETS.md)
- [Collection plans](docs/guides/STEAM_SYNC_README.md) · [Time fields](docs/guides/TIME_FIELD_CONTRACT.md) · [Time classification](docs/guides/TIME_CLASSIFICATION.md)
- [Release notes](RELEASE_NOTES.md) · [Stable scope](docs/releases/STABLE_RELEASE_SCOPE.md)
- Test reports: [performance](docs/validation/R2_PERFORMANCE_BASELINE.md), [Windows workflow](docs/validation/R3_WINDOWS_ACCEPTANCE.md), [bug fixes](docs/validation/AUDIT_REMEDIATION.md)
- [Current account scenarios](docs/validation/REAL_SCENARIO_VALIDATION.md) · [Next release scope](docs/releases/V1_2_RELEASE_PLAN.md)

The detailed guides and test reports are mostly in Chinese.

## Maintainers

[@lovewtong](https://github.com/lovewtong). Questions and bugs can go in [Issues](https://github.com/lovewtong/steam-library-toolkit/issues).

## Contributing

Please include the command you ran, the expected result and the error message when reporting a bug. Pull requests are welcome. For code changes, run:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
npm test
.\.venv\Scripts\python.exe tools/check_secrets.py
.\.venv\Scripts\python.exe tools/check_docs.py
.\.venv\Scripts\python.exe -m pip install build==1.6.1
.\.venv\Scripts\python.exe tools/check_distribution.py
git diff --check
```

Keep the English and Chinese README and usage guides in sync when changing commands or behavior.

The eight root Python commands remain compatibility entries. Implementation lives in `src/steam_library_toolkit/`; its `resources/` contains the browser page, schemas, built-in rules and Node bridge. Examples are in `examples/`, developer scripts in `tools/`, and retired experiments in `legacy/`. See [repository layout](docs/ARCHITECTURE.md).

## License

[MIT](LICENSE) © 2026 Steam Collections Contributors.
