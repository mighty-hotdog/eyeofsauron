#!/usr/bin/env python3

"""
name:       orchestrator_bot.py
brief desc: orchestrator service for ticket search bots

author:     mighty_hotdog
created:    01May2026
modified:   02May2026
desc:       orchestrator process for controlling/managing subprocesses that perform ticket searches on the KTMB website.
            reference template on which to add more complex/custom control logic as well as biz logic.
"""

import asyncio
import logging
import signal
import sys
import os

from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Literal, Any

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
#   REQUEST QUEUE CLASSES
# ────────────────────────────────────────────────
@dataclass(frozen=True)
class Request:
    type_: str
    params: dict[str, Any]

    def __post_init__(self):
        # this method runs immediately after object initialization
        # use this method to perform validation checks on object attributes
        if not isinstance(self.type_, str):
            raise ValueError("Request type_ must be a string")
        if not self.type_:
            raise ValueError("Request type_ cannot be an empty string")
        if self.type_.isspace():
            raise ValueError("Request type_ cannot contain only whitespace")
        if self.type_.strip() != self.type_:
            raise ValueError("Request type_ cannot contain leading or trailing whitespace")
        if self.params:
            for key in self.params.items():
                if not isinstance(key, str):
                    raise ValueError("Request params key must be a string")
                if not key:
                    raise ValueError("Request params key cannot be an empty string")
                if key.isspace():
                    raise ValueError("Request params key cannot contain only whitespace")
                if key.strip() != key:
                    raise ValueError("Request params key cannot contain leading or trailing whitespace")

class RequestQueue:
    requests: List[Request] = []
    paused: bool = False

    """
    # removing all getters and setters
    # method call is 30 - 50% more expensive than direct attribute access
    # keeping these as comments to show intended interface as originally designed
    def isPaused(self) -> bool:
        return self.paused

    def pause(self):
        self.paused = True

    def unpause(self):
        self.paused = False

    def size(self) -> int:
        # method returns number of requests in the queue
        return len(self.requests)

    def peek(self, index: Optional[int] = None) -> Optional[Request]:
        # method returns request object without removing it from the queue
        return None
    
    def clear(self):
        self.requests.clear()
    """

    async def refresh(self):
        # continuously looping method that refreshes queue by loading requests from external source
        pass

    async def insert(self, req_list: List[Request], index: Optional[int] = None) -> int:
        # method inserts requests into queue and returns number of inserted requests

        # validate inputs
        if not isinstance(req_list, list) or not all(isinstance(req, Request) for req in req_list):
            # Note that "all(isinstance(req, Request) for req in req_list" returns True even for req_list = []
            raise ValueError("req_list must be a list of Request objects only")
        if index is not None and not isinstance(index, int):
            raise ValueError("index must be an integer")
        
        # processing insert
        # input is empty list: return 0 immediately
        if len(req_list) < 1:
            return 0
        
        # index is None: extend and return
        elif index is None:
            self.requests.extend(req_list)
            return len(req_list)
        
        # index is int but beyond end of list: extend and return
        elif index >= len(self.requests):
            self.requests.extend(req_list)
            return len(req_list)

        # index is int and within bounds: insert and return
        #elif index < len(self.requests):
        else:
            self.requests[index:index] = req_list   # slice assignment. more efficient than concatenation
            #self.requests = self.requests[:index] + req_list + self.requests[index:]   # concatenation
            return len(req_list)

    async def remove(self, startindex: Optional[int] = None, endindex: Optional[int] = None) -> int:
        # method removes requests from queue from startindex to endindex inclusive, and returns number of removed requests

        # validate inputs
        if startindex is not None:
            if not isinstance(startindex, int):
                raise ValueError("startindex must be an integer")
            if startindex < 0:
                raise ValueError("startindex must be greater than or equal to 0")
        if endindex is not None:
            if not isinstance(endindex, int):
                raise ValueError("endindex must be an integer")
            if endindex < 0:
                raise ValueError("endindex must be greater than or equal to 0")
        if endindex is not None and startindex is not None and endindex < startindex:
            raise ValueError("endindex must be greater than or equal to startindex")
        
        # processing remove
        # self.requests is empty list: return 0 immediately
        if len(self.requests) < 1:
            return 0
        
        elif startindex is None:
            # startindex and endindex both None: remove all requests and return
            if endindex is None:
                num = len(self.requests)
                self.requests.clear()
                return num
            
            # startindex is none and endindex is not None but within bounds: remove from 0 to endindex inclusive and return
            elif endindex < len(self.requests):
                num = endindex + 1
                self.requests = self.requests[endindex + 1:]    # slicing. keeps elements from endindex + 1 to last
                return num
            
            # startindex is none and endindex is not None but beyond end of list: remove all requests and return
            else:
                num = len(self.requests)
                self.requests.clear()
                return num
            
        elif endindex is None:
            # endindex is None and startindex is not None but within bounds: remove from startindex to last inclusive and return
            if startindex < len(self.requests):
                num = len(self.requests) - startindex + 1
                self.requests = self.requests[:startindex]      # slicing. keeps elements from 0 to startindex - 1
                return num
            
            # endindex is None and startindex is not None but beyond end of list: remove all requests and return
            else:
                num = len(self.requests)
                self.requests.clear()
                return num
        
        else:
            # startindex and endindex are not None and startindex is beyond end of list: return 0
            if startindex >= len(self.requests):
                return 0
            
            # startindex and endindex are not None and
            #   startindex is within bounds and endindex is beyond end of list:
            #   remove from startindex to last inclusive and return
            elif endindex >= len(self.requests):
                num = len(self.requests) - startindex + 1
                self.requests = self.requests[:startindex]      # slicing. keeps elements from 0 to startindex - 1
                return num
            
            # startindex and endindex are not None and
            #   startindex and endindex are both within bounds:
            #   remove from startindex to endindex inclusive and return
            #elif startindex < len(self.requests) and endindex < len(self.requests):
            else:
                num = endindex - startindex + 1
                del self.requests[startindex:endindex + 1]      # deletes elements from startindex to endindex inclusive
                                                                # more efficient than slice andconcatenation
                #self.requests = self.requests[:startindex] + self.requests[endindex + 1:]   # slice and concatenate
                return num

    def get(self, index: Optional[int] = None) -> Optional[Request]:
        # method removes request from the queue and returns the request object

        # validate inputs
        if index is not None:
            if not isinstance(index, int):
                raise ValueError("index must be an integer")
            elif index >= len(self.requests):
                raise ValueError("index must be less than the number of requests in the queue")
            elif index < 0:
                raise ValueError("index must be greater than or equal to 0")

        # processing get
        # no requests in queue: return None
        if len(self.requests) < 1:
            return None
        
        # index is None: pop 1st element and return
        elif index is None:
            return self.requests.pop(0)
        
        # index is int and within bounds: pop element at index and return
        else:
            return self.requests.pop(index)

    async def profile(self) -> dict[str, int]:
        # method scans queue and returns a dictionary of request types and their counts
        
        # scan queue
        prof: dict[str, int] = {}
        for req in self.requests:
            if req.type_ in prof:
                prof[req.type_] += 1
            else:
                prof[req.type_] = 1
        return prof


