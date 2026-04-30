#!/usr/bin/env python3
"""
name:       orchestrator_bot.py
brief desc: orchestrator service for ticket search bots

author:     mighty_hotdog
created:    05Apr2026
modified:   07Apr2026
desc:       orchestrator process for controlling/managing subprocesses that perform ticket searches on the KTMB website.
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional
import asyncio
import json


# ────────────────────────────────────────────────
#   ENTRY POINT
# ────────────────────────────────────────────────

def main():
    setup_logging()

    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception:
        logger.exception("Unexpected top-level exception")
        sys.exit(70)
    finally:
        logger.info(f"Main process {__name__} stopped")


if __name__ == "__main__":
    main()


# ────────────────────────────────────────────────
#   MAIN LOOP
# ────────────────────────────────────────────────

async def main_loop():
    logger.info("Main process starting up...")
    await initialize()

    while state.running and state.success:
        state.loop_count += 1
        logger.info(f"Starting loop #{state.loop_count} ----------------------------------------")

        # do work
        state.success = await main_work()
        await asyncio.sleep(app_config.loop_interval)


# ────────────────────────────────────────────────
#   MAIN WORK
# ────────────────────────────────────────────────

async def main_work():
    await read_config()
    changed = await read_tasks()
    if changed:
        await handle_tasks()
    await update_state()

    # return True for successful pass, False for failure
    return True


# ────────────────────────────────────────────────
#   FUNCTIONS
# ────────────────────────────────────────────────

# setup logging for entire app
def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s | %(asctime)s | PID: %(process)d | %(filename)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # logging.FileHandler("app.log"),   # disable file logging for now
        ]
    )


# initialize app
async def initialize():
    logger.info("Initializing...")

    # check for workspace directories and files, if not present, create

    # NOT NEEDED, already done in read_config() and read_tasks() in main_work()
    """
    # check if config file exists, if not create with default values
    config_file_path = Path(app_config.config_path).joinpath(Path(app_config.config_file))
    if not config_file_path.is_file():
        config_file_path = await default_config()

    # read config file and load parameters
    await read_config()

    # check if user tasks file exists, if not create with default values
    tasks_file_path = Path(app_config.tasks_path).joinpath(Path(app_config.tasks_file))
    if not tasks_file_path.is_file():
        tasks_file_path = await default_tasks()
    """

    logger.info("Initialization complete")


# read config
async def read_config():
    # check if config file exists, if not, create with default values
    cfg_file = Path(app_config.config_path).joinpath(Path(app_config.config_file))
    if not cfg_file.is_file():
        cfg_file = await default_config()

    # check if config file changed since last read
    mtime = cfg_file.stat().st_mtime   # Get the last modification timestamp (float seconds since epoch)
    last_modified = datetime.fromtimestamp(mtime)   # Convert to datetime object (local time)
    if app_config.last_read_config < last_modified:
        # open config file and load parameters directly to in-memory config object
        with open(cfg_file, "r", encoding="utf-8") as f:
            global app_config
            app_config = json.load(f)

        # update last read time for config file
        app_config.last_read_config = datetime.now()
        
        # return True if config updated
        return True

    # return False if config not updated
    return False


# read user tasks
async def read_tasks():
    # check if tasks file exists, if not, create with default values
    tasks_file = Path(app_config.tasks_path).joinpath(Path(app_config.tasks_file))
    if not tasks_file.is_file():
        tasks_file = await default_tasks()

    # check if tasks file changed since last read
    mtime = tasks_file.stat().st_mtime   # get last modified timestamp (float seconds since epoch)
    last_modified = datetime.fromtimestamp(mtime)   # convert to datetime object (local time)
    if app_config.last_read_tasks < last_modified:
        # open tasks file and load tasks directly to in-memory tasks object
        with open(tasks_file, "r", encoding="utf-8") as f:
            user_tasks_transient = json.load(f)     # note the tasks are read into the transient record NOT the final
                                                    # this facilitates comparison vs the final record in handle_tasks()

        # update last read time for tasks file
        app_config.last_read_tasks = datetime.now()

        # compare with the final record to see if tasks have changed
        if user_tasks_transient != user_tasks_final:
            # return True if tasks changed
            return True

    # return False if tasks unchanged
    return False


async def handle_tasks():
    # compares user_tasks_transient vs user_tasks_final to obtain list of tasks to handle
    # overwrites user_tasks_transient with list of tasks to handle, making it the working record for tasks execution
    # executes tasks and updates them in user_tasks_transient accordingly
    # if all tasks executed successfully, overwrites user_tasks_final with the working record in user_tasks_transient
    # updates subprocs states
    
    await _get_tasks_to_handle()
    try:
        success = await _execute_tasks()
    except Exception:
        logger.exception("Unexpected exception: _execute_tasks()")
        sys.exit(70)
    finally:
        logger.info(f"Main process {__name__} stopped")

    if success:
        await _update_subprocs_states()

        # return True for successful pass
        return True

    # return False for failure
    return False


# update state
async def update_state():
    pass


# create config file with default values
async def default_config():
    # overwrite existing or create new config file with default values

    # create config object with default values
    default_path = "./"
    default_datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    cfg = AppConfig(
        program_name = "orchestrator_bot",
        cli_cmd = [sys.executable, "orchestrator_bot.py"],
        config_file = "config.json",
        tasks_file = "tasks.json",
        subprocs_file = "subprocs.json",
        status_file = "status.json",
        log_file = "orchestrator_bot.log",
        program_path = default_path,
        config_path = default_path,
        tasks_path = default_path,
        subprocs_path = default_path,
        status_path = default_path,
        log_path = default_path,
        loop_interval = 10.0,
        log_level = "INFO",
        last_read_config = default_datetime,
        last_read_tasks = default_datetime,
        last_read_subprocs = default_datetime,
        last_read_status = default_datetime,
        notify_file = "notify.json",
        notify_path = default_path,
        last_read_notify = default_datetime
    )

    # serialize config object directly to the config file
    cfg_file = Path(cfg.config_path).joinpath(Path(cfg.config_file))
    cfg_file.parent.mkdir(parents=True, exist_ok=True)  # create parent directories if don't exist
    with open(cfg_file, "w", encoding="utf-8") as f:    # overwrite existing or create new config file
        json.dump(cfg, f, indent=4)

    return cfg_file     # return path to config file


# create tasks file with default values
async def default_tasks():
    # overwrite existing or create new tasks file with 1 single example task

    # create example task
    task = UserTask(
        task_id=101,
        task_status="new",
        subproc_id=None,
        task_params={
            "ENTRY_POINT_URL": "https://shuttleonline.ktmb.com.my/Home/Shuttle",
            "FROM_STATION": "JB Sentral",
            "TO_STATION": "Woodlands CIQ",
            "Departure Date": datetime.now().strftime("%Y-%m-%d"),
            "Departure Time From": "05:00:00",
            "Departure Time To": "23:55:00",
            "Number of Tickets": "1",
            "Alert Email Sender": "TheGoldenHorde75@gmail.com",
            "Alert Email Receiver": "saracen75@gmail.com",
            "Notify": "true",
        },
        task_params_file="",
        task_input_file="",
        task_output_file="",
    )

    # put example task into a Dict[int, UserTask] collection in preparation to be serialized to the tasks file
    tasks: Dict[int, UserTask] = {}
    tasks.setdefault(task.task_id, task)
    
    # serialize collection to the tasks file
    tasks_file = Path(app_config.tasks_path).joinpath(Path(app_config.tasks_file))
    tasks_file.parent.mkdir(parents=True, exist_ok=True)    # create parent directories if don't exist
    with open(tasks_file, "w", encoding="utf-8") as f:      # overwrite existing or create new config file
        json.dump(tasks, f, indent=4)

    return tasks_file     # return path to tasks file


# helper functions for handle_tasks() ###################################
async def _get_tasks_to_handle():
    # compares user_tasks_transient vs user_tasks_final to obtain list of tasks to handle
    # overwrites user_tasks_transient with list of tasks to handle; user_tasks_transient is now the working record for tasks execution
    
    # go through transient record and create list of tasks to handle
    tasks_to_handle: Dict[int, UserTask] = {}
    for task_id in user_tasks_transient:
        
        # INFO: RFC 8259 says keys in a json object should be unique, but doesn't specify what to do if they aren't.
        #       Python's json module uses a standard dictionary under the hood which, since Python 3.7, preserves insertion order.
        #       Repeated assigning to the same key will just overwrite previous values.
        #
        #       Here, user_tasks_transient, which is populated via json.load() from the tasks file, behaves in the same way and
        #       contains only unique task_ids, preserving only the last UserTask object value for each duplicated task_id found in
        #       the tasks file.
        #
        #       Hence tasks_to_handle, which is populated from user_tasks_transient, contains only unique task_ids.
        #
        #       On a related note, user_tasks_final, which is populated from user_tasks_transient via handle_tasks(), also contains
        #       only unique task_ids.
        """
        # ignore tasks already included in tasks to handle
        if tasks_to_handle.get(task_id) is not None:
            continue
        elif user_tasks_transient[task_id].task_status != "executing" and \
        """

        # ignore tasks in transient record with invalid status
        if user_tasks_transient[task_id].task_status != "executing" and \
           user_tasks_transient[task_id].task_status != "new" and \
           user_tasks_transient[task_id].task_status != "changed" and \
           user_tasks_transient[task_id].task_status != "cancelled":
            continue
        # tasks in transient record but not found in final record to be handled as new tasks
        elif task_id not in user_tasks_final:
            tasks_to_handle.setdefault(task_id, user_tasks_transient[task_id])
            tasks_to_handle[task_id].task_status = "new"
        # tasks in transient record with same task_id as in final record but different parameters to be handled as changed tasks
        elif (user_tasks_transient[task_id].task_params != user_tasks_final[task_id].task_params) or \
             (user_tasks_transient[task_id].task_params_file != user_tasks_final[task_id].task_params_file) or \
             (user_tasks_transient[task_id].task_input_file != user_tasks_final[task_id].task_input_file) or \
             (user_tasks_transient[task_id].task_output_file != user_tasks_final[task_id].task_output_file):
            tasks_to_handle.setdefault(task_id, user_tasks_transient[task_id])
            tasks_to_handle[task_id].task_status = "changed"
        else:
            # all other tasks in transient record to be handled as per their values
            tasks_to_handle.setdefault(task_id, user_tasks_transient[task_id])

    # go through final record and add to list of tasks to handle
    for task_id in user_tasks_final:
        # tasks in final record but not found in transient record to be handled as cancelled tasks
        if task_id not in user_tasks_transient:
            tasks_to_handle.setdefault(task_id, user_tasks_final[task_id])
            tasks_to_handle[task_id].task_status = "cancelled"
    
    # overwrite user_tasks_transient with list of tasks to handle; user_tasks_transient is now the working record for tasks execution
    global user_tasks_transient
    user_tasks_transient = tasks_to_handle


async def _execute_tasks():
    # executes tasks as specified in user_tasks_transient and updates them accordingly in user_tasks_transient
    # if all tasks executed successfully, overwrites user_tasks_final with the final working record in user_tasks_transient
    # return True for successful pass, False for failure
    
    # if no tasks to handle, overwrite user_tasks_final and return True for successful pass
    if len(user_tasks_transient) == 0:
        logger.info("No tasks to handle")
        global user_tasks_final
        user_tasks_final = user_tasks_transient
        return True
    
    # loop thru and execute the tasks inside try/except/finally blocks
    for task_id in user_tasks_transient:
        if user_tasks_transient[task_id].task_status == "new":
            # start new subproc to handle task
            # update user_tasks_transient:
            #   1. set task_status to "executing"
            #   2. set subproc_id to new subproc pid
            #   3. set task_params_file to "XXXX_params.json" where XXXX is new subproc_id
            #   4. set task_input_file to "XXXX_input.json" where XXXX is new subproc_id
            #   5. set task_output_file to "XXXX_output.json" where XXXX is new subproc_id
            pass
        elif user_tasks_transient[task_id].task_status == "changed":
            # check if subproc with subproc_id is running, if so, terminate it
            # find and delete existing task_params_file, task_input_file, task_output_file containing subproc_id in their file names
            # start new subproc to handle task
            # update user_tasks_transient:
            #   1. set task_status to "executing"
            #   2. set subproc_id to new subproc pid
            #   3. set task_params_file to "XXXX_params.json" where XXXX is new subproc_id
            #   4. set task_input_file to "XXXX_input.json" where XXXX is new subproc_id
            #   5. set task_output_file to "XXXX_output.json" where XXXX is new subproc_id
            pass
        elif user_tasks_transient[task_id].task_status == "cancelled":
            # check if subproc with subproc_id is running, if so, terminate it
            # find and delete existing task_params_file, task_input_file, task_output_file containing subproc_id in their file names
            # update user_tasks_transient by deleting task
            pass
        elif user_tasks_transient[task_id].task_status == "executing":
            # check if subproc with subproc_id is running, if not:
            #   1. find and delete existing task_params_file, task_input_file, task_output_file containing subproc_id in their file names
            #   2. start new subproc to handle task
            #   3. update user_tasks_transient:
            #       1. set subproc_id to new subproc pid
            #       2. set task_params_file to "XXXX_params.json" where XXXX is new subproc_id
            #       3. set task_input_file to "XXXX_input.json" where XXXX is new subproc_id
            #       4. set task_output_file to "XXXX_output.json" where XXXX is new subproc_id
            # if subproc is running, do nothing
            pass
        else:
            # invalid task_status; update user_tasks_transient by deleting task
            pass

    # all tasks executed successfully:
    #   1. overwrite user_tasks_final with the final tasks execution working record in user_tasks_transient
    #   2. return True for successful pass
    logger.info(f'All {len(user_tasks_transient)} tasks executed successfully')
    global user_tasks_final
    user_tasks_final = user_tasks_transient
    return True


# is there really a need for a separate function for this? or can just fold everything into _execute_tasks()?
async def _update_subprocs_states():
    # 1. for all subprocs in user_tasks_final:
    #   1. check that subproc is running, if not, start new subproc
    #   2. update subprocs file:
    #       1. add subproc entry if not present
    #       2. update subproc_id, subproc_status, subproc_errors
    # 2. finds subprocs in subprocs file that are not in user_tasks_final:
    #    1. terminates them
    #    2. deletes associated task_params_file, task_input_file, task_output_file
    #    3. deletes them from the subprocs file
    pass
##################################################################################


# ────────────────────────────────────────────────
#   CLASSES AND DEFINITIONS
# ────────────────────────────────────────────────

# defines state for the main Orchestrator process
class ProcessState:
    def __init__(self):
        self.process_id: int = os.getpid()
        self.start_time: datetime = datetime.now()
        self.loop_count: int = 0
        self.running: bool = True
        self.success: bool = True
        self.last_error: Optional[str] = None


# defines configuration for the Orchestrator
@dataclass
class AppConfig:
    # INFO: core setup for basic multiproc dynamic orchestrator
    program_name: str = ""      # program name
    cli_cmd: List[str] = []     # command line args when starting program
    config_file: str = ""       # config file name, contains orchestrator system config, ie: contents of this dataclass
    tasks_file: str = ""        # tasks file name, contains user tasks to be performed:
                                #   task_id, task_status, subproc_id, task_params_file, task_params
    subprocs_file: str = ""     # subprocesses file name, contains subprocesses states:
                                #   subproc_id, subproc_status, subproc_errors
    status_file: str = ""       # app status file name, contains overall app status reports
                                # app refers to the whole setup, includes: orchestrator, all subprocesses, all config/params/data/etc files
    log_file: str = ""          # app log
    program_path: str = "./"    # path to executable
    config_path: str = "./"     # path to config file
    tasks_path: str = "./"      # path to tasks file
    subprocs_path: str = "./"   # path to subprocesses file
    status_path: str = "./"     # path to status file
    log_path: str = "./"        # path to log file
    loop_interval: float = 10.0 # seconds between loop iterations
    log_level: str = "INFO"     # app logging level
    last_read_config: datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    last_read_tasks: datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    last_read_subprocs: datetime = datetime.fromisoformat("1900-01-01 05:00:00")
    last_read_status: datetime = datetime.fromisoformat("1900-01-01 05:00:00")

    # INFO: additional setup for notification functionality
    notify_file: str = ""       # notification config file name, contains notification settings
    notify_path: str = "./"     # path to notification config file
    last_read_notify: datetime = datetime.fromisoformat("1900-01-01 05:00:00")


@dataclass
class SubprocConfig:
    program_name: str = ""      # subprocess program name
    cli_cmd: List[str] = []     # command line args when starting subprocess
    config_file: str = ""       # config file name, contains subprocess system config ie: contents of this dataclass
    program_path: str = "./"    # path to subprocess executable
    config_path: str = "./"     # path to subprocess config file
    restart: bool = True        # True: start subprocess on startup + restart on failure
                                # False: subprocess disabled ie: do not start/restart at all
    max_restarts: int = 5       # max number of start/restart attempts; set to 0 to disable restart
    backoff_base: float = 2.0   # base delay between restart attempts, compounds exponentially with each subsequent attempt
    loop_interval: float = 10.0 # subprocess loops every 10 seconds; modify/customize as needed
    jitter: bool = False        # add random jitter to loop iterations; where necessary for eg to evade target system's bot detection
    log_level: str = "INFO"     # subprocess log level


@dataclass
class UserTask:
    task_id: int = 0                    # unique task id; starts at 101 for normal user tasks; set to 0 at task setup
    task_status: str = "setup"          # "executing", "new", "changed", "cancelled", "setup"
                                        # "setup" is special status for tasks in process of being created/defined and not ready for handling
    subproc_id: Optional[int] = None    # subprocess pid
    task_params: Dict[str, str] = {}    # param_name -> param_value
    task_params_file: str = ""          # params file name and path
    task_input_file: str = ""           # input file name and path
    task_output_file: str = ""          # output file name and path


@dataclass
class SubprocState:
    subproc_id: int = 0                 # subprocess pid
    subproc_status: str = "setup"       # "running", "stopped", "failed", "setup"
                                        # "setup" is special status for subprocesses in process of being created/defined and not ready for execution
    subproc_errors: List[str] = []      # list of error messages


@dataclass
class WorkTask:
    id: int = 0                         # unique task id; starts at 101 for normal work tasks; set to 0 at task setup
    status: str = "setup"               # "executing", "new", "done", "cancelled", "setup"
                                        # "setup" is special status for tasks in process of being created/defined and not ready for execution
    action: str = ""                    # "start subproc", "kill subproc", "restart subproc", "change params", what else???
                                        # tasks not ready for execution are set to empty string ""
    task_params: Dict[str, str] = {}    # param_name -> param_value
    task_params_file: str = ""          # params file name and path
    task_input_file: str = ""           # input file name and path
    task_output_file: str = ""          # output file name and path


# ────────────────────────────────────────────────
#   GLOBAL VARIABLES AND DECLARATIONS
# ────────────────────────────────────────────────
logger = logging.getLogger(__name__)
state = ProcessState()
app_config = AppConfig()
subproc_configs: Dict[int, SubprocConfig] = {}  # pid -> SubprocConfig
user_tasks_final: Dict[int, UserTask] = {}      # task_id -> UserTask
user_tasks_transient: Dict[int, UserTask] = {}  # task_id -> UserTask