#!/usr/bin/env python3
"""
Ticket Search Bot (KTMB Shuttle Tebrau)
--------------------------
Long-running process with graceful shutdown, logging, and health structure.

At each execution loop (~ every 60 seconds + a random "jitter"):
    1. checks if config file has changed since last read, if yes:
       1.1 reads file and reloads parameters.
       1.2 performs recapture of sample request data.
       1.3 reconstructs curl request from file: "sample_request_data.json".
    2. sends curl request to KTMB webpage.
    3. parses response to check for available tickets.
    4. if new info found:
       4.1 writes to output file: "output.json", overwriting previous content.
       4.2 if notify flag is set, sends email alert.
    5. logs any critical error and sends alert to admin.    # TODO

Parameters:
    1. From station
    2. To station
    3. Departure date
    4. Departure time from
    5. Departure time to
    6. Number of tickets
    7. Alert email sender address
    8. Alert email receiver address
    9. Notify flag
"""

import logging
import signal
import sys
import time
import os
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path

import json
import orjson
import subprocess
import random
from bs4 import BeautifulSoup

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import keyring

# ────────────────────────────────────────────────
#   CONFIGURATION
# ────────────────────────────────────────────────

SCRIPT_NAME = Path(__file__).stem
LOG_LEVEL    = logging.INFO
LOOP_INTERVAL = 60.0          # seconds

# You can also load from environment variables or config file
# import os
# LOOP_INTERVAL = float(os.getenv("LOOP_INTERVAL", 10))

# parameters obtained from OS or user input
PID = f"{os.getpid()}"

# parameters to be loaded from config file; the following shows startup values
CONFIG_FILE = Path("sample")
REQUEST_DUMP_FILE = Path("sample")
OUTPUT_FILE = Path("sample")
FROM_STATION = ""
TO_STATION = ""
DEPARTURE_DATE = datetime.now().date()
DEPARTURE_TIME_FROM = (datetime.fromisoformat("1900-01-01 05:00:00")).time()
DEPARTURE_TIME_TO = (datetime.fromisoformat("1900-01-01 23:00:00")).time()
NUMBER_OF_TICKETS = 0
ALERT_EMAIL_SENDER = ""
ALERT_EMAIL_RECEIVER = ""
NOTIFY = True

# parameters updated by application during run; the following shows startup values
LAST_CONFIG_READ = datetime.fromisoformat("1900-01-01 05:00:00")
LAST_REQUEST_DUMP_READ = datetime.fromisoformat("1900-01-01 05:00:00")
LAST_NOTIFY = datetime.fromisoformat("1900-01-01 05:00:00")
CURL_CMD = []

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
#   SUPPORTING FUNCTIONS
# ────────────────────────────────────────────────

def reset_default_config():
    # reset parameters to default values

    # general app config
    app_config_string = '{"config_file": '
    app_config_string += f'"./data/{PID}_params.json", '
    app_config_string += '"dump_file": "./data/sample_request_data.json", "output_file": '
    app_config_string += f'"./data/{PID}_output.json"'
    app_config_string += '}'
    #app_config_string = '{"config_file": "./data/config.json", "dump_file": "./data/sample_request_data.json", "output_file": "./data/output.json"}'
    default_config_json = json.loads(app_config_string)

    # url
    default_config_json.setdefault("ENTRY_POINT_URL", "https://shuttleonline.ktmb.com.my/Home/Shuttle")

    # from station
    default_config_json.setdefault("FROM_STATION", "JB Sentral")

    # to station
    default_config_json.setdefault("TO_STATION", "Woodlands CIQ")

    # departure date param
    today = datetime.now().date().strftime("%Y-%m-%d")
    default_config_json.setdefault("Departure Date", today)

    # departure time params
    default_config_json.setdefault("Departure Time From", "05:00:00")
    default_config_json.setdefault("Departure Time To", "23:55:00")

    # number of tickets
    default_config_json.setdefault("Number of Tickets", "1")

    # alert email addresses
    default_config_json.setdefault("Alert Email Sender", "TheGoldenHorde75@gmail.com")
    default_config_json.setdefault("Alert Email Receiver", "saracen75@gmail.com")

    # notify
    default_config_json.setdefault("Notify", "true")

    # write to config file
    path = Path(default_config_json["config_file"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_config_json, f, indent=2, ensure_ascii=False)
    f.close()
    global CONFIG_FILE
    CONFIG_FILE = path
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'[{ts}] New config file created with default values: \"{CONFIG_FILE}\"')

