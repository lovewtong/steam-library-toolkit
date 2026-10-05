# Advanced usage

[English README](README.md) · [简体中文](USAGE.zh.md)

Run commands from the project root. Examples use the Windows virtual environment created in the README. Replace account and machine placeholders before use. Stable commands below work in v1.0.0; later features are marked separately.

## Accounts and sources

```powershell
# Reuse local Windows credentials for this process; do not save them.
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --account YOUR_STEAMID64 -o outputs/library.json
# Alternatively, scan with the Steam mobile app and save authorization in the OS keyring.
.\.venv\Scripts\python.exe steam_collect.py --login --no-store -o outputs/library.json
# Reuse previously saved QR authorization.
.\.venv\Scripts\python.exe steam_collect.py --no-store -o outputs/library.json
```

`config_local.json` is optional for client authentication. For API-only use, copy `config_local.example.json` and configure your API key and SteamID64 locally. API-only results are candidates, not a verified current client library. `--account` overrides the configured account; mismatched source accounts are rejected. Use separate output directories for different accounts.

`--machine MACHINE_NAME` selects an online client explicitly. The default targets this machine, not an arbitrary other device. A signed-in desktop does not eliminate the helper's own server connection and authentication step.

| Option | Behavior |
| --- | --- |
| `--strict-membership` | Require a verified current client list; allow auxiliary-source degradation |
| `--strict` | Require the current client and all enabled membership providers to succeed |
| `--require-source web_api` | Also require the named auxiliary source; repeatable |
| `--source client` | Select client collection |
| `--source api` | Select API-only collection, producing candidate membership |
| `--owned-only` | Apply traditional API filters; not a completeness guarantee |
| `--no-store` | Skip store metadata requests |

Strict membership policies do not require optional metadata or playtime providers to succeed. `--strict` failures leave the previous current pointer intact.

## Candidate data and completeness

`GetClientAppList` is checked for response shape, account, machine session and two matching AppID sets. It has no protocol completion marker that proves semantic completeness. An unexplained removal above 20% of the previous same-account client list blocks publication; only adjust `--max-unexplained-removal-ratio` after checking the change.

When the live client is unavailable, account-matched snapshots or the Web API can supply historical/candidate records. These normally go to a separate `.candidates.json` target and pointer. `--allow-candidates` permits candidate publication at the requested path; `--allow-candidate-membership` separately enables the experimental license-based candidate union. Neither proves current ownership.

## Snapshots

```powershell
.\.venv\Scripts\python.exe steam_collect.py --local-session --no-store --snapshot-out outputs/library.snapshot.json -o outputs/library.json
# Offline import; no credentials or network are used with these flags.
.\.venv\Scripts\python.exe steam_collect.py --apps-file outputs/library.snapshot.json --no-api --no-store -o outputs/imported.json
```

Snapshots preserve account, observation time, completeness evidence, record count and checksum. Legacy `AppID name` text imports cannot establish identity or age. A snapshot's freshness describes its age, not whether ownership has expired.

## Enrichment and caching

```powershell
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/enriched.json --workers 2
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/library.json -o outputs/sample.json --appid 550 --appid 730
.\.venv\Scripts\python.exe steam_enrich.py --input outputs/enriched.json -o outputs/refreshed.json --refresh-metadata --cache-dir outputs/store-cache
```

Inputs must have a valid run pointer and trusted client membership. Outputs must be separate. `--appid` limits requests, not output membership. Enrichment preserves membership, application type, time evidence and the original collection time; it does not revalidate ownership.

Workers range from 1 to 4 and share a request-start interval and cooldown. Missing or invalid metadata retains prior values; an explicit empty array can replace a prior array. A successful request does not imply complete fields. `metadata.state=partial` reports incomplete request coverage without deleting games.

Successful responses are cached for seven days; `not_found` for six hours; temporary failures for shorter periods. A not-found response does not prove permanent delisting. Current `main` uses cache v6 and refetches older entries on demand; released versions retain their own cache format. See [metadata semantics](METADATA_ENRICHMENT.md).

