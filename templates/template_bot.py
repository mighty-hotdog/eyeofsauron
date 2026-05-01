#!/usr/bin/env python3

"""
name:       template_bot.py
brief desc: template implementation for payload bots

author:     mighty_hotdog
created:    01May2026
modified:   01May2026
desc:       a reference implementation of a payload bot. customize as needed.

todos:      implement boilerplate + sample code for async http stuff using aiohttp
"""

import asyncio
import logging
import signal
import sys
import os

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Literal

import tomllib
import tomli_w      # pip install tomli-w
import tempfile
import shutil

import aiohttp      # pip install aiohttp


# ____________________________________________________________________________________
#   PAYLOAD FUNCTIONALITY
#   custom payload logic goes here
# ────────────────────────────────────────────────────────────────────────────────────
# sample payload params class, modify as needed
@dataclass
class PayloadParams:
    loop_interval: int


# ________________________________________________
#   PAYLOAD OBJECTS
#   custom payload objects + declarations go here
# ────────────────────────────────────────────────
payload_params = PayloadParams(loop_interval=20)


# ________________________________________________
#   PAYLOAD WORK
#   customize as needed
# ────────────────────────────────────────────────
async def payload_work():
    pass


# ________________________________________________
#   PAYLOAD LOOP
#   customize as needed
#   to be included in asyncio.gather() in main()
# ────────────────────────────────────────────────
async def payload_loop():
    while payload_state.running:
        payload_state.loop_count += 1
        logger.info(f"Starting payload loop #{payload_state.loop_count} ----------------------------------------")

        try:
            await payload_work()
        except Exception as e:
            logger.error(f"Error in payload_work(): {e}")
            # handle error

        # loop interval for payload_loop(), independent of main_loop()
        await asyncio.sleep(payload_params.loop_interval)


# ____________________________________________________________________________________
#   DAEMON SCAFFOLDING
# ────────────────────────────────────────────────────────────────────────────────────
# immutable dataclass for default config values
# throws dataclasses.FrozenInstanceError if try to set attributes after object created
# need to jump thru hoops to get around this if really needed
@dataclass(frozen=True)
class DefaultConfig:
    config_file: str
    loop_interval: int
    log_level: Literal[0, 10, 20, 30, 40, 50]

@dataclass
class ProcessState:
    running: bool = True
    start_time: datetime = datetime.now()
    loop_count: int = 0

@dataclass
class ProcessConfig:
    config_file: str
    loop_interval: int
    log_level: Literal[0, 10, 20, 30, 40, 50]
    # default values, immutable
    default_config: DefaultConfig = DefaultConfig(config_file=f"./config/{Path(__file__).stem}_config.toml", loop_interval=10, log_level=20)

    def __init__(self):
        self.default()

    def default(self):
        self.config_file = self.default_config.config_file
        self.loop_interval = self.default_config.loop_interval
        self.log_level = self.default_config.log_level

    def load(self, path: Optional[str] = None) -> bool:
        # loads config from path in arg
        # if arg not valid, loads from path in memory
        # if neither is valid, loads from default
        # returns True if config changed, False if not
        if path is None or not Path(path).is_file():
            if self.config_file is None or not Path(self.config_file).is_file():
                self.default()
                return True
            else:
                path = self.config_file
        
        logger.debug(f"Loading config from {path}")
        try:
            with open(Path(path), "rb") as f:
                data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            logger.error(f"TOML parse error reading {path}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error reading {path}: {e}")
            return False

        changed = False
        for key, value in data.items():
            if not hasattr(self, key):  # ignore unknown keys
                continue
            if value is None:   # ignore None values
                continue
            if value != self.__dict__[key]:     # ignore unchanged values
                setattr(self, key, value)       # set attribute to config file value
                changed = True
        return changed

    def save(self, path: Optional[str] = None) -> bool:
        # saves config to path in arg
        # if arg not valid, saves to path in memory
        # if neither is valid, saves to default
        # set config_file to save path
        # returns True if save successful, False if not
        if path is None:
            if self.config_file is None:
                self.config_file = self.default_config.config_file
            path = self.config_file

        logger.debug(f"Saving config to {path}")
        try:
            # atomic write pattern: write to temp file 1st then rename
            # avoids corruption of destination file due to interrupted/incomplete/failed writes
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".tmp", dir=Path(path).parent, delete=False) as tmp:
                data = self.__dict__
                tomli_w.dump(data, tmp)
                tmp.flush()
                tmp.close()
            shutil.move(tmp.name, path)
        except Exception as e:
            logger.error(f"Error writing to {path}: {e}")
            # clean up temp file if exists
            if 'tmp' in locals() and Path(tmp.name).exists():
                Path(tmp.name).unlink()
            return False

        self.config_file = path
        return True

