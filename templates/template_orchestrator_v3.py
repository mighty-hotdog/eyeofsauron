#!/usr/bin/env python3

"""
name:       basic_orchestrator.py
brief desc: reference template orchestrator process for controlling multiple subprocesses

author:     mighty_hotdog
created:    31Mar2026
modified:   01Apr2026
desc:       generic basic orchestrator process for controlling/managing subprocesses.
            intended as reference template on which to add more complex/custom control logic as well as biz logic.
"""

import asyncio
import logging
import signal
import sys
from dataclasses import dataclass
from typing import List, Dict, Optional
import aiohttp  # pip install aiohttp; for health checks

import json
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# subprocess config _____________________________________________________________________
##########################################################
# subprocess biz logic config                            #
# modify/customize as needed                             #
##########################################################
@dataclass
class SubprocBizConfig:
    params_file: str    # params file name, contains subprocess biz logic parameters
    input_data_file: str
    output_data_file: str


##########################################################
# generic subprocess system config                       #
# pertains to process control, no biz logic              #
##########################################################
@dataclass
class SubprocSysConfig:
    program_name: str           # subprocess program name
    cli_cmd: List[str]          # command line args when starting subprocess
    config_file: str            # config file name, contains subprocess system config ie: contents of this dataclass
    program_path: str = "./"    # path to subprocess executable
    config_path: str = "./"     # path to subprocess config file
    restart: bool = True        # True: start subprocess on startup + restart on failure
                                # False: subprocess disabled ie: do not start/restart at all
    max_restarts: int = 5       # max number of start/restart attempts; set to 0 to disable restart
    backoff_base: float = 2.0   # base delay between restart attempts; compounds exponentially with each subsequent attempt
    loop_interval: float = 10.0 # subprocess loops every 10 seconds; modify/customize as needed
    jitter: bool = False        # add random jitter to loop iterations; to evade target system's bot detection
    log_level: str = "INFO"     # subprocess log level

    # === New: Health check settings ===
    health_url: Optional[str] = None          # e.g. "http://127.0.0.1:8000/health"
    health_interval: float = 0.0              # seconds between checks; set to 0.0 to disable health checks
    health_timeout: float = 5.0               # timeout per check
    max_consecutive_failures: int = 3         # restart after this many failed checks in a row


##########################################################
# combined subprocess config                             #
# includes both system and biz logic configs             #
##########################################################
@dataclass
class SubprocConfig:
    program_name: str   # subprocess program name, identical to sys.program_name
    sys: SubprocSysConfig
    biz: SubprocBizConfig


# orchestrator config ___________________________________________________________________
##########################################################
# orchestrator biz logic config                          #
# modify/customize as needed                             #
##########################################################
@dataclass
class OrchestratorBizConfig:
    params_file: str    # params file name, contains orchestrator biz logic parameters
    input_data_file: str
    output_data_file: str


##########################################################
# generic orchestrator system config                     #
# pertains to subprocess orchestration, no biz logic     #
##########################################################
@dataclass
class OrchestratorSysConfig:
    program_name: str           # orchestrator program name
    cli_cmd: List[str]          # command line args when starting program
    config_file: str            # config file name, contains orchestrator system config, ie: contents of this dataclass
    tasks_file: str             # tasks file name, contains user tasks to be performed:
                                #   task_id, task_status, subproc_id, task_params_file, task_params
    health_file: str            # subprocess health file name, contains subprocesses status:
                                #   subproc_id, subproc_status, subproc_errors
    status_file: str            # app status file name, contains overall app status reports
                                # app refers to the whole setup, includes: orchestrator, all subprocesses, all config/params/data files
    error_log_file: str         # app error log
    program_path: str = "./"    # path to orchestrator executable
    config_path: str = "./"     # path to orchestrator config file
    tasks_path: str = "./"      # path to tasks file
    health_path: str = "./"     # path to health file
    status_path: str = "./"     # path to status file
    error_log_path: str = "./"  # path to error log
    last_read_config: datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    last_read_tasks: datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    last_read_health: datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    last_read_status: datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    loop_interval: float = 10.0 # seconds between loop iterations
    log_level: str = "INFO"     # app logging level


##########################################################
# combined orchestrator config                           #
# includes both system and biz logic configs             #
##########################################################
@dataclass
class OrchestratorConfig:
    program_name: str   # orchestrator program name, identical to sys.program_name
    sys: OrchestratorSysConfig
    biz: OrchestratorBizConfig


