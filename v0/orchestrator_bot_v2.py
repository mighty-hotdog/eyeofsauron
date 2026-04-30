#!/usr/bin/env python3
"""
Just to be clear, this is NOT working code. It is an attempt at a working prototype that I have abandoned in order to pursue 
a completely different approach: brutal focus on getting the code to work 1st. AFTER that happens, then considerations of 
efficiency, scalability, maintainability, and all these good stuff can be addressed.
"""
"""
name:       orchestrator_bot.py
brief desc: orchestrator service for ticket search bots

author:     mighty_hotdog
created:    02Apr2026
modified:   02Apr2026
desc:       orchestrator process for controlling/managing subprocesses that perform ticket searches on the KTMB website.
            
            long-running process with user-initiated termination via cli, graceful shutdown and logging.
            At startup:
            1. initializes workspace:
               1.1 sets up and begins background logging for info and errors.
               1.2 sets up admin alert, and if "notify" is set, begins sending alerts.
               1.2 creates workspace directories and files.
               1.3 loads orchestrator config params from persistent storage into workspace.
                   (ie: reads orchestrator config file and loads parameters into workspace)
               1.4 loads user tasks from persistent storage into workspace.
                   (ie: reads user tasks file and loads tasks into workspace)
               1.5 creates and schedules work tasks to handle user tasks.
            2. executes work tasks:
               2.1 starts subprocesses to handle user tasks:
                   for each subprocess to be started:
                   2.1.1 starts subprocess logging.
                   2.1.2 starts subprocess itself.
                   2.1.3 starts subprocess monitoring.
               2.2 updates workspace record of work tasks, user tasks and subprocesses health.
            3. updates persistent storage:
               3.1 updates user tasks and subprocesses health into persistent storage.
                   (ie: writes/updates user tasks file and subprocesses health file)
               3.2 creates app status report and appends to persistent storage: app status file.
               3.3 if "persist logs" is set, writes logs and errors to persistent storage: error log file.
               
            At each execution loop (~ every 60 seconds):
                1. ongoing background logging and alerting as per settings.
                2. updates orchestrator config.
                   2.1 checks if orchestrator config file has changed, and if yes, reads file and reloads parameters.
                       (parameters take effect at next execution loop)
                3. updates and handles user tasks.
                   3.1 checks if user tasks file has changed, and if yes, reads file and extracts tasks into temp record.
                   3.2 compares temp record with workspace record of user tasks, look for:
                       2.2.1 deleted/changed tasks.
                       2.2.2 new unassigned tasks.
                   3.3 creates and schedules work tasks to handle user tasks:
                       2.3.1 terminates existing subprocesses for deleted user tasks.
                       2.3.2 terminates and restarts existing subprocesses for changed user tasks.
                       2.3.3 starts new subprocesses and assigns to them the new user tasks.
                   3.4 executes work tasks.
                   3.5 updates workspace record of work tasks, user tasks and subprocesses health.
                4. updates persistent storage:
                   4.1 updates user tasks and subprocesses health into persistent storage.
                   4.2 creates app status report and appends to persistent storage: app status file.
                   4.3 if "persist logs" is set, writes logs and errors to persistent storage: error log file.
"""

