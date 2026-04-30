#!/usr/bin/env python3
"""
name:       ticket_search_bot.py
brief desc: KTMB website ticket search bot

author:     mighty_hotdog
created:    11Apr2026
modified:   25Apr2026
desc:       continuous process, once started runs until terminated by error or user command.
            based on search parameters, monitors KTMB website for available tickets.
            notifies upon tickets found.
"""

import asyncio
import logging
import signal
import sys
import os
import random
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from pathlib import Path
from typing import Any, Literal, Optional

import tomllib
import tomli_w      # pip install tomli-w
import tempfile
import shutil
import subprocess
import orjson     # pip install orjson
import json
from bs4 import BeautifulSoup   # pip install beautifulsoup4

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import keyring





# ────────────────────────────────────────────────
#   TICKET SEARCH BOT FUNCTIONALITY
#   custom functionality: edit as needed
# ────────────────────────────────────────────────

# Ticket Search Parameters class
@dataclass
class SearchParams:
    params_file: Path
    sample_request_file: Path
    output_file: Path
    url: str
    frequency: int
    jitter: bool
    from_station: str
    to_station: str
    departure_date: date
    departure_time_from: time
    departure_time_to: time
    num_tickets: int
    alert_sender_email: str
    alert_recipient_email: str
    notify: bool
    last_notify: datetime

    def __init__(self):
        self.default()

    def load(self, path: Optional[Path] = None) -> bool:
        # loads params into memory from path, or from stored path if no path specified
        # returns True if params changed, False if not
        params_path: Optional[Path] = None
        if path is not None and path.is_file():                     # if arg is valid params file path, try to open and load
            params_path = path
        elif self.params_file is not None and self.params_file.is_file():   # if stored parameter is valid params file path, try to open and load
            params_path = self.params_file
        else:                                                       # if neither is valid, load from default
            self.default()
            return True
        
        try:
            with open(params_path, "rb") as f:
                data = tomllib.load(f)
                #f.close()      # not needed as the context manager closes the file automatically in the next line right after the with block
                                # this is however NEEDED for tempfile.NamedTemporaryFile() esp on Windows after writing
            changed = False
            for key, value in data.items():
                if not hasattr(self, key):  # ignore unknown keys
                    continue
                if value is None:   # ignore None values
                    continue
                if value == self.__dict__[key]:    # ignore values that are already set
                    continue
                setattr(self, key, value)   # set attribute to value from config file
                changed = True
            return changed
        except tomllib.TOMLDecodeError as e:
            logger.error(f"TOML parse error reading {params_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading search params from {params_path}: {e}")
            raise

    def save(self, path: Optional[Path] = None) -> bool:
        # saves params from memory to path, or to stored path if no path specified
        # returns True if successful, False if not
        params_path: Optional[Path] = None
        if path is not None:
            params_path = path
        elif self.params_file is not None:
            params_path = self.params_file
        else:
            logger.error("Save search params failed: No valid file path specified")
            return False

        try:
            # ensure parent directory exists
            params_path.parent.mkdir(parents=True, exist_ok=True)
            
            # safe write: write to temp file then rename
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".tmp", dir=params_path.parent, delete=False) as tmp:
                tomli_w.dump(self.__dict__, tmp)
                tmp.flush()
                tmp.close()
            shutil.move(tmp.name, params_path)

            # update path in memory
            self.params_file = params_path
            return True
        except Exception as e:
            logger.error(f"Error saving search params to {params_path}: {e}")
            # clear up temp file if exists
            if 'tmp' in locals() and Path(tmp.name).exists():
                Path(tmp.name).unlink(missing_ok=True)
            raise

    def default(self) -> None:
        # loads default param values
        self.params_file = Path(f"./date/{os.getpid()}_params.json")
        self.sample_request_file = Path("./date/sample_request_data.json")
        self.output_file = Path(f"./date/{os.getpid()}_output.json")
        self.frequency = 60     # 60 seconds interval between queries
        self.jitter = True
        self.url = "https://shuttleonline.ktmb.com.my/Home/Shuttle"
        self.from_station = "JB Sentral"
        self.to_station = "Woodlands CIQ"
        self.departure_date = datetime.now().date()
        self.departure_time_from = datetime.strptime("05:00:00", "%H:%M:%S").time()
        self.departure_time_to = datetime.strptime("23:00:00", "%H:%M:%S").time()
        self.num_tickets = 1
        self.alert_sender_email = "TheGoldenHorde75@gmail.com"
        self.alert_recipient_email = "saracen75@gmail.com"
        self.notify = True
        self.last_notify = datetime.fromisoformat("1900-01-01 05:00:00")


