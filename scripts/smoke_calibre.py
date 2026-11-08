"""Run built ZIPs with calibre-debug and a separate test configuration.

Set CALIBRE_CONFIG_DIRECTORY to a folder inside this repository before running.
This script uses the real Calibre loader, browser, Metadata and HTML sanitizer.
"""
import argparse
import json
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from queue import Queue
from threading import Event

spec = importlib.util.spec_from_file_location('korean_plugin_build', Path(__file__).with_name('build.py'))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
PLUGIN_CONFIGS, ROOT_DIR, get_plugin_version = build.PLUGIN_CONFIGS, build.ROOT_DIR, build.get_plugin_version


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', choices=['all'] + list(PLUGIN_CONFIGS), default='all')
    parser.add_argument('--title', default='트렌드 코리아 2027')
    parser.add_argument('--isbn', default='9791124073483')
    parser.add_argument('--author', action='append', default=[], help='Author to include in title searches.')
    parser.add_argument('--allow-missing-toc', action='store_true', help='Some foreign titles have no YES24 table of contents.')
    parser.add_argument('--report', type=Path, help='Write a JSON report for all requested stores.')
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--isolated', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    configured = os.environ.get('CALIBRE_CONFIG_DIRECTORY')
    if not configured or (ROOT_DIR) not in Path(configured).resolve().parents:
        raise SystemExit('Set CALIBRE_CONFIG_DIRECTORY to a separate test folder inside this repository.')
    if not args.isolated:
        # A used config imports the previous ZIP before add_plugin can replace it.
        # Start with an empty config so this run always tests the current build.
        Path(configured).mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='smoke-', dir=configured) as temporary:
            env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=temporary)
            result = subprocess.run([sys.executable, '-e', str(Path(__file__).resolve()), '--']
                                    + sys.argv[1:] + ['--isolated'], env=env)
        raise SystemExit(result.returncode)

    from calibre.constants import __version__, config_dir
    from calibre.customize.ui import add_plugin, metadata_plugins
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from diagnostics import check_source
    if Path(config_dir).resolve() != Path(configured).resolve():
        raise SystemExit('Calibre is not using the requested test configuration.')
    names = []
    for store, (label, _) in PLUGIN_CONFIGS.items():
        if args.store not in ('all', store):
            continue
        version = get_plugin_version(ROOT_DIR / 'plugins' / store / '__init__.py')
        archive = ROOT_DIR / 'dist' / f'Calibre-Metadata-Plugin-{label}-v{version}.zip'
        source = add_plugin(str(archive))
        names.append(source.name)
    print('Calibre', __version__, flush=True)
    rows = []
    for source in metadata_plugins(['identify']):
        if source.name in names:
            for row in check_source(source, args.title, args.author, args.isbn, args.timeout):
                rows.append(row)
                print('%s %s: %s (%s)' % (row['store'], row['mode'], row['status'], row['stage']), flush=True)
    report = {'calibre': __version__, 'results': rows}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    if not rows or any(row['status'] not in ('ok', 'partial_metadata') for row in rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
