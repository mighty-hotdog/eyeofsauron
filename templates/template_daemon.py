#!/usr/bin/env python3
"""
Continuous Service Template
--------------------------
Long-running process with graceful shutdown, logging, and health structure.
"""

import logging
import signal
import sys
import time
import os
from typing import Optional
from datetime import datetime
from pathlib import Path

# ────────────────────────────────────────────────
#   CONFIGURATION
# ────────────────────────────────────────────────

SCRIPT_NAME = Path(__file__).stem
LOG_LEVEL    = logging.INFO
LOOP_INTERVAL = 10.0          # seconds

# You can also load from environment variables or config file
# import os
# LOOP_INTERVAL = float(os.getenv("LOOP_INTERVAL", 10))

# ────────────────────────────────────────────────
#   LOGGING SETUP
# ────────────────────────────────────────────────

def setup_logging() -> None:
    logging.basicConfig(
        level=LOG_LEVEL,
        format="%(asctime)s  │ %(levelname)-7s │ %(name)s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # logging.FileHandler(f"{SCRIPT_NAME}.log"),
        ]
    )

logger = logging.getLogger(SCRIPT_NAME)


# ────────────────────────────────────────────────
#   STATE / SHARED DATA
# ────────────────────────────────────────────────

class ServiceState:
    """Simple in-memory state / flags"""

    def __init__(self):
        self.running: bool = True
        self.start_time: datetime = datetime.now()
        self.loop_count: int = 0
        self.last_error: Optional[str] = None


state = ServiceState()


# ────────────────────────────────────────────────
#   GRACEFUL SHUTDOWN
# ────────────────────────────────────────────────

def handle_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name
    logger.info(f"Received {sig_name} → initiating shutdown...")
    state.running = False


def register_signals():
    signals = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGHUP"):
        signals.append(signal.SIGHUP)

    for sig in signals:
        signal.signal(sig, handle_shutdown)


# ────────────────────────────────────────────────
#   MAIN WORK (this is what you customize)
# ────────────────────────────────────────────────

def do_work() -> bool:
    """
    Return True  = work completed successfully
    Return False = temporary error (should retry next loop)
    Raise       = serious error (will be caught & logged)
    """
    try:
        # ── Your actual business logic here ────────────────
        logger.info(f"Working... (loop #{state.loop_count})")
        time.sleep(1.2)  # simulate some work

        # Example: call API, read queue, process files, etc.
        # check_something()
        # send_notification()
        # update_database()

        return True

    except Exception as exc:
        logger.exception("Critical error in do_work()")
        state.last_error = str(exc)
        return False


# ────────────────────────────────────────────────
#   MAIN LOOP
# ────────────────────────────────────────────────

def main_loop():
    logger.info("Service starting...")
    logger.info(f"PID = {os.getpid()}")

    while state.running:
        state.loop_count += 1

        success = do_work()

        if not success:
            logger.warning("Work iteration failed → will retry")

        # Important: small sleep even on success (avoid CPU 100%)
        time.sleep(LOOP_INTERVAL)

    logger.info(f"Main loop exited after {state.loop_count} iterations")


# ────────────────────────────────────────────────
#   ENTRY POINT
# ────────────────────────────────────────────────

def main():
    setup_logging()
    register_signals()

    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception:
        logger.exception("Unexpected top-level exception")
        sys.exit(70)  # EX_SOFTWARE
    finally:
        uptime = datetime.now() - state.start_time
        logger.info(f"Service stopped | uptime = {uptime} | loops = {state.loop_count}")
        # cleanup()   # close connections, flush buffers, etc.


if __name__ == "__main__":
    main()