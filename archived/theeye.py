# monitor script
# monitor.py
import subprocess
import time
import json
import sys
import random
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# search parameters
#DEPARTURE_DATE = datetime.now().strftime("%Y-%m-%d").date()
DEPARTURE_DATE = datetime.now().date()# - timedelta(days=3)
DEPARTURE_TIME_FROM = (datetime.fromisoformat("1900-01-01 05:00:00")).time()
DEPARTURE_TIME_TO = (datetime.fromisoformat("1900-01-01 23:00:00")).time()
NUMBER_OF_TICKETS = 0

# notification parameters
ALERT_EMAIL_ADDRESS = ""

# request parameters
RAW_CURL = ""
CURL_CMD = [
    "curl", #"-s", "-L", "-o", "/dev/null", "-w", "%{http_code}",
    'https://shuttleonline.ktmb.com.my/ShuttleTrip/Trip',
    '-H', 'Accept: application/json, text/javascript, */*; q=0.01',
    '-H', 'Accept-Language: en-US,en;q=0.8',
    '-H', 'Connection: keep-alive',
    '-H', 'Content-Type: application/json',
    '-b', 'X-CSRF-TOKEN-COOKIENAME=CfDJ8LfaBG9SFaNDpEieOEVY5PrmQyeJaJy2SLkE8RVEgN-jwsjVcsVY-fbhhJxQz8kknsFNhmp_sNRWEFh08TQQWGQR0fO-goCk-LXvADPYLz5BaBWQ8G38Gm1EHecOZeNi0fDKKkIgSIKH3IYvW0mEhAQ',
    '-H', 'Origin: https://shuttleonline.ktmb.com.my',
    '-H', 'Referer: https://shuttleonline.ktmb.com.my/ShuttleTrip',
    '-H', 'RequestVerificationToken: CfDJ8LfaBG9SFaNDpEieOEVY5PpmoFXSHLy0NZPtcl868AgrLC3KGPMsMwqkcs_OWGxBJKLxbp9hcf5iWDLUGQK1W-bNElp0QTu8m52Fqu9RT77lMpTx8OBkOK66ABcV5L1pvFTM5N0NKk7Omx_NbgHriz0',
    '-H', 'Sec-Fetch-Dest: empty',
    '-H', 'Sec-Fetch-Mode: cors',
    '-H', 'Sec-Fetch-Site: same-origin',
    '-H', 'Sec-GPC: 1',
    '-H', 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36',
    '-H', 'X-Requested-With: XMLHttpRequest',
    '-H', 'sec-ch-ua: "Chromium";v="146", "Not-A.Brand";v="24", "Brave";v="146"',
    '-H', 'sec-ch-ua-mobile: ?0',
    '-H', 'sec-ch-ua-platform: "Windows"',
    '--data-raw', '{"SearchData":"QMtgKLaS7/pAxo5U9Xe3mI3hB9RhpD67Er7zIeEx51ZcLV9d60OJPIliNlkUYNQu+ST/CBeNtVuYNTssVHcChCAtdWzt828jQJOpxLqBOE6qySFK9sxTerAYdn3TgzztrQ8gHAZ52mRxsKJSiMeW/BUkbX/2gzh10eu3SgFM2TzI/4hVaST7s2qYYj3SQYuU/ogJwiTKBNT8WA38JaEsNaQHQ7N0dB5s3A1keth07Ap2Fq+rs6cDxN3kaWBb7hhEnGXy9VC/OsootRK+LBN0tpaPOpCFoYfaPjyBA6Qwlba5t5NqwY2msaNO+A0uMah88JwmAm7EQ+nIiHIyakIFZVe/7h+oQBeqsk5MrL3S02gl8C4v+jZGfP3Q+5vrq0J57ZyzwmTecZDqjolLs8vbMtECGnCMvDTImBgz9gqxrk08hQyje4Ht1y9TNwX7cpPGcg6wF/3K2gJ1k/fYKF/Cbn2/RbV+vtxHWSgjZodTkXlRnAPLDEkCBXQL6zkbwxEkgHSsFBHiTL1B+gkndCGm/Q==","FormValidationCode":"Whj/MtCgZhL9jVEvNpSd9ZC7o5XkDIErfwp6RcSrCm9CAJ3Y3jt0MX5cQtmwYQmWv7GPy2PKDSmJ3ts43dwlZ5i5LtcwYParMU8Qt8l4ZyuNSlMsQnUjzkmkihm5d5L9hn6xLmoJXjIwI1TsjbiG7w==","DepartDate":"2026-03-20","IsReturn":false,"BookingTripSequenceNo":1}'
]

