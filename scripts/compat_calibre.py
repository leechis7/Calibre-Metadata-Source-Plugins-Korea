"""Install ZIPs, exercise settings UI, then verify persistence in a new process.

Run using calibre-debug -e scripts/compat_calibre.py. Uses only temporary
configuration and a temporary empty library; never opens a user's library.
"""
import importlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if '--write-settings' not in sys.argv and '--read-settings' not in sys.argv:
        with tempfile.TemporaryDirectory(prefix='calibre-compat-') as temporary:
            env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=temporary, QT_QPA_PLATFORM='offscreen')
            for stage in ('--write-settings', '--read-settings'):
                subprocess.run([sys.executable, '-e', str(Path(__file__).resolve()), '--', stage], env=env, check=True)
        return
    from calibre.constants import __version__, config_dir
    from calibre.customize.ui import add_plugin, metadata_plugins
    if Path(config_dir).resolve() != Path(os.environ['CALIBRE_CONFIG_DIRECTORY']).resolve():
        raise RuntimeError('Unexpected Calibre configuration')
    sys.path.insert(0, str(ROOT / 'scripts'))
    spec = importlib.util.spec_from_file_location('korean_plugin_build', ROOT / 'scripts/build.py')
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)
    PLUGIN_CONFIGS, get_plugin_version = build.PLUGIN_CONFIGS, build.get_plugin_version
    if '--write-settings' in sys.argv:
        from calibre.gui2 import Application
        from calibre.db.legacy import LibraryDatabase
        app = Application([])
        with tempfile.TemporaryDirectory(prefix='calibre-library-') as directory:
            db = LibraryDatabase(directory)
            try:
                for store, (label, namespace) in PLUGIN_CONFIGS.items():
                    version = get_plugin_version(ROOT / 'plugins' / store / '__init__.py')
                    source = add_plugin(str(ROOT / 'dist' / ('Calibre-Metadata-Plugin-%s-v%s.zip' % (label, version))))
                    cfg = importlib.import_module('calibre_plugins.' + namespace + '.config')
                    if store == 'aladin':
                        cfg.get_current_db = lambda: db
                    widget = source.config_widget()
                    if store == 'aladin':
                        widget.toc_checkbox.setChecked(False)
                        widget.max_downloads_spin.setValue(3)
                        widget.comments_suffix_edit.setText('설정 저장 검증')
                    else:
                        options = dict(zip((option.name for option in source.options), widget.widgets))
                        options['append_toc'].setChecked(False)
                        options['max_results'].setValue(3)
                    source.save_settings(widget)
                    widget.close()
                    print('Settings saved:', source.name, source.version, flush=True)
            finally:
                db.close()
    else:
        names = {'Aladin.co.kr', 'YES24.com', 'Kyobobook.co.kr'}
        found = set()
        for source in metadata_plugins(['identify']):
            if source.name not in names:
                continue
            found.add(source.name)
            if source.name == 'Aladin.co.kr':
                cfg = importlib.import_module('calibre_plugins.aladin_co_kr.config')
                prefs = cfg.plugin_prefs[cfg.STORE_NAME]
                valid = (prefs[cfg.KEY_APPEND_TOC] is False and prefs[cfg.KEY_MAX_DOWNLOADS] == 3
                         and prefs[cfg.KEY_COMMENTS_SUFFIX] == '설정 저장 검증')
            else:
                valid = source.prefs['append_toc'] is False and source.prefs['max_results'] == 3
            if not valid:
                raise RuntimeError('Settings did not persist: ' + source.name)
        if found != names:
            raise RuntimeError('Installed plugins missing: ' + repr(names - found))
        print('Install and settings persistence: Calibre', __version__, 'OK', flush=True)


if __name__ == '__main__':
    main()
