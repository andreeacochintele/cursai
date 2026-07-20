"""
Centralized logging configuration.

Call setup_logging() once, as early as possible, from each entry point
(app.py's lifespan, main.py's main()). Every other module then just does:

    import logging
    logger = logging.getLogger(__name__)

and logs normally (logger.info/.warning/.error/.exception) — they all
funnel through the same handler/format configured here, so log level and
formatting only ever need to change in one place, and every line is
consistently timestamped and tagged with the module it came from.

Why this instead of print(): print() gives no level (can't tell an INFO
from an ERROR at a glance), no timestamp, no source module, and can't be
redirected/filtered without touching every call site. logger.exception()
also auto-attaches the full traceback, replacing the manual
traceback.print_exc() calls scattered around the codebase.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()

    if root.handlers:
        # Already configured — avoids duplicate log lines if this gets
        # called more than once (e.g. under --reload's re-import).
        return

    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(handler)