"""
OLD STUFF RETAINED HERE FOR EASY REFERENCE

Orchestrator Service for Ticket Search Bots
--------------------------
##################################
##  IMPLEMENTATION INCOMPLETE   ##
##################################

Long-running process with graceful shutdown, logging, and health structure.

At each execution loop (~ every 60 seconds):
    1. checks if config file "config.json" has changed, and if yes, reads file and reloads parameters.
    2. checks on existing bots' health and updates health file: "health.json"
    3. checks if tasks file "tasks.json" has changed, and if yes:
       2.1 reads file and extracts tasks.
       2.2 looks for deleted/changed tasks.
       2.3 looks for new unassigned tasks.
    4. handles each task by:
       3.1 terminating existing bots for deleted tasks.
       3.2 terminating and restarting existing bots for changed tasks.
       3.3 starting new bots and assigning to them the new tasks.
    5. creates status report and appends to status file: "status.json".
    6. logs any critical error and sends alert to admin.

Parameters:
    1. Config file name/path
    2. Tasks file name/path
    3. Health file name/path
    4. Status file name/path
    5. Error log file name/path
    6. Entry point URL
    7. Admin email address
    8. Alert email sender address
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
#   CLASSES AND DEFINITIONS
# ────────────────────────────────────────────────

class ProcessState:
    def __init__(self):
        self.process_id: int = os.getpid()
        self.start_time: datetime = datetime.now()
        self.loop_count: int = 0
        self.running: bool = True
        self.success: bool = True
        self.last_error: Optional[str] = None


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
latest_task_id = 101                            # +1 to get next unused task_id
latest_work_id = 101                            # +1 to get next unused work_id


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

    """
    cfg = AppConfig()
    cfg.program_name = "orchestrator_bot"
    cfg.cli_cmd = [sys.executable, "orchestrator_bot.py"]
    cfg.config_file = "config.json"
    cfg.tasks_file = "tasks.json"
    cfg.subprocs_file = "subprocs.json"
    cfg.status_file = "status.json"
    cfg.log_file = "orchestrator_bot.log"
    cfg.program_path = "./"
    cfg.config_path = "./"
    cfg.tasks_path = "./"
    cfg.subprocs_path = "./"
    cfg.status_path = "./"
    cfg.log_path = "./"
    cfg.loop_interval = 10.0
    cfg.log_level = "INFO"
    cfg.last_read_config = datetime.fromisoformat("1900-01-01 05:00:00")
    cfg.last_read_tasks = datetime.fromisoformat("1900-01-01 05:00:00")
    cfg.last_read_subprocs = datetime.fromisoformat("1900-01-01 05:00:00")
    cfg.last_read_status = datetime.fromisoformat("1900-01-01 05:00:00")
    cfg.notify_file = "notify.json"
    cfg.notify_path = "./"
    cfg.last_read_notify = datetime.fromisoformat("1900-01-01 05:00:00")
    """
    """
    config_str = '{"program_name": "orchestrator_bot", }'
    config_json = json.loads(config_str)
    config_json.setdefault("cli_cmd", [sys.executable, "orchestrator_bot.py"])
    config_json.setdefault("config_file", "config.json")
    config_json.setdefault("tasks_file", "tasks.json")
    config_json.setdefault("subprocs_file", "subprocs.json")
    config_json.setdefault("status_file", "status.json")
    config_json.setdefault("log_file", "orchestrator_bot.log")
    config_json.setdefault("program_path", "./")
    config_json.setdefault("config_path", "./")
    config_json.setdefault("tasks_path", "./")
    config_json.setdefault("subprocs_path", "./")
    config_json.setdefault("status_path", "./")
    config_json.setdefault("log_path", "./")
    config_json.setdefault("loop_interval", 10.0)
    config_json.setdefault("log_level", "INFO")
    config_json.setdefault("last_read_config", datetime.fromisoformat("1900-01-01 05:00:00"))
    config_json.setdefault("last_read_tasks", datetime.fromisoformat("1900-01-01 05:00:00"))
    config_json.setdefault("last_read_subprocs", datetime.fromisoformat("1900-01-01 05:00:00"))
    config_json.setdefault("last_read_status", datetime.fromisoformat("1900-01-01 05:00:00"))
    config_json.setdefault("notify_file", "")
    config_json.setdefault("notify_path", "./")
    config_json.setdefault("last_read_notify", datetime.fromisoformat("1900-01-01 05:00:00"))
    """
    """
    config_str = '{'
    config_str += '"program_name": "orchestrator_bot", '
    config_str += '"cli_cmd": [sys.executable, "orchestrator_bot.py"], '
    config_str += '"config_file": "config.json", '
    config_str += '"tasks_file": "tasks.json", '
    config_str += '"subprocs_file": "subprocs.json", '
    config_str += '"status_file": "status.json", '
    config_str += '"log_file": "orchestrator_bot.log", '
    config_str += '"program_path": "./", '
    config_str += '"config_path": "./", '
    config_str += '"tasks_path": "./", '
    config_str += '"subprocs_path": "./", '
    config_str += '"status_path": "./", '
    config_str += '"log_path": "./", '
    config_str += '"loop_interval": 10.0, '
    config_str += '"log_level": "INFO", '
    config_str += '"last_read_config": "1900-01-01 05:00:00", '
    config_str += '"last_read_tasks": "1900-01-01 05:00:00", '
    config_str += '"last_read_subprocs": "1900-01-01 05:00:00", '
    config_str += '"last_read_status": "1900-01-01 05:00:00" '
    config_str += '}'

    config_json = json.loads(config_str)
    """


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

    """
    tasks_str = '{[101, {'
    tasks_str += '"task_id": 101, '
    tasks_str += '"task_status": "new", '
    tasks_str += '"subproc_id": None, '
    tasks_str += '"task_params": {"ENTRY_POINT_URL": "https://shuttleonline.ktmb.com.my/Home/Shuttle", '
    tasks_str += '"FROM_STATION": "JB Sentral", '
    tasks_str += '"TO_STATION": "Woodlands CIQ", '
    tasks_str += f'\"Departure Date\": \"{datetime.now().strftime("%Y-%m-%d")}\", '
    tasks_str += '"Departure Time From": "05:00:00", '
    tasks_str += '"Departure Time To": "23:55:00", '
    tasks_str += '"Number of Tickets": "1", '
    tasks_str += '"Alert Email Sender": "TheGoldenHorde75@gmail.com", '
    tasks_str += '"Alert Email Receiver": "saracen75@gmail.com", '
    tasks_str += '"Notify": "true", '
    tasks_str += '}'
    tasks_str += '"task_params_file": "", '
    tasks_str += '"task_output_file": "", '
    tasks_str += '}]}'
    tasks_json = json.loads(tasks_str)
    """


# read config file and load params
async def read_config():
    # check if config file exists, if not, create with default values
    cfg_file = Path(app_config.config_path).joinpath(Path(app_config.config_file))
    if not cfg_file.is_file():
        cfg_file = await default_config()

    # check if in-memory config need to be refreshed/updated: last read time vs last modified time
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

    """
    app_config.program_name = config_json["program_name"]
    app_config.cli_cmd = config_json["cli_cmd"]
    app_config.config_file = config_json["config_file"]
    app_config.tasks_file = config_json["tasks_file"]
    app_config.subprocs_file = config_json["subprocs_file"]
    app_config.status_file = config_json["status_file"]
    app_config.log_file = config_json["log_file"]

    app_config.program_path = config_json["program_path"]
    app_config.config_path = config_json["config_path"]
    app_config.tasks_path = config_json["tasks_path"]
    app_config.subprocs_path = config_json["subprocs_path"]
    app_config.status_path = config_json["status_path"]
    app_config.log_path = config_json["log_path"]

    app_config.loop_interval = config_json["loop_interval"]
    app_config.log_level = config_json["log_level"]

    app_config.last_read_config = datetime.now()
    app_config.last_read_tasks = config_json["last_read_tasks"]
    app_config.last_read_subprocs = config_json["last_read_subprocs"]
    app_config.last_read_status = config_json["last_read_status"]

    app_config.notify_file = config_json["notify_file"]
    app_config.notify_path = config_json["notify_path"]
    app_config.last_read_notify = config_json["last_read_notify"]
    """


# read user tasks file and load tasks into transient record
async def read_tasks():
    # check if tasks file exists, if not, create with default values
    tasks_file = Path(app_config.tasks_path).joinpath(Path(app_config.tasks_file))
    if not tasks_file.is_file():
        tasks_file = await default_tasks()

    # check if in-memory tasks need to be refreshed/updated: last read time vs last modified time
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


# internal helper functions for handle_tasks() ###################################
async def _get_tasks_to_handle():
    # compares user_tasks_transient vs user_tasks_final to obtain list of tasks to handle
    # overwrites user_tasks_transient with list of tasks to handle; user_tasks_transient is now the working record for tasks execution

    # INFO: just go thru the for loop and if-else check gauntlet to eliminate tasks with invalid statuses if nothing else
    """
    # if no tasks in the final record, return the transient record wholesale as everything to be handled
    if len(user_tasks_final) == 0:
        return user_tasks_transient
    """
    
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


# update app state
async def update_state():
    pass


# initialize app
async def initialize():
    logger.info("Initializing...")

    # check for workspace directories and files, if not present, create

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

    logger.info("Initialization complete")


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