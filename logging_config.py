"""
Sets up logging for the whole app. Call setup_logging() once at startup
(from app.py or main.py), then everywhere else just do:

    import logging
    logger = logging.getLogger(__name__)

and use logger.info/warning/error/exception as usual.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()

    if root.handlers:
        # avoid double handlers on --reload
        return

    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(handler)