## Files and backups

For `-o outputs/library.json`:

```text
outputs/
├── library.json                  # Compatibility export
├── library.audit.json            # Compatibility audit export
├── library.current.json          # Pointer and hashes for the committed run
└── .library.runs/
    └── <run_id>/                 # Library, audit, classifications and reports
```

The pointer changes only after the complete run is validated and durable. Readers verify hashes and load artifacts from the same run. Preserve the pointer **and its referenced hidden run directory** when backing up; the flat JSON alone is not a verified run. Do not edit files inside an existing run.

Runs include `steam_library.audit.json`, `classified.json`, `classified.csv`, `classified.md`, `steam_library_classified.json`, applied correction rules, summaries and available snapshots/probe reports. Failure diagnostics for this example use a separate `outputs/.library.failed-runs/` directory. Lock files may remain after exit; operating-system locks release when the process ends. Old runs are not automatically removed.

## Classification and browsing

```powershell
.\.venv\Scripts\python.exe classify_games.py -i outputs/enriched.json
.\.venv\Scripts\python.exe classify_steam_games.py -i outputs/enriched.json
.\.venv\Scripts\python.exe classify_games.py -i outputs/enriched.json --include-type game,demo
.\.venv\Scripts\python.exe steam_picker.py --input outputs/enriched.json --name BioShock --list
.\.venv\Scripts\python.exe steam_picker.py --serve --input outputs/enriched.json --port 8765 --no-browser
```

The classifiers select explicit `game` types by default. `--include-type all` includes other and unknown types; candidate inputs require `--allow-candidates`. Standalone classifiers write flat exports; they do not replace a verified run's frozen classifications. Use `steam_reclassify.py` to apply corrections to a new verified run.

The picker uses Chinese classification labels in both documentation modes. Refresh the browser after publishing a new run. `--open INDEX` launches a game in Steam; it is not a preview operation.

The review queue is available on main and in the v1.1.0 draft, not v1.0.0:

```powershell
.\.venv\Scripts\python.exe steam_review_classification.py --input outputs/enriched.json
```

Developer/publisher filters and plan groups are available on `main`, but are not included in v1.0.0 or the v1.1.0 draft. See [manufacturer usage](MANUFACTURER_FACETS.md). Use the README's commands to preview and export plans; do not pass them to legacy Node writers.

## Evidence and troubleshooting

Types use client, PICS, store/cache and historical evidence, leaving unresolved types unknown. Playtime retains per-field provenance and conflicts; unknown, known zero and historical values are distinct. Client-list stability cannot resolve all missing playtime or prove a complete library.

| Symptom | What to check |
| --- | --- |
| `PYTHON_DEPENDENCY_MISSING` | Install requirements using the same virtual-environment Python that runs the scripts |
| `CLIENT_AUTH_UNAVAILABLE` | A desktop login alone may lack usable cached credentials; check the selected account or use `--login` |
| `CM_CONNECT_TIMEOUT` / `WEB_SESSION_TIMEOUT` | Inspect the reported stage and existing network/proxy configuration; these are different failure stages |
| `OUTPUT_BUSY` | Another process holds the output lock; do not remove files to bypass it |
| Candidate data rejected by the picker | Obtain a verified client run, or explicitly opt into candidate browsing |
| Unknown metadata or `partial` enrichment | Read per-app field states and source errors; missing does not mean unsupported |
| Old data still displayed | Check `--input`, the selected current pointer and browser refresh; flat exports do not replace verified generations |

`--diagnose` is a credential-free, offline first check. Configured HTTP(S) proxies are used without printing their addresses or passwords. Do not share raw authentication or proxy diagnostics containing secrets. See [audit fixes](AUDIT_REMEDIATION.md), [time semantics](TIME_FIELD_CONTRACT.md) and [release migration](RELEASE_NOTES.md) for details.