def update_params():
    # read parameters from config file

    # check if config file exists, if not, create with default values
    global CONFIG_FILE
    if CONFIG_FILE.is_file() == False:
        reset_default_config()
    
    # check if parameters need to be updated
    mtime = CONFIG_FILE.stat().st_mtime   # Get the last modification timestamp (float seconds since epoch)
    last_modified = datetime.fromtimestamp(mtime)   # Convert to datetime object (local time)
    global LAST_CONFIG_READ
    if LAST_CONFIG_READ < last_modified:
        # read config file and set parameters
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config_json = json.load(f)
        f.close()
        CONFIG_FILE = Path(config_json["config_file"])
        global REQUEST_DUMP_FILE
        REQUEST_DUMP_FILE = Path(config_json["dump_file"])
        global OUTPUT_FILE
        OUTPUT_FILE = Path(config_json["output_file"])
        global FROM_STATION
        FROM_STATION = config_json["FROM_STATION"]
        global TO_STATION
        TO_STATION = config_json["TO_STATION"]
        global DEPARTURE_DATE
        DEPARTURE_DATE = datetime.strptime(config_json["Departure Date"], "%Y-%m-%d").date()
        global DEPARTURE_TIME_FROM
        DEPARTURE_TIME_FROM = datetime.strptime(config_json["Departure Time From"], "%H:%M:%S").time()
        global DEPARTURE_TIME_TO
        DEPARTURE_TIME_TO = datetime.strptime(config_json["Departure Time To"], "%H:%M:%S").time()
        global NUMBER_OF_TICKETS
        NUMBER_OF_TICKETS = int(config_json["Number of Tickets"])
        global ALERT_EMAIL_SENDER
        ALERT_EMAIL_SENDER = config_json["Alert Email Sender"]
        global ALERT_EMAIL_RECEIVER
        ALERT_EMAIL_RECEIVER = config_json["Alert Email Receiver"]
        global NOTIFY
        if config_json["Notify"] == "true":
            NOTIFY = True
        else:
            NOTIFY = False
        LAST_CONFIG_READ = datetime.now()
        print(f"[{datetime.strftime(LAST_CONFIG_READ, '%Y-%m-%d %H:%M:%S')}] Parameters updated: ")
        print(f"\t\t\tfrom {FROM_STATION} to {TO_STATION}")
        print(f"\t\t\tdeparture {DEPARTURE_DATE} {DEPARTURE_TIME_FROM} - {DEPARTURE_TIME_TO}")
        print(f"\t\t\tnumber of tickets {NUMBER_OF_TICKETS}")
        print(f"\t\t\talert email address {ALERT_EMAIL_RECEIVER}")
        print(f"\t\t\tnotify is {NOTIFY}")
        return True
    else:
        return False

def recapture_request_data():
    # recapture sample request data

    cmd_string = ["python3", "capture_request_ktmb.py"]
    global FROM_STATION
    global TO_STATION
    print("Recapturing sample request...")
    #ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #print(f"[{ts}] Sending sample request: from {FROM_STATION} to {TO_STATION}")
    
    try:
        result = subprocess.run(
            cmd_string,
            capture_output=True,
            text=True,
            timeout=25           # important – prevent hanging forever
        )
        raw = result.stdout.strip()
        print(raw)

        # check if recapture was successful
        global REQUEST_DUMP_FILE
        if REQUEST_DUMP_FILE.is_file():
            mtime = REQUEST_DUMP_FILE.stat().st_mtime   # Get the last modification timestamp (float seconds since epoch)
            last_modified = datetime.fromtimestamp(mtime)   # Convert to datetime object (local time)
            if (datetime.now() - timedelta(seconds=5)) < last_modified < datetime.now():
                print("Recapture successful")
                return True
            else:
                print("Recapture failed")
                return False
        
    except subprocess.TimeoutExpired:
        print("→ TIMEOUT")
    except Exception as e:
        print(f"→ ERROR: {e}")

