"""
Entry point for `python -m katrain_qt`.

CRITICAL: Shims are installed at the top of app_qt.py, which happens
before any katrain imports. This module simply delegates to app_qt.main().
"""

from katrain_qt.app_qt import main

if __name__ == "__main__":
    main()
