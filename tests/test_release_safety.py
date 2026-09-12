import os
from pathlib import Path
import subprocess
import unittest


class ImportAccountGuardTests(unittest.TestCase):
    def test_missing_invalid_or_64bit_account_exits_before_import(self):
        root = Path(__file__).resolve().parents[1]
        for value in ('', 'not-an-account', '0', str(2**32), str(2**56)):
            with self.subTest(value=value):
                result = subprocess.run(['node', 'import_script.js'], cwd=root,
                                        env={**os.environ, 'STEAM_ID_32': value},
                                        capture_output=True, encoding='utf-8', timeout=10)
                self.assertEqual(result.returncode, 1)
                self.assertIn('STEAM_ID_32', result.stderr)
                self.assertIn('未执行收藏写入', result.stderr)


if __name__ == '__main__':
    unittest.main()
