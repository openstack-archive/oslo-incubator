"""
 wrapper for pyflakes to ignore gettext based warning:
     "undefined name '_'"
"""
import sys

import pyflakes.checker
from pyflakes.scripts.pyflakes import main

if __name__ == "__main__":
    orig_builtins = set(pyflakes.checker._MAGIC_GLOBALS)
    pyflakes.checker._MAGIC_GLOBALS = orig_builtins | set(['_'])
    sys.exit(main())
