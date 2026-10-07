"""Bootstrap supported old commands without requiring an editable installation."""
from importlib import import_module
from pathlib import Path
import sys


def entry(module_name, invoked_name):
    source = Path(__file__).resolve().parent / 'src'
    sys.path.insert(0, str(source))
    module = import_module(module_name)
    if invoked_name == '__main__':
        raise SystemExit(module.main())
    # Imported old commands use the same module object, including patchable globals.
    sys.modules[invoked_name] = module
