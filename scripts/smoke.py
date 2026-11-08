#!/usr/bin/env python
"""Run the real Calibre source paths, including Kyobo API recovery.

Build ZIPs first. Arguments are forwarded to smoke_calibre.py; use --report PATH
for a per-store JSON report. This is a manual check, never a scheduled job.
"""
import os
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, CALIBRE_CONFIG_DIRECTORY=str(root / '.dev-deps/live-diagnostics'))
    raise SystemExit(subprocess.call(['calibre-debug', '-e', str(root / 'scripts/smoke_calibre.py'), '--']
                                    + sys.argv[1:], env=env))
