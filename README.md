# steam-library-toolkit

[![CI](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/lovewtong/steam-library-toolkit/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Collect, audit and organize your Steam library with local browsing and collection-plan exports.

**English** | [简体中文](README.zh.md)

A local Python and Node.js toolkit for collecting a Steam library, inspecting source evidence, enriching store metadata, correcting classifications and choosing games in a browser. Unknown values remain visible, and each published run keeps its own verifiable artifacts.

The npm manifest retains the historical private helper name `steam-collections`; use this repository's source, not a published npm package.

## Table of Contents

- [Security](#security)
- [Background](#background)
- [Install](#install)
- [Usage](#usage)
- [Features and versions](#features-and-versions)
- [Support and limitations](#support-and-limitations)
- [Documentation](#documentation)
- [Maintainers](#maintainers)
- [Contributing](#contributing)
- [License](#license)

## Security

- Keep credentials, cookies, account configuration and personal library dumps out of issues and pull requests. `config_local.json`, `*.local.json`, caches and `outputs/` are ignored by Git.
- `--local-session` explicitly uses the signed-in Windows account's local Steam credentials for this process. QR authorization uses an approved OS credential store, with no plaintext fallback.
- The picker listens on `127.0.0.1` and serves only its page and library endpoints. The validated Python workflow does not support automatic Steam collection writes.

## Background

Steam's `GetOwnedGames` can omit games visible in the client. This project cross-checks the online client list, licenses, Web API and saved snapshots instead of assuming one API returns the entire library.

The goal is to collect as much of the library as the evidence supports, make unknown values and provenance inspectable, and keep classifications correctable. Client-response validation is an engineering check, not proof of absolute server-side completeness.

## Install

### Requirements

| Component | Verified environment |
| --- | --- |
| Windows with desktop Steam signed in | Primary live acceptance environment; one account |
| Python | 3.14.2 in Windows live acceptance; 3.12 in offline CI |
| Node.js and npm | Node 22.19.0 in Windows acceptance; Node 22 in CI |
| Git | Required for the clone commands below |

Install [Python](https://www.python.org/downloads/), [Node.js](https://nodejs.org/en/download) and [Git](https://git-scm.com/downloads) first. Previously suggested Python 3.10 / Node 18 minimums have not received the same acceptance testing.

### Windows PowerShell

Install the published stable version:

```powershell
git clone --branch v1.0.0 https://github.com/lovewtong/steam-library-toolkit.git
cd steam-library-toolkit
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tested.txt
npm ci
.\.venv\Scripts\python.exe -m pip check
```

Run subsequent commands from the project root. The explicit virtual-environment path avoids mixing Python installations. `requirements-tested.txt` pins direct dependencies, not every cross-platform transitive dependency.

For development, clone without `--branch v1.0.0`. Open-PR features require that PR's branch; they are not part of the stable tag. See [Features and versions](#features-and-versions).

## Usage

### Collect, enrich and browse

Keep desktop Steam online and signed in, then run:

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --strict-membership -o outputs/library.json
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/enriched.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/enriched.json
```

Collection also creates audit and classification artifacts. Enrichment fetches store metadata without logging in again; a large library may take several minutes on a cold cache. The picker opens in your browser. Press `Ctrl+C` in its terminal to stop it.

`--strict-membership` requires a verified live client list while allowing auxiliary-source degradation. Use `--strict` when all enabled membership sources must succeed. If local credentials are unavailable, replace `--local-session` with `--login` for QR authorization.

### Correct classifications and export a plan

Create `classification_overrides.local.json` using the [AppID correction guide](CLASSIFICATION_OVERRIDES.md), then publish a separate corrected run:

```powershell
.\.venv\Scripts\python.exe steam_reclassify.py --input outputs/enriched.json -o outputs/corrected.json
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/corrected.json
```

In another terminal, replace `YOUR_STEAMID64` with the account used for collection:

```powershell
$steamAccount = 'YOUR_STEAMID64'
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --dry-run
.\.venv\Scripts\python.exe -B steam_sync_collections.py --input outputs/corrected.json --account $steamAccount --export-only -o outputs/collections.local.json
```

Dry-run previews without writing a plan. Export checks the account, run, membership and file hashes; it does not write to Steam or revalidate current ownership. Enrichment and reclassification require separate output names.

### CLI

```powershell
.\.venv\Scripts\python.exe steam_collect.py --help
.\.venv\Scripts\python.exe steam_collect.py --diagnose
.\.venv\Scripts\python.exe steam_enrich.py --help
.\.venv\Scripts\python.exe steam_picker.py --help
.\.venv\Scripts\python.exe steam_sync_collections.py --help
```

Diagnostics inspect dependencies without reading credentials or probing the network. See [advanced usage](USAGE.md) for accounts, strict modes, snapshots, caches, troubleshooting and artifact layout.

## Features and versions

| Capability | Availability |
| --- | --- |
| Client library collection, source audit and unknown-value tracking | v1.0.0 |
| Store enrichment with caching, bounded requests and cancellation | v1.0.0 |
| AppID corrections, offline rebuilding, CSV/Markdown and local picker | v1.0.0 |
| Verified collection-plan preview and export | v1.0.0 |
| Classification review queue and six additional AppID corrections | On main; included in the unpublished v1.1.0 draft |
| Developer/publisher metadata, corrections, filters and plan groups | Unreleased; [PR #10](https://github.com/lovewtong/steam-library-toolkit/pull/10) |
| Acquisition-date grouping and first-observed tracking | Planned; not implemented |

The published release is [v1.0.0](https://github.com/lovewtong/steam-library-toolkit/releases/tag/v1.0.0). [v1.1.0](V1_1_RELEASE_PLAN.md) is still a draft; manufacturer facets are outside its frozen target. Check [Releases](https://github.com/lovewtong/steam-library-toolkit/releases) for publication status.

On the manufacturer feature branch, the picker adds developer/publisher filters. The plan CLI supports `--group-by developers publishers` and exact-name `--developer` / `--publisher` filters. See [manufacturer facets](MANUFACTURER_FACETS.md) for correction examples and verification results.

## Support and limitations

- Windows single-account collection, enrichment, correction/reversal, browsing and plan export have been exercised in a real environment. See [Windows acceptance](R3_WINDOWS_ACCEPTANCE.md).
- Windows, Linux and macOS run offline CI. This does **not** establish live authentication support on all three platforms.
- Client-list consistency checks do not prove Steam never omits a record. API/snapshot fallbacks are labeled as candidates; unknown playtime is not converted to zero.
- Classification includes heuristics. Reviewed samples do not establish full-library accuracy; personal corrections remain part of the workflow.
- Multi-account transitions, Families, refunds, expiring access and long-term QR authorization need further live acceptance.
- Legacy Python writes are disabled. Separate Node/LevelDB writers have not passed the same safety and persistence acceptance and are outside the recommended workflow.

## Documentation

README and usage guides are maintained in English and Chinese. Detailed design and acceptance reports below are currently mainly in Chinese.

| Topic | Document |
| --- | --- |
| Advanced commands, files and troubleshooting | [English](USAGE.md) · [简体中文](USAGE.zh.md) |
| Stable scope and migration | [Scope](STABLE_RELEASE_SCOPE.md) · [Release notes](RELEASE_NOTES.md) |
| Enrichment and field coverage | [Metadata guide](METADATA_ENRICHMENT.md) |
| Classification and corrections | [Rules](CLASSIFICATION_RULES.md) · [Corrections](CLASSIFICATION_OVERRIDES.md) |
| Review queue and manufacturers | [Review queue](CLASSIFICATION_REVIEW_QUEUE.md) · [Manufacturers](MANUFACTURER_FACETS.md) |
| Collection-plan validation | [Plan guide](STEAM_SYNC_README.md) |
| Time-field semantics | [Time contract](TIME_FIELD_CONTRACT.md) |
| Performance and live evidence | [R2 baseline](R2_PERFORMANCE_BASELINE.md) · [R3 acceptance](R3_WINDOWS_ACCEPTANCE.md) |
| Audit fixes and open boundaries | [Remediation record](AUDIT_REMEDIATION.md) |

## Maintainers

[@lovewtong](https://github.com/lovewtong). Ask questions and report reproducible bugs in the [issue tracker](https://github.com/lovewtong/steam-library-toolkit/issues).

## Contributing

Issues and pull requests are welcome. Describe the problem, expected behavior and verification performed; distinguish offline tests from live Steam validation. Include only redacted diagnostics, never credentials or personal library dumps.

For code changes, run:

```powershell
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_*.py"
npm test
.\.venv\Scripts\python.exe tools/check_secrets.py
git diff --check
```

Keep English and Chinese README/usage guides synchronized. Update the relevant contract or acceptance document when behavior changes. Changes require review before merging; do not present untested account scenarios as supported.

## License

[MIT](LICENSE) © 2026 Steam Collections Contributors.