# Ticket Search Bot class
class TicketSearchBot:
    params: SearchParams = SearchParams()
    query_string: list[str] = []

    async def update_params(self) -> bool:
        # loads search params from file
        # if params changed, save new params and return True, if not return False
        if self.params.load() and self.params.save():
            return True
        return False

    async def default_params(self) -> None:
        # sets search params to default
        self.params.default()

    async def recapture_sample_request(self) -> bool:
        # recapture sample request data
        cmd_string = ["python3", "capture_request_ktmb.py"]
        logger.info("Recapturing sample request...")
        logger.debug(f"Sending sample request: from {self.params.from_station} to {self.params.to_station}")
        
        try:
            result = subprocess.run(
                cmd_string,
                capture_output=True,
                text=True,
                timeout=25           # important – prevent hanging forever
            )
        except subprocess.TimeoutExpired:
            logger.error("→ TIMEOUT")
            return False
        except Exception as e:
            logger.error(f"→ RECAPTURE SAMPLE REQUEST FAILED: {e}")
            return False

        # check if recapture successful by:
        #   (1) visually inspecting dump file data, and
        raw = result.stdout.strip()
        logger.info(raw)

        #   (2) checking dump file modification time is very recent, ie: less than 5 seconds ago
        file = self.params.sample_request_file
        if file.is_file():
            mtime = file.stat().st_mtime   # Get the last modification timestamp (float seconds since epoch)
            last_modified = datetime.fromtimestamp(mtime)   # Convert to datetime object (local time)
            if (datetime.now() - timedelta(seconds=5)) < last_modified < datetime.now():
                logger.info("Recapture successful")
                return True
            
        logger.error("Recapture failed")
        return False

    async def construct_query(self) -> list[str]:
        # construct request using sample request data as base template and merging in search parameters
        # returns newly constructed request

        # read sample request data from file
        file = self.params.sample_request_file
        try:
            if file.is_file() or await self.recapture_sample_request():
                sample_request = orjson.loads(file.read_bytes())
            else:
                logger.error("Construct query failed")
                return []
        except orjson.JSONDecodeError as e:
            logger.error(f"JSON parse error reading {file}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading sample request data from {file}: {e}")
            raise

        # build the curl request
        query = ["curl"]
        query.append(sample_request["url"])
        
        sample_request.pop("url", None)
        sample_request.pop("from_station", None)
        sample_request.pop("to_station", None)
        SearchData = sample_request.pop("SearchData")
        FormValidationCode = sample_request.pop("FormValidationCode")
        sample_request.pop("DepartDate")
        IsReturn = sample_request.pop("IsReturn")
        BookingTripSequenceNo = sample_request.pop("BookingTripSequenceNo")

        for key, value in sample_request.items():
            if key == 'cookie':
                query.append('-b')
                query.append(f'{value}')
                continue
            elif key == 'accept-encoding':
                query.append('-H')
                query.append(f'{key}: utf-8, {value}')
                continue
            query.append('-H')
            query.append(f'{key}: {value}')
        
        query.append("--data-raw")
        str = '{\"SearchData\":'
        str += f'\"{SearchData}\",'
        str += '\"FormValidationCode\":'
        str += f'\"{FormValidationCode}\",'
        str += '\"DepartDate\":'
        str += f'\"{self.params.departure_date}\",'
        str += '\"IsReturn\":'
        if not IsReturn:
            str += 'false,'
        str += '\"BookingTripSequenceNo\":'
        str += f'{BookingTripSequenceNo}'
        str += '}'
        query.append(f"{str}")

        # update query string
        self.query_string = query

        logger.info(f"New CURL command constructed successfully")
        logger.debug(f"New CURL command constructed:\n{query}\n")
        return query

    async def send_query(self,query):
        # send request to target server and returns response

        logger.info(f"Sending request: from {self.params.from_station} to {self.params.to_station} / departure {self.params.departure_date} {self.params.departure_time_from} - {self.params.departure_time_to} / number of tickets {self.params.num_tickets}")

        try:
            logger.debug(f"Running CURL command:\n {query}\n")
            result = subprocess.run(
                query,
                capture_output=True,
                text=True,
                timeout=25           # important – prevent hanging forever
            )
        except subprocess.TimeoutExpired:
            logger.error("→ TIMEOUT")
            return None
        except Exception as e:
            logger.error(f"→ SEND QUERY FAILED: {e}")
            return None

        raw = result.stdout.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error reading {raw}: {e}")
            return None
        except Exception as e:
            logger.error(f"Parse error reading {raw}: {e}")
            return None

        status = parsed['status']
        messages = parsed['messages']
        messagecode = parsed['messageCode']
        response_body = parsed.get('data')

        logger.info(f"Received website response: status {result.returncode} / response_status {status} / messages {messages} / message_code {messagecode}")
        if response_body is None:
            logger.warning("Response body is empty")
        truncated_data = response_body#[0:254]
        logger.debug(truncated_data)
        
        return response_body

    async def check_ticket_availability(self, response) -> bool:
        # process response to check for available tickets

        # parse data into beautiful soup
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
        except UnicodeDecodeError as e:
            logger.error(f"→ Unicode parse error reading {response.content}: {e}")
            return False
        except Exception as e:
            logger.error(f"→ Parse error reading {response.content}: {e}")
            return False

        # verify response date is correct
        response_date_el = soup.find("th", class_="dayActive")
        if response_date_el:
            response_date_string = f"{response_date_el["data-departdate"]}"
            response_date = datetime.strptime(response_date_string, "%d %b %Y").date()
            if response_date != self.params.departure_date:
                logger.error(f"→ DATE IS INCORRECT / EXPECTED {self.params.departure_date} / ACTUAL {response_date}. Skipping ticket check...")
                return False
        else:
            logger.error("→ Date extraction from response body failed. Skipping ticket check...")
            return False
        
        # check for available tickets per specified time period
        logger.info("Checking ticket availability...")
        results_string = '{\"depart_date\":'
        results_string += f'\"{response_date_string}\"'
        results_string += '}'

        try:
            results_json = json.loads(results_string)
        except json.JSONDecodeError as e:
            # just log error and exit function skipping rest of ticket check
            logger.error(f"JSON parse error reading {results_string}: {e}")
            return False
        
        for tr in soup.find_all("tr"):
            if "data-hourminute" not in tr.attrs:
                continue
            timeslot_string = f"{tr['data-hourminute']}"
            timeslot = datetime.strptime(timeslot_string, "%H%M").time()
            if self.params.departure_time_from <= timeslot <= self.params.departure_time_to:
                for td in tr.find_all("td"):
                    if "class" in td.attrs:
                        continue
                    numOfTickets = int(td.get_text())
                    if numOfTickets >= self.params.num_tickets:
                        results_json.setdefault(timeslot_string, numOfTickets)
                        logger.info(f"→ {timeslot} HAS AVAILABLE TICKETS = {numOfTickets}")
        
        # if available tickets found, check if output file exists
        if len(results_json) > 1:
            output_path = self.params.output_file
            if not output_path.is_file():
                # output file does not exist: create new file and write to it
                logger.info(f'Writing to new output file: {output_path}')

                try:
                    # ensure parent directory exists
                    output_path.parent.mkdir(parents=True, exist_ok=True)

                    # safe write: write to temp file then rename
                    with tempfile.NamedTemporaryFile(mode="wt", suffix=".tmp", dir=output_path.parent, delete=False) as tmp:
                        json.dump(results_json, tmp, indent=2, ensure_ascii=False)
                        tmp.flush()
                        tmp.close()
                    shutil.move(tmp.name, output_path)
                except Exception as e:
                    # just log error, clear up temp file if exists, and proceed
                    logger.error(f"Error writing output to {output_path}: {e}")
                    # clear up temp file if exists
                    if 'tmp' in locals() and Path(tmp.name).exists():
                        Path(tmp.name).unlink(missing_ok=True)
            else:
                try:
                    # output file exists: check if content is different vs results
                    with open(output_path, "r", encoding="utf-8") as f:
                        old_results_json = json.load(f)
                        #f.close()      # not needed as the context manager closes the file automatically in the next line right after the with block
                                        # this is however NEEDED for tempfile.NamedTemporaryFile() esp on Windows after writing
                except json.JSONDecodeError as e:
                    # just log error and proceed
                    logger.error(f"JSON parse error reading from existing output file {output_path}: {e}")

                if old_results_json != results_json:
                    # different: write results to output file overwriting existing content
                    logger.info(f'Writing to output file: {output_path}')

                    try:
                        # safe write: write to temp file then rename
                        with tempfile.NamedTemporaryFile(mode="wt", suffix=".tmp", dir=output_path.parent, delete=False) as tmp:
                            json.dump(results_json, tmp, indent=2, ensure_ascii=False)
                            tmp.flush()
                            tmp.close()
                        shutil.move(tmp.name, output_path)
                    except Exception as e:
                        # just log error, clear up temp file if exists, and proceed
                        logger.error(f"Error writing output to {output_path}: {e}")
                        # clear up temp file if exists
                        if 'tmp' in locals() and Path(tmp.name).exists():
                            Path(tmp.name).unlink(missing_ok=True)

            return True # available tickets found
        return False    # no available tickets

    async def notify(self):
        # check output result and send notification where appropriate

        # return if self.params.notify is False
        if not self.params.notify:
            return
        
        # check if output file exists
        output_path = self.params.output_file
        if output_path.is_file():
            # check if output file has been modified since last read
            mtime = output_path.stat().st_mtime   # Get the last modification timestamp (float seconds since epoch)
            last_modified = datetime.fromtimestamp(mtime)   # Convert to datetime object (local time)
            if self.params.last_notify < last_modified:
                # send notification
                logger.info("Sending notification...")
                try:
                    with open(output_path, "r", encoding="utf-8") as f:
                        results_json = json.load(f)
                        #f.close()      # not needed as the context manager closes the file automatically in the next line right after the with block
                                        # this is however NEEDED for tempfile.NamedTemporaryFile() esp on Windows after writing
                    results_str = json.dumps(results_json, indent=2, ensure_ascii=False)
                except json.JSONDecodeError as e:
                    # just log error and proceed
                    logger.error(f"Notify failed: JSON parse error reading {output_path}: {e}")
                    return
                except Exception as e:
                    # just log error and proceed
                    logger.error(f"Notify failed: Error reading {output_path}: {e}")
                    return
                
                # update last notification time
                self.params.last_notify = datetime.now()

                # send email
                ####################################################################################################
                # to avoid spamming, turn this on with caution!!
                #await self.send_email(results_str)
                ####################################################################################################

    async def send_email2(self, input_str: str):
        # send email

        try:
            input_json = json.loads(input_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error reading {input_str}: {e}")
            return
        
        if len(input_json) < 2:
            logger.info("No valid info in output. Exiting send_email()...")
            return
        
        # create email
        msg = MIMEMultipart()
        msg["From"] = self.params.alert_sender_email
        msg["To"] = self.params.alert_recipient_email
        msg["Subject"] = "Tickets Available on KTMB"

        # construct email body
        body = "Hello!\n"
        for key in input_json:
            if key == "from_station":
                body += f"\tFrom: {input_json[key]}\n"
                continue
            elif key == "to_station":
                body += f"\tTo: {input_json[key]}\n"
                continue
            elif key == "depart_date":
                body += f"\tDeparture Date: {input_json[key]}\n"
                continue
            body += f"\t{key} available tickets: {input_json[key]}\n"
        msg.attach(MIMEText(body, "plain"))

        # retrieve secret
        secret = keyring.get_password("app_sender_email", "password")

        # Send email
        if secret:
            try:
                with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:   # or use SMTP + starttls()
                    server.login(self.params.alert_sender_email, secret)
                    server.send_message(msg)
                logger.info("Send email successful")
            except Exception as e:
                logger.error(f"Send email failed: {e}")

    async def cleanup(self):
        pass


# ────────────────────────────────────────────────
#   DAEMON SCAFFOLDING
# ────────────────────────────────────────────────

@dataclass
class ProcessConfig:
    name: str = Path(__file__).stem     # name of this process
    pid: int = os.getpid()
    config_file: Path = Path(name).joinpath("_config.toml")     # path to config toml file
    loop_interval: int = 10
    # log levels:
    #   NOTSET = 0    no level set
    #   DEBUG = 10    detailed info, for debugging during development
    #   INFO = 20     confirms program working as expected
    #   WARNING = 30  indicates potential problem or something unexpected occurred, but program still working as expected
    #   ERROR = 40    indicates serious problem or failure
    #   CRITICAL = 50 indicates very serious problem or failure that might require program shutdown
    log_level: Literal[0, 10, 20, 30, 40, 50] = logging.INFO

    def load(self, path: Optional[Path] = None) -> bool:
        # loads config in memory from path, or from stored path if no path specified
        # returns True if config changed, False if not
        config_path: Optional[Path] = None
        if path is not None and path.is_file():                     # if arg is valid config file path, try to open and load
            config_path = path
        elif self.config_file is not None and self.config_file.is_file():   # if stored parameter is valid config file path, try to open and load
            config_path = self.config_file
        else:                                                       # if neither is valid, load from default
            self.default()
            return True
        
        try:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
                #f.close()      # not needed as the context manager closes the file automatically in the next line right after the with block
                                # this is however NEEDED for tempfile.NamedTemporaryFile() esp on Windows after writing
            changed = False
            for key, value in data.items():
                if key == "pid":    # pid shall not be overridden by config file value
                    continue
                if not hasattr(self, key):  # ignore unknown keys
                    continue
                if value is None:   # ignore None values
                    continue
                if value == self.__dict__[key]:    # ignore values that are already set
                    continue
                setattr(self, key, value)   # set attribute to value from config file
                changed = True
            return changed
        except tomllib.TOMLDecodeError as e:
            logger.error(f"TOML parse error reading {config_path}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading proc config from {config_path}: {e}")
            raise

    def save(self, path: Optional[Path] = None) -> bool:
        # saves config in memory to path, or to stored path if no path specified
        # returns True if successful, False if not
        config_path: Optional[Path] = None
        if path is not None:
            config_path = path
        elif self.config_file is not None:
            config_path = self.config_file
        else:
            self.config_file = Path(self.name).joinpath("_config.toml")
            config_path = self.config_file
            #logger.error("Save config failed: No valid file path specified")
            #return False

        try:
            # ensure parent directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)

            # safe write: write to temp file then rename
            with tempfile.NamedTemporaryFile(mode="wb", suffix=".tmp", dir=config_path.parent, delete=False) as tmp:
                tomli_w.dump(self.__dict__, tmp)
                tmp.flush()
                tmp.close()
            shutil.move(tmp.name, config_path)

            # update path in memory
            self.config_file = config_path
            return True
        except Exception as e:
            logger.error(f"Error saving config to {config_path}: {e}")
            # clear up temp file if exists
            if 'tmp' in locals() and Path(tmp.name).exists():
                Path(tmp.name).unlink(missing_ok=True)
            raise

    def default(self) -> None:
        # loads default config values
        self.name = Path(__file__).stem
        self.pid = os.getpid()
        self.config_file = Path(self.name).joinpath("_config.toml")
        self.loop_interval = 10
        self.log_level = logging.INFO


@dataclass
class ProcessState:
    start_time: datetime = datetime.now()
    loop_count: int = 0
    running: bool = True
    success: bool = True


def setup_logging():
    logging.basicConfig(
        level=config.log_level,
        format="[%(levelname)s | %(asctime)s | PID: %(process)d | %(filename)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            #logging.FileHandler("app.log"),    # disable file logging for now
        ]
    )
    logger.info(f"Log level set to {config.log_level}")