def construct_request():
    # construct request from base template + other parameters

    # read sample request from dump file
    global REQUEST_DUMP_FILE
    if REQUEST_DUMP_FILE.is_file() or recapture_request_data():
        sample_request = orjson.loads(REQUEST_DUMP_FILE.read_bytes())
    else:
        print("Construct CURL command failed")
        return []

    # build the curl request
    curl_cmd = ["curl"]
    curl_cmd.append(sample_request["url"])
    
    sample_request.pop("url", None)
    sample_request.pop("from_station", None)
    sample_request.pop("to_station", None)
    SearchData = sample_request.pop("SearchData")
    FormValidationCode = sample_request.pop("FormValidationCode")
    DepartDate = sample_request.pop("DepartDate")
    IsReturn = sample_request.pop("IsReturn")
    BookingTripSequenceNo = sample_request.pop("BookingTripSequenceNo")

    for key, value in sample_request.items():
        if key == 'cookie':
            curl_cmd.append('-b')
            curl_cmd.append(f'{value}')
            continue
        elif key == 'accept-encoding':
            curl_cmd.append('-H')
            curl_cmd.append(f'{key}: utf-8, {value}')
            continue
        curl_cmd.append('-H')
        curl_cmd.append(f'{key}: {value}')
    
    curl_cmd.append("--data-raw")
    str = '{\"SearchData\":'
    str += f'\"{SearchData}\",'
    str += '\"FormValidationCode\":'
    str += f'\"{FormValidationCode}\",'
    str += '\"DepartDate\":'
    global DEPARTURE_DATE
    str += f'\"{DEPARTURE_DATE}\",'
    str += '\"IsReturn\":'
    if IsReturn == False:
        str += 'false,'
    str += '\"BookingTripSequenceNo\":'
    str += f'{BookingTripSequenceNo}'
    str += '}'
    curl_cmd.append(f"{str}")

    #print(f"New CURL command constructed:\n{curl_cmd}\n")
    print(f"New CURL command constructed successfully")
    return curl_cmd

def send_request():
    # send request to target server and returns response

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    global FROM_STATION
    global TO_STATION
    global DEPARTURE_DATE
    global DEPARTURE_TIME_FROM
    global DEPARTURE_TIME_TO
    print(f"\n[{ts}] Sending request: from {FROM_STATION} to {TO_STATION} / departure {DEPARTURE_DATE} {DEPARTURE_TIME_FROM} - {DEPARTURE_TIME_TO} / number of tickets {NUMBER_OF_TICKETS}")
    
    try:
        global CURL_CMD
        #print(f"Running CURL command:\n {CURL_CMD}\n")
        result = subprocess.run(
            CURL_CMD,
            capture_output=True,
            text=True,
            timeout=25           # important – prevent hanging forever
        )
        raw = result.stdout.strip()
        parsed = json.loads(raw)

        status = parsed['status']
        messages = parsed['messages']
        messagecode = parsed['messageCode']
        response_body = parsed.get('data')

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Received website response: status {result.returncode} / response_status {status} / messages {messages} / message_code {messagecode}")
        #truncated_data = response_body#[0:254]
        #print(truncated_data)
        
    except subprocess.TimeoutExpired:
        print("→ TIMEOUT")
    except Exception as e:
        print(f"→ ERROR: {e}")
    
    return response_body

