import re
import json
import sys
import orjson
from playwright.sync_api import sync_playwright, Page, expect
from datetime import datetime
from pathlib import Path

def test_verify_correct_page(page: Page):
    page.goto("https://shuttleonline.ktmb.com.my/Home/Shuttle")

    # Expect page to contain expected elements
    # "Shuttle Tebrau"
    expect(page.get_by_text("Shuttle Tebrau", exact=True)).to_be_visible()
    # "Origin"
    expect(page.get_by_text("Origin")).to_be_visible()
    # "Destination"
    expect(page.get_by_text("Destination")).to_be_visible()
    # "Departure date"
    expect(page.get_by_text("Departure date")).to_be_visible()
    # "Return date"
    expect(page.get_by_text("Return date")).to_be_visible()
    # "Pax"
    expect(page.get_by_text("Pax", exact=True)).to_be_visible()
    # Search button
    expect(page.get_by_role("button", name="SEARCH")).to_be_visible()

def test_setup_for_submit(page: Page):
    page.goto("https://shuttleonline.ktmb.com.my/Home/Shuttle")

    # If maintenance pop-up is present, click to dismiss
    if page.locator('div.modal-content').filter(has_text="System maintenance scheduled").count() > 0:
        page.locator('div.modal-content').filter(has_text="System maintenance scheduled").get_by_role("button", name="OK").click()
    
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
        datadump_json.setdefault("url", url)
        assert post_data is not None
        for key, value in post_data.items():
            datadump_json.setdefault(key, value)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{ts}] Writing extracted request to file")

        path = Path("data_dump.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(datadump_json, f, indent=2, ensure_ascii=False)
        print("Check file contents:")
        read_dump = orjson.loads(path.read_bytes())
        print(read_dump)
        print("\nnon JSON dump:")
        dumbdump = json.dumps(read_dump, indent=2, ensure_ascii=False)
        print(dumbdump)
    else:
        print("\nERROR: Invalid request")
        print("URL:", url)
        print("Method:", method)
        print("\nHeaders:")
        for key, value in headers.items():
            print(f"{key}: {value}")
        if [post_data] is None:
            print("No post data")
        else:
            assert post_data is not None
            print("\nData:")
            for item in post_data.items():
                print(item)