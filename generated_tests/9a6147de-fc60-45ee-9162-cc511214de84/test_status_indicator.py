import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: bae0d458-588f-48a5-b8f7-6a368fdea008
def test_status_indicator_is_visible_on_main_dashboard(page: Page):
    page.goto(f"{BASE_URL}/")
    
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_be_visible()

# SCENARIO_ID: 58432760-04bb-4e7b-8286-d3eb2a5a326f
def test_status_indicator_reflects_active_state(page: Page):
    page.goto(f"{BASE_URL}/")
    
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_have_text("Active")

# SCENARIO_ID: 5501f7d7-f1cc-44f2-a50f-549546f7d949
def test_status_indicator_falls_back_to_unknown_on_missing_data(page: Page):
    # Mock API to return empty status object
    page.route("**/api/status", lambda route: route.fulfill(json={}))
    
    page.goto(f"{BASE_URL}/")
    
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_have_text("Unknown")

# SCENARIO_ID: 52ae1a6d-2517-40c9-8b30-5d06fe8be91d
def test_status_indicator_has_aria_live_polite_attribute(page: Page):
    page.goto(f"{BASE_URL}/")
    
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_have_attribute("aria-live", "polite")

# SCENARIO_ID: 093ec286-c9ab-4ddf-93b5-0a2d4d9f29f0
def test_status_indicator_handles_long_status_labels(page: Page):
    long_status = "System Maintenance Mode Underway"
    page.route("**/api/status", lambda route: route.fulfill(json={"status": long_status}))
    
    page.goto(f"{BASE_URL}/")
    
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_be_visible()
    expect(status_indicator).to_have_text(long_status)

# SCENARIO_ID: 65bb2a5c-8776-4448-a0af-06e77d30962e
def test_status_indicator_escapes_xss_injection_strings(page: Page):
    malicious_payload = "<img src=x onerror=alert(1)>"
    
    # Register dialog handler to fail if an alert is triggered
    page.on("dialog", lambda dialog: pytest.fail(f"XSS Vulnerability: Alert triggered with message: {dialog.message}"))
    
    page.route("**/api/status", lambda route: route.fulfill(json={"status": malicious_payload}))
    
    page.goto(f"{BASE_URL}/")
    
    # Verify that the payload is rendered as literal text and not as HTML
    expect(page.get_by_text("<img src=x")).to_be_visible()
    expect(page.get_by_role("status")).to_contain_text(malicious_payload)

# SCENARIO_ID: 959016d7-23e4-4209-86e0-762351e836f6
def test_status_indicator_is_visible_on_mobile_viewport(page: Page):
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(f"{BASE_URL}/")
    
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_be_visible()

# SCENARIO_ID: 90c14c2c-956d-4a4d-b1f4-ab8aeb530399
def test_status_indicator_updates_automatically_via_realtime_event(page: Page):
    page.goto(f"{BASE_URL}/")
    
    status_indicator = page.get_by_role("status")
    # Assuming initial state is 'Online' as per scenario
    expect(status_indicator).to_have_text("Online")
    
    # Trigger a simulated WebSocket message/update via page evaluation
    # Note: Implementation depends on how the app handles internal state updates
    page.evaluate("""
        window.dispatchEvent(new MessageEvent('message', {
            data: JSON.stringify({ type: 'STATUS_UPDATE', status: 'Offline' })
        }));
    """)
    
    expect(page.get_by_text("Offline")).to_be_visible()