def check_for_start_stop_flag():
    pass

def read_params():
    pass

def adjust_params():
    global DEPARTURE_DATE
    DEPARTURE_DATE += timedelta(days=1)
    print(f"New departure date: {DEPARTURE_DATE}")
    #str = CURL_CMD.pop()
    #data = json.loads(str)
    #depart_date = datetime.strptime(data["DepartDate"], "%Y-%m-%d")
    #new_depart_date = depart_date + timedelta(days=1)
    #data["DepartDate"] = datetime.strftime(new_depart_date, "%Y-%m-%d")
    #new_str = json.dumps(data).strip()
    #CURL_CMD.append(new_str)

def create_curl_cmd():
    global DEPARTURE_DATE
    global CURL_CMD
    str = CURL_CMD.pop()
    data = json.loads(str)
    #depart_date = datetime.strptime(data["DepartDate"], "%Y-%m-%d")
    #new_depart_date = depart_date + timedelta(days=1)
    data["DepartDate"] = datetime.strftime(DEPARTURE_DATE, "%Y-%m-%d")
    new_str = json.dumps(data).strip()
    CURL_CMD.append(new_str)
    #print(f"Curl command: {CURL_CMD}")
    return CURL_CMD

def send_request():
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Sending request with parameters: departure date {DEPARTURE_DATE} / departure time {DEPARTURE_TIME_FROM} - {DEPARTURE_TIME_TO} / number of tickets {NUMBER_OF_TICKETS}")
    #ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #print(f"[{ts}] Sending request...", end=" ", flush=True)
    
    try:
        result = subprocess.run(
            create_curl_cmd(),
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
        truncated_data = response_body#[0:254]

        print(f"                      Received website response:       status {result.returncode} / response_status {status} / messages {messages} / message_code {messagecode}")
        #print(truncated_data)

        if result.returncode != 0:
            print("→ EXECUTION ERROR")
            sys.exit(1)
        if status != True:
            if messages[0] == "Date has passed.":
                print("→ SERVER RETURNS ERROR: DATE HAS PASSED")
                print("→ ADJUSTING PARAMETERS...")
                adjust_params()
                return None
            else:
                print("→ SERVER RETURNS ERROR:", messages[0])
                print("→ EXITING...")
                sys.exit(1)
        
    except subprocess.TimeoutExpired:
        print("→ TIMEOUT")
    except Exception as e:
        print(f"→ ERROR: {e}")
    
    return response_body

def check_availability(input_data):
    # search for date, departure time, # of tickets
    # verify search date is correct
    soup = BeautifulSoup(input_data, 'html.parser')
    response_date_string = soup.find("th", class_="dayActive")["data-departdate"]
    if response_date_string:
        response_date = datetime.strptime(response_date_string, "%d %b %Y").date()
        if response_date != DEPARTURE_DATE:
            print(f"→ DATE IS INCORRECT / EXPECTED {DEPARTURE_DATE} / ACTUAL {response_date}. Exiting...")
            sys.exit(1)
    else:
        print("→ Date extraction from response body failed. Exiting...")
        sys.exit(1)
    print("Date verified: ", response_date)
    
    # check for available tickets for specified time period
    for tr in soup.find_all("tr"):
        if "data-hourminute" not in tr.attrs:
            continue
        timeslot = datetime.strptime(tr["data-hourminute"], "%H%M").time()
        if DEPARTURE_TIME_FROM <= timeslot <= DEPARTURE_TIME_TO:
            #print("→ Checking timeslot:", timeslot)
            # check for available tickets
            for td in tr.find_all("td"):
                if "class" in td.attrs:
                    continue
                numOfTickets = int(td.get_text())
                if numOfTickets > NUMBER_OF_TICKETS:
                    print(f"→ {timeslot} HAS AVAILABLE TICKETS = {numOfTickets}")

def notify(message):
    pass

# ────────────────────────────────────────
if __name__ == "__main__":
    print("Starting monitor. Ctrl+C to stop.")
    while True:
        data = send_request()
        if data is None:
            continue
        check_availability(data)
        notify("Tickets available!")
        time.sleep(60 + random.randint(0, 10))  # 60 + random seconds