##########################################################
# user task                                              #
#                                                        #
##########################################################
@dataclass
class UserTask:
    task_id: str
    task_status: str
    subproc_id: str
    task_params_file: str = ""  # params file name and path
    task_params: List[str] = []


# orchestrator functionality ____________________________________________________________
##########################################################
# orchestrator biz logic functionality                   #
# modify/customize as needed                             #
##########################################################
class OrchestratorBizLogic:
    pass


##########################################################
# generic orchestrator system functionality              #
# pertains to subprocess orchestration, no biz logic     #
##########################################################
class OrchestratorSysLogic:
    def __init__(self):
        self.config: OrchestratorConfig
        self.configs: Dict[str, SubprocConfig] = {}
        self.user_tasks: Dict[str, UserTask] = {}
        self.processes: Dict[str, asyncio.subprocess.Process] = {}
        self.restart_counts: Dict[str, int] = {}
        self.failure_counts: Dict[str, int] = {}      # for health checks
        self.running = True
        self.background_tasks: List[asyncio.Task] = []

    async def read_config(self):
        # read orchestrator config file

        # check if config file exists, if not, create with default values
        cfg_file = Path(self.config.sys.config_path).joinpath(Path(self.config.sys.config_file))
        if not cfg_file.is_file():
            await self.default_config() # note this does update "self.config.sys.config_path" and "self.config.sys.config_file"
            cfg_file = Path(self.config.sys.config_path).joinpath(Path(self.config.sys.config_file)) # read config file path again

        # check if parameters need to be updated
        mtime = cfg_file.stat().st_mtime   # get last modified timestamp (float seconds since epoch)
        last_modified = datetime.fromtimestamp(mtime)   # convert to datetime object (local time)
        if self.config.sys.last_read_config < last_modified:
            # read config file and set parameters
            # open() and json.load() are both synchronous/blocking, but they are fast, typically < 1-5 ms, if the config file < 1MB
            # also this config file read is done infrequently: once at startup and then only when modified
            with open(cfg_file, "r", encoding="utf-8") as f:
                config_json = json.load(f)
            
            self.config.sys.program_name = config_json["program_name"]
            self.config.sys.cli_cmd = config_json["cli_cmd"]
            self.config.sys.config_file = config_json["config_file"]
            self.config.sys.tasks_file = config_json["tasks_file"]
            self.config.sys.health_file = config_json["health_file"]
            self.config.sys.status_file = config_json["status_file"]
            self.config.sys.error_log_file = config_json["error_log_file"]

            self.config.sys.program_path = config_json["program_path"]
            self.config.sys.config_path = config_json["config_path"]
            self.config.sys.tasks_path = config_json["tasks_path"]
            self.config.sys.health_path = config_json["health_path"]
            self.config.sys.status_path = config_json["status_path"]
            self.config.sys.error_log_path = config_json["error_log_path"]

            self.config.sys.loop_interval = config_json["loop_interval"]
            self.config.sys.log_level = config_json["log_level"]

            self.config.sys.last_read_config = datetime.now()

    async def read_tasks(self):
        # read user tasks file
        
        # check if tasks file exists, if not, create with default values
        tasks_file = Path(self.config.sys.tasks_path).joinpath(Path(self.config.sys.tasks_file))
        if not tasks_file.is_file():
            await self.default_tasks()

        # check if user tasks need to be updated
        mtime = tasks_file.stat().st_mtime   # get last modified timestamp (float seconds since epoch)
        last_modified = datetime.fromtimestamp(mtime)   # convert to datetime object (local time)
        if self.config.sys.last_read_tasks < last_modified:
            # read tasks file
            # open() and json.load() are both synchronous/blocking, but they are fast, typically < 1-5 ms, if the config file < 1MB
            # also this config file read is done infrequently: once at startup and then only when modified
            with open(tasks_file, "r", encoding="utf-8") as f:
                tasks_json = json.load(f)
            
            # task_id, task_status, subproc_id, task_params_file, task_params
            for task_id in tasks_json:
                task = tasks_json[task_id]
                self.user_tasks[task_id] = UserTask(
                    task_id=task["task_id"],
                    task_status=task["task_status"],
                    subproc_id=task["subproc_id"],
                    task_params_file=task["task_params_file"],
                    task_params=task["task_params"],
                )

            self.config.sys.last_read_tasks = datetime.now()

    async def read_health(self):
        pass

    async def read_status(self):
        pass
    
    async def write_config(self, msg: str):
        pass

    async def write_tasks(self, msg: str):
        pass

    async def write_health(self, msg: str):
        pass

    async def write_status(self, msg: str):
        pass

    async def write_error_log(self, msg: str):
        pass

    async def default_config(self):
        pass

    async def default_tasks(self):
        pass

    async def start_all(self):
        for name, cfg in self.configs.items():
            await self._start_process(name, cfg)
        logger.info(f"Orchestrator started {len(self.configs)} processes")

    async def _start_process(self, name: str, cfg: SubprocConfig):
        if not cfg.sys.restart:
            return
        try:
            proc = await asyncio.create_subprocess_exec(
                *cfg.sys.cli_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.processes[name] = proc
            self.restart_counts[name] = 0
            self.failure_counts[name] = 0
            logger.info(f"Started {name} (PID {proc.pid})")

            # Core monitoring tasks
            self.background_tasks.extend([
                asyncio.create_task(self._monitor_process(name)),
                asyncio.create_task(self._log_output(name, proc.stdout, "stdout")),
                asyncio.create_task(self._log_output(name, proc.stderr, "stderr")),
            ])

            # Health check task (only if configured)
            if cfg.sys.health_url and cfg.sys.health_interval > 0.0:
                self.background_tasks.append(asyncio.create_task(self._health_monitor(name)))

        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")

    async def _log_output(self, name: str, stream, prefix: str):
        if not stream:
            return
        async for line in stream:
            if line := line.decode().rstrip():
                logger.info(f"[{name}] {prefix}: {line}")

    async def _monitor_process(self, name: str):
        """Monitor process exit and handle restarts."""
        cfg = self.configs[name]
        while self.running:
            proc = self.processes.get(name)
            if proc is None:
                break

            try:
                returncode = await proc.wait()
                logger.warning(f"{name} exited with code {returncode}")

                if not self.running or not cfg.sys.restart:
                    break

                await self._handle_restart(name, cfg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error for {name}: {e}")

    async def _health_monitor(self, name: str):
        """Periodically ping the health endpoint."""
        cfg = self.configs[name]

        # exit if not configured
        if isinstance(cfg.sys.health_url, str) == False or isinstance(cfg.sys.health_timeout, float) == False:
            return
        else:
            assert cfg.sys.health_url is str
            assert cfg.sys.health_timeout is float
            
        connector = aiohttp.TCPConnector(limit=10)

        async with aiohttp.ClientSession(connector=connector) as session:
            while self.running:
                await asyncio.sleep(cfg.sys.health_interval)

                if name not in self.processes:
                    continue

                try:
                    async with session.get(
                        cfg.sys.health_url,
                        timeout=cfg.sys.health_timeout
                    ) as resp:
                        if resp.status == 200:
                            self.failure_counts[name] = 0
                            logger.debug(f"Health check passed for {name}")
                            continue
                except (aiohttp.ClientError, asyncio.TimeoutError, Exception) as e:
                    pass  # treat any error as failure

                # Health check failed
                self.failure_counts[name] = self.failure_counts.get(name, 0) + 1
                logger.warning(f"Health check failed for {name} ({self.failure_counts[name]}/{cfg.sys.max_consecutive_failures})")

                if self.failure_counts[name] >= cfg.sys.max_consecutive_failures:
                    logger.error(f"{name} failed health checks consecutively → restarting")
                    await self._restart_process(name, cfg)
                    self.failure_counts[name] = 0

    async def _restart_process(self, name: str, cfg: SubprocConfig):
        """Kill current process and start a new one."""
        if name in self.processes:
            proc = self.processes[name]
            if proc.returncode is None:
                try:
                    proc.kill()  # or .terminate() for graceful
                except ProcessLookupError:
                    pass
            self.processes.pop(name, None)

        await self._start_process(name, cfg)

    async def _handle_restart(self, name: str, cfg: SubprocConfig):
        self.restart_counts[name] = self.restart_counts.get(name, 0) + 1
        if self.restart_counts[name] > cfg.sys.max_restarts:
            logger.error(f"{name} exceeded max restarts. Not restarting.")
            cfg.sys.restart = False
            return

        backoff = cfg.sys.backoff_base ** self.restart_counts[name]
        logger.info(f"Restarting {name} in {backoff:.1f}s (attempt {self.restart_counts[name]})")
        await asyncio.sleep(backoff)
        await self._start_process(name, cfg)

    async def stop_all(self, timeout: float = 10.0):
        self.running = False
        logger.info("Shutting down orchestrator...")

        for task in self.background_tasks:
            task.cancel()

        # Graceful termination
        for name, proc in list(self.processes.items()):
            if proc.returncode is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *(p.wait() for p in self.processes.values() if p.returncode is None),
                    return_exceptions=True
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Some processes did not exit in time — forcing kill")
            for proc in self.processes.values():
                if proc.returncode is None:
                    proc.kill()

        logger.info("All processes stopped.")

    async def run_forever(self):
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(self._handle_shutdown(s)))
            except NotImplementedError:
                pass

        await self.start_all()

        try:
            while self.running:
                await asyncio.sleep(10)
        finally:
            await self.stop_all()

    async def _handle_shutdown(self, sig):
        logger.info(f"Received {sig.name} — shutting down")
        await self.stop_all()


##########################################################
# combined orchestrator functionality                    #
# includes both system and biz logic functionality       #
##########################################################
class SubprocessOrchestrator:
    program_name: str
    sys: OrchestratorSysLogic
    biz: OrchestratorBizLogic


# ====================== EXAMPLE USAGE ======================

async def main():
    config = OrchestratorConfig(
        program_name="orchestrator",
        sys=OrchestratorSysConfig(
            program_name="orchestrator",
            cli_cmd=["python", "orchestrator.py"],
            config_file="orchestrator_config.json",
            tasks_file="orchestrator_tasks.json",
            health_file="orchestrator_health.json",
            status_file="orchestrator_status.json",
            error_log_file="orchestrator_error.log",
            loop_interval=10.0,
            log_level="INFO"
        ),
        biz=OrchestratorBizConfig(
            params_file="orchestrator_params.json",
            input_data_file="orchestrator_input_data.json",
            output_data_file="orchestrator_output_data.json"
        )
    )
    configs = [
        SubprocConfig(
            program_name="api-worker",
            sys=SubprocSysConfig(
                program_name="api-worker",
                cli_cmd=[sys.executable, "api_worker.py"],
                config_file="api_worker_config.json",
                #restart=True,
                #max_restarts=5,
                #backoff_base=2.0,
                #loop_interval=10.0,
                #jitter=False,
                #log_level="INFO",
                health_url="http://127.0.0.1:8000/health",
                health_interval=0.0,    # health checks disabled
                health_timeout=5.0,
                max_consecutive_failures=3
            ),
            biz=SubprocBizConfig(
                params_file="api_worker_params.json",
                input_data_file="api_worker_input_data.json",
                output_data_file="api_worker_output_data.json"
            )
        ),
        SubprocConfig(
            program_name="playwright-scraper",
            sys=SubprocSysConfig(
                program_name="playwright-scraper",
                cli_cmd=[sys.executable, "playwright_scraper.py"],
                config_file="playwright_scraper_config.json",
                #restart=True,
                #max_restarts=5,
                #backoff_base=2.0,
                loop_interval=60.0,
                jitter=True,
                #log_level="INFO",
                #health_url="http://127.0.0.1:8000/health",
                health_interval=0.0,    # health checks disabled
                #health_timeout=5.0,
                #max_consecutive_failures=3
            ),
            biz=SubprocBizConfig(
                params_file="playwright_scraper_params.json",
                input_data_file="playwright_scraper_input_data.json",
                output_data_file="playwright_scraper_output_data.json"
            )
        ),
        SubprocConfig(
            program_name="background-job",
            sys=SubprocSysConfig(
                program_name="background-job",
                cli_cmd=[sys.executable, "background_job.py"],
                config_file="background_job_config.json",
                #restart=True,
                #max_restarts=5,
                #backoff_base=2.0,
                loop_interval=60.0,
                #jitter=False,
                #log_level="INFO",
                #health_url="http://127.0.0.1:8000/health",
                health_interval=0.0,    # health checks disabled
                #health_timeout=5.0,
                #max_consecutive_failures=3
            ),
            biz=SubprocBizConfig(
                params_file="background_job_params.json",
                input_data_file="background_job_input_data.json",
                output_data_file="background_job_output_data.json"
            )
        )
    ]

    orchestrator = SubprocessOrchestrator()
    orchestrator.program_name = config.sys.program_name
    #orchestrator.sys = OrchestratorSysLogic(config, configs)
    orchestrator.sys = OrchestratorSysLogic()
    orchestrator.biz = OrchestratorBizLogic()
    await orchestrator.sys.run_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Orchestrator stopped by user")