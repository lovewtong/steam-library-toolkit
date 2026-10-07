"""Check relative Markdown file links in source documents, without reading local data."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'!?\[[^\]\n]*\]\(([^)\s]+)\)')


def main():
    command = ['git', '-c', f'safe.directory={ROOT.as_posix()}', '-C', str(ROOT)]
    names = subprocess.check_output(command + ['ls-files', '-z', '--cached', '--others', '--exclude-standard'])
    failures, checked = [], 0
    for raw in sorted(set(names.split(b'\0'))):
        if not raw:
            continue
        path = ROOT / raw.decode('utf-8')
        if path.suffix != '.md' or not path.is_file():
            continue
        content = path.read_text(encoding='utf-8')
        for match in LINK.finditer(content):
            target = urlsplit(match[1])
            if target.scheme or target.netloc or not target.path or target.path.startswith('/'):
                continue
            checked += 1
            destination = (path.parent / unquote(target.path)).resolve()
            if not destination.is_relative_to(ROOT) or not destination.exists():
                line = content.count('\n', 0, match.start()) + 1
                failures.append(f'{path.relative_to(ROOT).as_posix()}:{line}: {match[1]}')
    if failures:
        print('Broken relative document links:\n' + '\n'.join(failures))
        return 1
    print(f'Relative document links passed ({checked}); URL availability and heading anchors are not checked.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