def check_availability(input_data):
    # process response to check for available tickets

    soup = BeautifulSoup(input_data, 'html.parser')
    response_date_el = soup.find("th", class_="dayActive")
    if response_date_el:
        response_date_string = f"{response_date_el["data-departdate"]}"
        response_date = datetime.strptime(response_date_string, "%d %b %Y").date()
        global DEPARTURE_DATE
        global DEPARTURE_TIME_FROM
        global DEPARTURE_TIME_TO
        if response_date != DEPARTURE_DATE:
            print(f"→ DATE IS INCORRECT / EXPECTED {DEPARTURE_DATE} / ACTUAL {response_date}. Exiting...")
            sys.exit(1)
        print(f"Checking ticket availability...")
    else:
        print("→ Date extraction from response body failed. Exiting...")
        sys.exit(1)
    
    # check for available tickets for specified time period
    results_string = '{\"depart_date\":'
    results_string += f'\"{response_date_string}\"'
    results_string += '}'
    results_json = json.loads(results_string)
    for tr in soup.find_all("tr"):
        if "data-hourminute" not in tr.attrs:
            continue
        timeslot_string = f"{tr['data-hourminute']}"
        timeslot = datetime.strptime(timeslot_string, "%H%M").time()
        if DEPARTURE_TIME_FROM <= timeslot <= DEPARTURE_TIME_TO:
            for td in tr.find_all("td"):
                if "class" in td.attrs:
                    continue
                numOfTickets = int(td.get_text())
                global NUMBER_OF_TICKETS
                if numOfTickets >= NUMBER_OF_TICKETS:
                    results_json.setdefault(timeslot_string, numOfTickets)
                    print(f"→ {timeslot} HAS AVAILABLE TICKETS = {numOfTickets}")
    if len(results_json) > 1:
        # if output file does not exist, create and write to it
        global OUTPUT_FILE
        if OUTPUT_FILE.is_file() == False:
            print(f'Writing to output file: {OUTPUT_FILE}')
            OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(results_json, f, indent=2, ensure_ascii=False)
            f.close()
        else:
            # if output file exists, check if results are new, if yes write to file
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                old_results_json = json.load(f)
            f.close()
            if old_results_json != results_json:
                # write results to output file, overwriting existing contents
                print(f'Writing to output file: {OUTPUT_FILE}')
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(results_json, f, indent=2, ensure_ascii=False)
                f.close()
        return True # available tickets found
    return False    # no available tickets

def notify():
    # check output result and send notification where appropriate

    # check if NOTIFY is True
    global NOTIFY
    if NOTIFY == False:
        return
    # check if output file exists and/or has been modified since last read
    global OUTPUT_FILE
    if OUTPUT_FILE.is_file() == True:
        mtime = OUTPUT_FILE.stat().st_mtime   # Get the last modification timestamp (float seconds since epoch)
        last_modified = datetime.fromtimestamp(mtime)   # Convert to datetime object (local time)
        global LAST_NOTIFY
        if LAST_NOTIFY < last_modified:
            # send notification
            LAST_NOTIFY = datetime.now()
            print("Sending notification...")
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                results_json = json.load(f)
            f.close()
            ####################################################################################################
            # to avoid spamming, turn this on with caution!!
            #send_email(results_json)
            ####################################################################################################

def send_email(input_json):
    # send email

    if input_json == None or len(input_json) < 3:
        print("No valid info in output. Exiting send_email()...")
        return
    # create email
    msg = MIMEMultipart()
    global ALERT_EMAIL_SENDER
    msg["From"] = ALERT_EMAIL_SENDER
    global ALERT_EMAIL_RECEIVER
    msg["To"] = ALERT_EMAIL_RECEIVER
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
                server.login(ALERT_EMAIL_SENDER, secret)
                server.send_message(msg)
            print("Send email successful")
        except Exception as e:
            print(f"Error: {e}")

# ────────────────────────────────────────────────
#   MAIN WORK
# ────────────────────────────────────────────────

def do_work() -> bool:
    """
    Return True  = work completed successfully
    Return False = temporary error (should retry next loop)
    Raise       = serious error (will be caught & logged)
    """
    try:
        # ── Your actual business logic here ────────────────

        # update parameters if needed
        updated = update_params()
        
        # check if CURL command needs to be updated
        global CURL_CMD
        if len(CURL_CMD) == 0 or updated:
            CURL_CMD = construct_request()
        
        # send request, check availability, notify
        response = send_request()
        found = check_availability(response)
        if found == True:
            notify()
        logger.info(f"Working... (loop #{state.loop_count})")

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
        jitter = random.randint(0, 20)
        print("Jitter:", jitter)
        time.sleep(LOOP_INTERVAL + jitter)

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