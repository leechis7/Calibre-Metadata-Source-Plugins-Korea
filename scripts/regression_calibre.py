"""Offline catalogue regression tests with the real Calibre loader and Metadata.

Run with calibre-debug -e scripts/regression_calibre.py after building ZIPs.
CALIBRE_CONFIG_DIRECTORY must point to an isolated directory in this repository.
All HTTP responses are synthetic; no bookstore requests are made.
"""
import os
import importlib.util
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest


def main():
    root = Path(__file__).resolve().parents[1]
    configured = os.environ.get('CALIBRE_CONFIG_DIRECTORY')
    if not configured or (root / '.dev-deps') not in Path(configured).resolve().parents:
        raise SystemExit('Set CALIBRE_CONFIG_DIRECTORY to an isolated folder inside .dev-deps.')
    if '--isolated' not in sys.argv:
        # Calibre imports installed plugins at startup. A previously used config
        # can retain old shared modules even after add_plugin installs a new ZIP.
        # Use a fresh process and an empty config for every regression run.
        Path(configured).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='regression-', dir=configured) as temporary:
            env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=temporary)
            result = subprocess.run([sys.executable, '-e', str(Path(__file__).resolve()), '--', '--isolated'], env=env)
        raise SystemExit(result.returncode)
    from calibre.constants import __version__, config_dir
    from calibre.customize.ui import add_plugin
    if Path(config_dir).resolve() != Path(configured).resolve():
        raise SystemExit('Calibre did not use the requested isolated configuration.')

    spec = importlib.util.spec_from_file_location('korean_plugin_build', root / 'scripts/build.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    PLUGIN_CONFIGS, get_plugin_version = build.PLUGIN_CONFIGS, build.get_plugin_version
    templates = {}
    for store, (label, _) in PLUGIN_CONFIGS.items():
        version = get_plugin_version(root / 'plugins' / store / '__init__.py')
        templates[store] = add_plugin(str(root / 'dist' / ('Calibre-Metadata-Plugin-%s-v%s.zip' % (label, version))))

    sys.path.insert(0, str(root / 'tests'))
    from test_catalog import CatalogTests

    def source_factory(store):
        template = templates[store]
        return type(template)(template.plugin_path)

    CatalogTests.stores = tuple(PLUGIN_CONFIGS)
    CatalogTests.source_factory = staticmethod(source_factory)
    print('Offline regression with Calibre', __version__, flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CatalogTests))
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == '__main__':
    main()