# ________________________________________________
#   JOB QUEUE CLASSES
# ────────────────────────────────────────────────
@dataclass(frozen=True)
class Job:
    type_: str
    params: dict[str, str]

class JobQueue:
    jobs: List[Job] = []
    paused: bool = False

    def isPaused(self) -> bool:
        return self.paused

    def pause(self):
        self.paused = True

    def size(self) -> int:
        return len(self.jobs)

    def insert(self, req: Job, index: Optional[int] = None) -> int:
        return len(self.jobs)   # returns index of inserted job

    def get(self, index: Optional[int] = None) -> Optional[Job]:
        return None

    def peek(self, index: Optional[int] = None) -> Optional[Job]:
        return None

    async def profile(self) -> Optional[dict[str, int]]:
        return None

    def clear(self):
        self.jobs.clear()


# ________________________________________________
#   CONFIG LIBRARY CLASSES
# ────────────────────────────────────────────────
@dataclass
class Config:
    name: str
    source: str
    params: dict[str, Any]

class ConfigLibrary:
    params: dict[str, Config]

    def size(self) -> int:
        return len(self.params)
    
    async def add(self, list: Optional[list[str]] = None) -> int:
        if list is None:
            # add all available configs
            pass
        else:
            # add configs in list
            for name in list:
                # add this config
                pass
        return 0    # return # of configs added in this call

    async def remove(self, list: Optional[list[str]] = None) -> int:
        num = 0
        if list is None:
            # remove all configs
            num = self.size()
            self.clear()
        else:
            # remove configs in list
            for name in list:
                if self.params.pop(name, None) is not None:
                    num += 1
        return num

    def get(self, name: str) -> Optional[Config]:
        return self.params.get(name)
    
    def config_list(self) -> List[str]:
        return list(self.params.keys())
    
    def clear(self):
        self.params.clear()


# ________________________________________________
#   BOT LIBRARY CLASSES
# ────────────────────────────────────────────────
@dataclass(frozen=True)
class BotType:
    name: str
    config_name: str
    attributes: Optional[dict[str, Any]]

class BotLibrary:
    bot_types: Dict[str, BotType]

    def size(self) -> int:
        return len(self.bot_types)

    async def add(self, bot_list: List[BotType]) -> int:
        num = 0
        for bot in bot_list:
            if bot.name not in self.bot_types and bot is not None:
                num += 1
                self.bot_types[bot.name] = bot
        return num      # return # of bot types added

    async def remove(self, bot_list: Optional[list[str]] = None) -> int:
        num = 0
        if bot_list is None:
            # remove all bot types
            num = self.size()
            self.clear()
        else:
            # remove bot types in list
            for name in bot_list:
                if self.bot_types.pop(name, None) is not None:
                    num += 1
        return num      # return # of bot types removed

    def get(self, name: str) -> Optional[BotType]:
        return self.bot_types.get(name)

    def bot_list(self) -> List[str]:
        return list(self.bot_types.keys())

    def clear(self):
        self.bot_types.clear()


