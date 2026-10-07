import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from steam_library_toolkit.build_identity import payload_hash, producer_package_info
from steam_library_toolkit.storage.runs import new_run_metadata

VERSION = '1.3.0.dev0'


class BuildIdentityTests(unittest.TestCase):
    def package(self, root):
        (root / 'resources').mkdir()
        (root / '__init__.py').write_bytes(b'# package\n')
        (root / 'resources/rule.json').write_bytes(b'{"rule":true}\n')

    def stamp(self, root):
        info = {'schema_version': 1, 'package_version': VERSION, 'payload_sha256': payload_hash(root, VERSION)}
        (root / 'resources/build-info.json').write_text(json.dumps(info), encoding='utf-8')
        return info

    def installed(self, root):
        return (patch('steam_library_toolkit.paths.SOURCE_ROOT', None),
                patch('steam_library_toolkit.paths.PACKAGE_ROOT', root),
                patch('importlib.metadata.version', return_value=VERSION))

    def test_identity_ignores_location_bytecode_and_stamp_but_tracks_names_bytes_and_version(self):
        with tempfile.TemporaryDirectory() as name:
            first, second = Path(name) / 'a', Path(name) / 'b'
            first.mkdir(); second.mkdir()
            self.package(first); self.package(second)
            before = payload_hash(first, VERSION)
            self.assertEqual(before, payload_hash(second, VERSION))
            self.stamp(first)
            (first / '__pycache__').mkdir()
            (first / '__pycache__/__init__.pyc').write_bytes(b'compiled')
            self.assertEqual(before, payload_hash(first, VERSION))
            self.assertNotEqual(before, payload_hash(first, '1.3.0'))
            (second / '__init__.py').rename(second / 'other.py')
            self.assertNotEqual(before, payload_hash(second, VERSION))
            (first / '__init__.py').write_bytes(b'# edited\n')
            self.assertNotEqual(before, payload_hash(first, VERSION))

    def test_installed_run_uses_verified_identity_and_never_the_working_directory_git(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.package(root); info = self.stamp(root)
            a, b, c = self.installed(root)
            with a, b, c, patch('subprocess.run', side_effect=AssertionError('No checkout Git probe')):
                with patch('steam_library_toolkit.diagnostics.environment_report', return_value={}):
                    producer = new_run_metadata()['producer']
            self.assertEqual(producer, {'git_commit': None, 'dirty': None, 'package_version': VERSION,
                'build_id': 'sha256:' + info['payload_sha256'], 'build_status': 'verified'})

    def test_older_wheel_without_stamp_remains_unknown_and_usable(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.package(root)
            a, b, c = self.installed(root)
            with a, b, c:
                self.assertEqual(producer_package_info(), {'package_version': VERSION,
                    'build_id': None, 'build_status': 'unavailable'})

    def test_modified_resource_is_not_reported_as_the_original_build(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.package(root); self.stamp(root)
            (root / 'resources/rule.json').write_bytes(b'{}')
            a, b, c = self.installed(root)
            with a, b, c:
                result = producer_package_info()
            self.assertEqual(result['build_status'], 'modified')
            self.assertIsNone(result['build_id'])

    def test_invalid_stamp_and_version_mismatch_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); self.package(root)
            examples = ['not json', '[]', json.dumps({'schema_version': 1, 'package_version': 'wrong',
                         'payload_sha256': 'a' * 64}), json.dumps({'schema_version': True,
                         'package_version': VERSION, 'payload_sha256': 'a' * 64})]
            a, b, c = self.installed(root)
            with a, b, c:
                for example in examples:
                    with self.subTest(example=example):
                        (root / 'resources/build-info.json').write_text(example, encoding='utf-8')
                        self.assertEqual(producer_package_info()['build_status'], 'invalid')

    def test_source_version_comes_from_its_project_not_another_installed_distribution(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            (root / 'pyproject.toml').write_text('[project]\nversion = "1.3.0.dev0"\n', encoding='utf-8')
            with patch('steam_library_toolkit.paths.SOURCE_ROOT', root), \
                 patch('importlib.metadata.version', side_effect=AssertionError('No installed-version guess')):
                self.assertEqual(producer_package_info(), {'package_version': VERSION,
                    'build_id': None, 'build_status': 'source'})

    def test_missing_or_invalid_source_version_remains_unknown(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            with patch('steam_library_toolkit.paths.SOURCE_ROOT', root):
                for content in ('not toml', '[project]\nversion = 1\n', '[project]\nversion = ""\n'):
                    with self.subTest(content=content):
                        (root / 'pyproject.toml').write_text(content, encoding='utf-8')
                        self.assertIsNone(producer_package_info()['package_version'])
