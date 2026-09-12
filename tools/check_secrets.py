"""Conservative source-file secret checks. Never print the matched secret value."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = [
    re.compile(rb"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}"),
    re.compile(rb'''(?i)["']?(?:steam_api_key|api_key|webapi_key)["']?\s*[:=]\s*["'][a-f0-9]{32}["']'''),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
]


def main():
    files = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard']).split(b'\0')
    failures = []
    for raw in set(files):
        if not raw:
            continue
        path = Path(raw.decode('utf-8'))
        if not (ROOT / path).is_file():
            continue
        data = (ROOT / path).read_bytes()
        if any(pattern.search(data) for pattern in PATTERNS):
            failures.append(str(path))
    if failures:
        print('Possible credentials found in: ' + ', '.join(sorted(failures)))
        return 1
    print('Source credential pattern scan passed. This does not scan Git history or ignored local artifacts.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