def init_main():
    # initialize main process objects
    # initialize main process config
    pass

def setup_logging(lvl: Optional[Literal[0, 10, 20, 30, 40, 50]] = None):
    if lvl is None:
        lvl = main_config.log_level
    logger.info(f"Setting log level to {lvl}")
    logging.basicConfig(
        level=lvl,
        format="[%(levelname)-7s │ %(asctime)s │ %(process)d | %(filename)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,     # add this to facilitate setup_logging() calls even after main process startup
        handlers=[
            logging.StreamHandler(sys.stdout),
            #logging.FileHandler(config.log_file),    # disable file logging for now
        ]
    )

def setup_signal_handlers():
    loop = asyncio.get_event_loop()
    for sig in [signal.SIGINT, signal.SIGTERM]:
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(handle_shutdown(s)))
    if hasattr(signal, "SIGHUP"):
        loop.add_signal_handler(signal.SIGHUP, lambda s=signal.SIGHUP: asyncio.create_task(handle_reconfig(s)))

async def handle_shutdown(sig: Optional[signal.Signals] = None):
    if sig is not None:
        logger.info(f"Received {sig.name} — shutting down")
    # add shutdown code here
    main_state.running = False      # stop main loop
    payload_state.running = False   # stop payload loop

async def handle_reconfig(sig: Optional[signal.Signals] = None):
    if sig is not None:
        logger.info(f"Received {sig.name} — reconfiguring")
    # add reconfig code here
    logger.info(f"Loop interval set to {main_config.loop_interval} seconds")
    setup_logging()

async def cleanup():
    # add cleanup code here
    # clean up all tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

async def update_config() -> bool:
    # update main process config
    # return True if changed, False if not
    if main_config.load():
        main_config.save()
        return True
    return False


# ________________________________________________
#   MAIN PROCESS OBJECTS
# ────────────────────────────────────────────────
logger = logging.getLogger(__name__)
main_state = ProcessState()
payload_state = ProcessState()
main_config = ProcessConfig()


# ________________________________________________
#   MAIN WORK
# ────────────────────────────────────────────────
async def main_work():
    if await update_config():
        await handle_reconfig()


# ________________________________________________
#   MAIN LOOP
# ────────────────────────────────────────────────
async def main_loop():
    while main_state.running:
        main_state.loop_count += 1
        logger.info(f"Starting loop #{main_state.loop_count} ----------------------------------------")

        try:
            # do work
            await main_work()
        except Exception as e:
            logger.error(f"Error in main_work(): {e}")
            # handle error

        # loop interval for main_loop(), independent of payload_loop()
        await asyncio.sleep(main_config.loop_interval)


# ________________________________________________
#   ENTRY POINT
# ────────────────────────────────────────────────
async def main():
    init_main()
    setup_logging()
    setup_signal_handlers()

    try:
        await asyncio.gather(main_loop(), payload_loop())   # add more async coroutines here as needed
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
        # handle keyboard interrupt
    except Exception:
        logger.exception("Unexpected top-level exception")
        sys.exit(70)
    finally:
        logger.info(f"Main process {__name__} stopped")
        await cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as e:
        logger.info(f"Process exiting...: {e}")
        sys.exit(e.code)