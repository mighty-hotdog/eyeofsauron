#!/usr/bin/env python3
"""
Capture Sample Request From KTMB Website
--------------------------
Loads parameters from config file: "config.json".
Loads KTMB webpage for Shuttle Tebrau train tickets.
Setups page to search for:
    1. FROM_STATION to TO_STATION   (according to parameters loaded from config file)
    2. one way trip
    3. today departure
    4. 1 pax
Sends request, then captures the xhr request and writes to dump file 'sample_request_data.json'.

Parameters:
    1. Entry point URL
    2. From station
    3. To station
"""

from playwright.sync_api import sync_playwright, expect

import json
#import orjson
from datetime import datetime
from pathlib import Path

# ────────────────────────────────────────────────
#   CONFIGURATION
# ────────────────────────────────────────────────

SCRIPT_NAME = Path(__file__).stem

# parameters to be loaded from config file; the following shows startup values
CONFIG_FILE = Path("./data/config.json")
REQUEST_DUMP_FILE = Path("sample")
URL = "https://shuttleonline.ktmb.com.my/Home/Shuttle"
FROM_STATION = "JB Sentral"
TO_STATION = "Woodlands CIQ"

# parameters updated by application during run; the following shows startup values
#LAST_CONFIG_READ = datetime.fromisoformat("1900-01-01 05:00:00")
#LAST_REQUEST_DUMP_READ = datetime.fromisoformat("1900-01-01 05:00:00")

# ────────────────────────────────────────────────
#   FUNCTIONS
# ────────────────────────────────────────────────

def reset_default_config():
    # reset parameters to default values

    # general app config
    app_config_string = '{"config_file": "./data/config.json", "dump_file": "./data/sample_request_data.json", "output_file": "./data/output.json"}'
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
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'[{ts}] New config file created with default values: \"{path}\"')

def update_params():
    # load parameters from config file

    # check if config file exists, if not, create with default values
    global CONFIG_FILE
    if CONFIG_FILE.is_file() == False:
        reset_default_config()
    
    # read config file and set parameters
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config_json = json.load(f)
    f.close()
    CONFIG_FILE = Path(config_json["config_file"])
    global REQUEST_DUMP_FILE
    REQUEST_DUMP_FILE = Path(config_json["dump_file"])
    global URL
    URL = config_json["ENTRY_POINT_URL"]
    global FROM_STATION
    FROM_STATION = config_json["FROM_STATION"]
    global TO_STATION
    TO_STATION = config_json["TO_STATION"]

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f'[{ts}] Parameters updated: from station {FROM_STATION} / to station {TO_STATION}')

with sync_playwright() as p:
    update_params()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] Sending sample request: from {FROM_STATION} to {TO_STATION}")
    
    # Pick a device (full list: https://github.com/microsoft/playwright/blob/main/packages/playwright-core/src/server/deviceDescriptorsSource.json)
    #iphone = p.devices['iPhone 14']          # or 'iPhone 13', 'iPhone SE', etc.
    #pixel  = p.devices['Pixel 7']
    #galaxy = p.devices['Galaxy S22']

    #browser = p.chromium.launch(headless=True)  # or p.webkit.launch() for Safari-like
    #context = browser.new_context(**iphone)     # ← this applies mobile emulation
    browser = p.chromium.launch(headless=True)  # headless=True in production
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        # record_har_path="network.har"   # optional: save everything to HAR file
    )
    page = context.new_page()

    # Go to the site & do actions
    page.goto(URL)

    # If maintenance pop-up is present, click to dismiss
    if page.locator('div.modal-content').filter(has_text="System maintenance scheduled").count() > 0:
        page.locator('div.modal-content').filter(has_text="System maintenance scheduled").get_by_role("button", name="OK").click()

    # Check if needed to swap From and To stations
    FromStation = page.locator('input[class="form-control"][name="FromStationId"]').input_value()
    ToStation = page.locator('input[class="form-control"][name="ToStationId"]').input_value()
    if FromStation.lower() == TO_STATION.lower() and ToStation.lower() == FROM_STATION.lower():
        # Click to swap From to To stations + check if swap is successful
        PreFromStationData = page.locator('input[type="hidden"][name="FromStationData"]').input_value()
        PreToStationData = page.locator('input[type="hidden"][name="ToStationData"]').input_value()
        #print(f"From: {FromStation}, Data: {PreFromStationData}")
        #print(f"To: {ToStation}, Data: {PreToStationData}")
        page.locator('i.fa.fa-exchange.web-exchange.mt22[onclick="SwapFromToTerminal()"]').click()
        FromStationData = page.locator('input[type="hidden"][name="FromStationData"]').input_value()
        ToStationData = page.locator('input[type="hidden"][name="ToStationData"]').input_value()
        #print(f"FromStationData: {FromStationData}")
        #print(f"ToStationData: {ToStationData}")
        if FromStationData == PreToStationData and ToStationData == PreFromStationData:
            print("Swap successful")
        else:
            print("Swap failed")
    
    # Click to open date picker for departure date
    page.locator('input[type="text"][name="OnwardDate"]').click()

    # Click to select departure date
    daypicker_el = page.locator('div.lightpick__day.is-available')
    daypicker_el.nth(0).click()

    # Click to select one way trip
    one_way_trip_el = page.locator('a.btn.picker-btn')
    one_way_trip_el.click()

    # Extract request
    search_button_el = page.get_by_role("button", name="SEARCH")
    with page.expect_request(lambda r: r.resource_type in ("xhr", "fetch")) as request_info:
        search_button_el.click()

    # Check extracted request is valid and contains all items of interest
    request = request_info.value
    method = request.method
    url = request.url
    headers = request.all_headers()
    post_data = request.post_data_json

    if method == "POST" and url is not None and headers.get("cookie") is not None and headers.get("requestverificationtoken") is not None and post_data is not None:
        # serialize to json and write to dump file
        datadump_json = headers
        assert post_data is not None
        for key, value in post_data.items():
            datadump_json.setdefault(key, value)
        datadump_json.setdefault("url", url)
        datadump_json.setdefault("from_station", FROM_STATION)
        datadump_json.setdefault("to_station", TO_STATION)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] Writing captured request data to file {REQUEST_DUMP_FILE}")

        path = Path(REQUEST_DUMP_FILE)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(datadump_json, f, indent=2, ensure_ascii=False)
        #print("Check file contents:")
        #read_dump = orjson.loads(path.read_bytes())
        #print(read_dump)
        #print("\nnon JSON dump:")
        #dumbdump = json.dumps(read_dump, indent=2, ensure_ascii=False)
        #print(dumbdump)
    else:
        print("\nERROR: Request captured with invalid data")
        print("URL:", url)
        print("Method:", method)
        print("\nHeaders:")
        for key, value in headers.items():
            print(f"{key}: {value}")
        print(f"Search parameters: from {FROM_STATION} to {TO_STATION}")
        if [post_data] is None:
            print("No post data")
        else:
            assert post_data is not None
            print("\nPost data:")
            for item in post_data.items():
                print(item)