"""Build-time resource copies; project metadata lives exclusively in pyproject.toml."""
import json
from pathlib import Path
import runpy
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        source = Path(__file__).resolve().parent
        resources = Path(self.build_lib) / 'steam_library_toolkit/resources'
        bridge = resources / 'node_bridge'
        bridge.mkdir(parents=True, exist_ok=True)
        manifest = json.loads((source / 'package.json').read_text(encoding='utf-8'))
        manifest.pop('scripts', None)  # Developer and legacy shortcuts are not installed commands.
        (bridge / 'package.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        (bridge / 'package-lock.json').write_bytes((source / 'package-lock.json').read_bytes())
        rules = resources / 'rules'
        rules.mkdir(parents=True, exist_ok=True)
        (rules / 'CLASSIFICATION_RULES.md').write_bytes((source / 'docs/guides/CLASSIFICATION_RULES.md').read_bytes())
        # Deterministic payload identity survives sdist -> wheel and excludes itself.
        identity = runpy.run_path(str(source / 'src/steam_library_toolkit/build_identity.py'))
        version = self.distribution.get_version()
        info = {'schema_version': 1, 'package_version': version,
                'payload_sha256': identity['payload_hash'](resources.parent, version)}
        (resources / 'build-info.json').write_text(json.dumps(info, sort_keys=True) + '\n', encoding='utf-8')


setup(cmdclass={'build_py': BuildPy})
