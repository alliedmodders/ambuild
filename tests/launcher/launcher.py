# vim: set sts=2 ts=8 sw=2 tw=99 et:
# Usage: launcher.py <C|CXX> <compiler> [args...]
import subprocess
import sys

lang = sys.argv[1]
argv = sys.argv[2:]
argv.insert(1, '-DLAUNCHED_{}'.format(lang))
sys.exit(subprocess.call(argv))
