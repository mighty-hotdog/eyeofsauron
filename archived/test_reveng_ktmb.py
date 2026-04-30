import re
import json
import sys
from playwright.sync_api import sync_playwright, Page, expect
from datetime import datetime

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
        page.locator('div.modal-content').filter(has_text="System maintenance scheduled").click()
    
    # Click to open date picker for departure date
    page.locator('input[type="text"][name="OnwardDate"]').click()
    #hidden_datepicker_el = page.locator('section.lightpick.is-hidden')
    #print(hidden_datepicker_el.count())

    # Click to select departure date
    daypicker_el = page.locator('div.lightpick__day.is-available')
    daypicker_el.nth(0).click()

    # Click to select one way trip
    one_way_trip_el = page.locator('a.btn.picker-btn')
    one_way_trip_el.click()

    # Extract response
    #response = page.wait_for_response(lambda r: r.request.resource_type in ("xhr", "fetch"))       # wait_for_response might not work
    #with page.expect_response(lambda r: r.request.resource_type in ("xhr", "fetch")) as resp_info: # expect_response is better alternative
    #response = resp_info.value
    #print("First XHR/fetch after click:", response.json())

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
        # write to config file
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[{ts}] Writing extracted request to file")
    else:
        print("\n")
        print("ERROR: Invalid request")
        print("Method:", method)
        print("URL:", url)
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
    
    # Click SEARCH button
    #search_button_el = page.get_by_role("button", name="SEARCH")
    #search_button_el.click()

    # Show response
    #print("First XHR/fetch after click:", response)
    #for i in range(daypicker_el.count()):
    #    print(f"Daypicker value: {daypicker_el.nth(i).inner_text()}")
    # Locate and set correct origin and destination
    #if (page.locator('input[type="text"][name="FromStationId"]').input_value() == "JB SENTRAL") and (page.locator('input[type="text"][name="ToStationId"]').input_value() == "WOODLANDS CIQ"):
    #    FromStationData_value = page.locator('input[type="hidden"][name="FromStationData"]').input_value()
    #    ToStationData_value = page.locator('input[type="hidden"][name="ToStationData"]').input_value()

    #    print(f"FromStationData: {FromStationData_value}")
    #    print(f"ToStationData: {ToStationData_value}")
    #    print("\n\n")

        #page.locator('i.fa.fa-exchange.web-exchange.d-none.d-md-block.mt22[onclick="SwapFromToTerminal()"]').click()
        #FromStationData_value = page.locator('input[type="hidden"][name="FromStationData"]').input_value()
        #ToStationData_value = page.locator('input[type="hidden"][name="ToStationData"]').input_value()

        #print(f"FromStationData: {FromStationData_value}")
        #print(f"ToStationData: {ToStationData_value}")
    
    #el = page.locator('input[type="hidden"]')
    #el = page.locator("*:has-text('token')")
    #el = page.locator("*:has-text('__RequestVerificationToken')")
    #el = page.locator('input[name="__RequestVerificationToken"]')
    #el = page.get_by_text("__RequestVerificationToken")
    #el = page.get_by_text(re.compile(r"token", re.IGNORECASE))
    #el = page.get_by_text(re.compile('__RequestVerificationToken', re.IGNORECASE))
    #el = page.get_by_text("/^token")
    #el = page.locator("text=/^token$/i")
    #print(el.input_value())
    #el = page.locator('input[type="hidden"]').filter(has_text=re.compile('__RequestVerificationToken', re.IGNORECASE))
    #el = page.locator('input[type="hidden"][name="__RequestVerificationToken"]').filter(has_text="__RequestVerificationToken")
    #el = page.locator('input[type="hidden"]')#.filter(has=page.get_by_text("__RequestVerificationToken"))
    #el = page.locator('input[type="hidden"]')#.get_by_text("StationData")
    #print(f"token instances found: {el.count()}")
    #for i in range(el.count()):
    #    print(f"token {i}: {el.nth(i).get_attribute('name')} / value: {el.nth(i).input_value()}")
    #print(el.get_attribute("name"))
    #print("\n\n")