# ________________________________________________
#   BOT POOL CLASSES
# ────────────────────────────────────────────────
@dataclass
class BotState:
    paused: bool = False
    mode: Literal["working", "reconfiguring", "idling"] = "working"

@dataclass
class BotInstance:
    id: int
    type_: BotType
    params: Config
    state: BotState

class BotPool:
    bots: Dict[int, BotInstance] = {}

    def size(self) -> int:
        return len(self.bots)

    async def profile(self) -> Optional[dict[str, int]]:
        return None

    async def add(self, bot_list: List[BotInstance]) -> int:
        num = 0
        for bot in bot_list:
            if bot.id not in self.bots and bot is not None:
                num += 1
                self.bots[bot.id] = bot
        return num      # return # of bot instances added

    async def remove(self, bot_list: Optional[list[int]] = None) -> int:
        num = 0
        if bot_list is None:
            # remove all bot instances
            num = self.size()
            self.clear()
        else:
            # remove bot instances in list
            for id in bot_list:
                if self.bots.pop(id, None) is not None:
                    num += 1
        return num      # return # of bot instances removed

    def get(self, id: int) -> Optional[BotInstance]:
        return self.bots.get(id)

    def bot_list(self) -> List[int]:
        return list(self.bots.keys())

    def clear(self):
        self.bots.clear()


# ________________________________________________
#   RESULT PIPELINE CLASSES
# ────────────────────────────────────────────────
class ResultPipeline:
    pass


# ________________________________________________
#   ORCHSTRATOR CLASSES
# ────────────────────────────────────────────────
@dataclass
class OrchestratorConfig:
    request_to_job_loop_interval: int = 5
    job_to_result_loop_interval: int = 5

@dataclass
class OrchestratorState:
    request_to_job_loop_running: bool = True
    job_manager_loop_running: bool = True

class Orchestrator:
    state: OrchestratorState
    config: OrchestratorConfig

    config_library: ConfigLibrary
    request_queue: RequestQueue
    job_queue: JobQueue
    bot_library: BotLibrary
    bot_pool: BotPool
    result_pipeline: ResultPipeline

    def __init__(self):
        self.state = OrchestratorState()
        self.config = OrchestratorConfig()

        self.config_library = ConfigLibrary()
        self.request_queue = RequestQueue()
        self.job_queue = JobQueue()
        self.bot_library = BotLibrary()
        self.bot_pool = BotPool()
        self.result_pipeline = ResultPipeline()
    
    async def request_to_job(self):
        while self.state.request_to_job_loop_running:
            request = self.request_queue.get()
            # convert request to job
            self.job_queue.insert(Job(type_="test", params={"test": "test"}))

            await asyncio.sleep(self.config.request_to_job_loop_interval)  # short 5s sleep so that CPU isn't 100%

    async def bot_manager(self):
        while self.state.job_manager_loop_running:
            await self.job_queue.profile()
            await self.bot_pool.profile()
            # do calculations
            await self.launch_bots()
            await self.kill_bots()

            await asyncio.sleep(self.config.job_to_result_loop_interval)  # short 5s sleep so that CPU isn't 100%
    
    async def launch_bots(self):
        pass

    async def kill_bots(self):
        pass


# ________________________________________________
#   PAYLOAD OBJECTS
#   custom payload objects + declarations go here
# ────────────────────────────────────────────────
payload_params = PayloadParams(loop_interval=20)
orchestrator = Orchestrator()


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
        #format="[%(levelname)-7s │ %(asctime)s │ %(process)d | %(filename)s] %(message)s",
        format="[%(levelname)s │ %(asctime)s │ %(process)d | %(filename)s] %(message)s",
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
    orchestrator.state.request_to_job_loop_running = False  # stop request to job loop
    orchestrator.state.job_manager_loop_running = False     # stop job manager loop

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
        logger.info(f"Starting main loop #{main_state.loop_count} ----------------------------------------")

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
        # add more async coroutines here as needed
        await asyncio.gather(main_loop(), payload_loop(), orchestrator.request_to_job(), orchestrator.bot_manager())
    except KeyboardInterrupt:
        # for when KeyboardInterrupt is not SIGINT or SIGTERM
        logger.info("KeyboardInterrupt received")
        await handle_shutdown()
    except Exception:
        logger.exception("Unexpected top-level exception")
        sys.exit(70)
    finally:
        logger.info("Main process stopped | uptime = %s | loops = %s", datetime.now() - main_state.start_time, main_state.loop_count)
        logger.info("Payload loops stopped | uptime = %s | loops = %s", datetime.now() - payload_state.start_time, payload_state.loop_count)
        await cleanup()
        sys.exit(0)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except SystemExit as e:
        logger.info(f"Process exiting...: {e}")
        sys.exit(e.code)