"""
Network Request/Response Capture Template
--------------------------
Loads a webpage, performs some actions, and captures all or filtered network requests/responses.
"""

from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=False)  # headless=True in production
    context = browser.new_context(
        viewport={'width': 1280, 'height': 800},
        # record_har_path="network.har"   # optional: save everything to HAR file
    )
    page = context.new_page()

    # Lists to collect everything
    requests_log = []
    responses_log = []

    # Listen to every request
    def log_request(request):
        req_info = {
            "method": request.method,
            "url": request.url,
            "resource_type": request.resource_type,      # "xhr", "fetch", "script", "image", ...
            "headers": dict(request.headers),
            "post_data": request.post_data,              # for POST/PUT etc.
        }
        requests_log.append(req_info)
        print(f">> {request.method} {request.url}  ({request.resource_type})")

    page.on("request", log_request)

    # Listen to every response
    def log_response(response):
        try:
            body = response.text() if response.body() else None  # careful: consumes body!
        except:
            body = "[binary or error]"

        resp_info = {
            "status": response.status,
            "url": response.url,
            "resource_type": response.request.resource_type,
            "headers": dict(response.headers),
            "body_preview": body[:500] if body else None,  # truncate large bodies
        }
        responses_log.append(resp_info)
        print(f"<< {response.status} {response.url}")

    page.on("response", log_response)

    # Go to the site & do actions
    page.goto("https://example.com/some-dynamic-page")
    page.wait_for_timeout(5000)               # give time for background requests
    # ... do clicks, scrolls, form submissions etc.
    # page.locator("button#search").click()
    # page.wait_for_load_state("networkidle")

    # After you're done → inspect what you captured
    print(f"Captured {len(requests_log)} requests and {len(responses_log)} responses")

    # Optional: filter only API calls / XHR / fetch
    api_calls = [
        r for r in zip(requests_log, responses_log)
        if r[0]["resource_type"] in ("xhr", "fetch")
    ]

    for req, resp in api_calls[:5]:  # show first few
        print(f"API → {req['method']} {req['url']}")
        print(f"     ← {resp['status']}  body preview: {resp['body_preview']}")

    browser.close()

with sync_playwright() as p:
    run(p)