def setup_signal_handling():
    loop = asyncio.get_running_loop()
    for sig in signal.valid_signals():
        if sig == signal.SIGINT or sig == signal.SIGTERM:
            logger.info(f"Received {sig.name} — shutting down")
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(handle_shutdown(s)))
        elif sig == signal.SIGHUP:
            logger.info(f"Received {sig.name} — reconfiguring")
            loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(handle_reconfig(s)))


async def handle_shutdown(sig: Optional[signal.Signals] = None):
    sys.exit(0)


async def handle_reconfig(sig: Optional[signal.Signals] = None):
    setup_logging()
    logger.info(f"Loop interval set to {config.loop_interval} seconds")


def update_config() -> bool:
    if config.load() and config.save():
        return True
    return False


def cleanup():
    pass


# ────────────────────────────────────────────────
#   GLOBAL VARIABLES AND DECLARATIONS
# ────────────────────────────────────────────────

# daemon scaffolding
logger = logging.getLogger(__name__)
config = ProcessConfig()
state = ProcessState()

# custom functionality: edit as needed
bot = TicketSearchBot()


# ────────────────────────────────────────────────
#   MAIN WORK
# ────────────────────────────────────────────────

async def main_work():
    # loop interval and jitter for main_work(), not affected by the sleep in main_loop()
    if bot.params.jitter:
        jitter = random.randint(0, 20)
        logger.info("Jitter:", jitter)
        await asyncio.sleep(bot.params.frequency + jitter)

    try:
        query = bot.query_string
        if await bot.update_params() or len(query) == 0:
            query = await bot.construct_query()

        response = await bot.send_query(query)
        if await bot.check_ticket_availability(response):
            await bot.notify()
    except Exception as e:
        logger.error(f"Error: {e}")
        raise

    # return True for successful pass
    return True

# ────────────────────────────────────────────────
#   MAIN LOOP
# ────────────────────────────────────────────────

async def main_loop():
    logger.info("Main process starting up...")
    while state.running:
        state.loop_count += 1
        logger.info(f"Starting loop #{state.loop_count} ----------------------------------------")

        # update process config and handle reconfig
        if update_config():
            await handle_reconfig()

        # do work
        state.success = await main_work()

        # loop interval for main_loop(), not affected by the sleep in main_work()
        await asyncio.sleep(config.loop_interval)



# ────────────────────────────────────────────────
#   ENTRY POINT
# ────────────────────────────────────────────────

async def main():
    setup_logging()
    setup_signal_handling()
    logger.info(f"Loop interval set to {config.loop_interval} seconds")

    try:
        await main_loop()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received")
    except Exception:
        logger.exception("Unexpected top-level exception")
        sys.exit(70)
    finally:
        logger.info("Process stopped | uptime = %s | loops = %s", datetime.now() - state.start_time, state.loop_count)
        cleanup()


# this check ensures that if this file is run as a script, condition is true and main() is called
# but if this file is imported into another file as a module, __name__ is set to the module name, and main() is not called
if __name__ == "__main__":
    asyncio.run(main())





