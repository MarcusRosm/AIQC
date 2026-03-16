import os
import re
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: d4687dca-ef9d-4d4a-90be-cc64463de082
def test_status_indicator_is_visible_on_load(page: Page):
    page.goto(BASE_URL)
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_be_visible()

# SCENARIO_ID: 500afed9-5c08-4e92-bcdb-41e3d17cd557
def test_status_indicator_shows_connected_when_healthy(page: Page):
    page.goto(BASE_URL)
    healthy_text = page.get_by_text(re.compile(r"healthy|connected|active", re.IGNORECASE))
    expect(healthy_text).to_be_visible()

# SCENARIO_ID: c7980f0e-51b0-49b8-a999-8e1976d10ef2
def test_status_indicator_shows_disconnected_on_api_failure(page: Page):
    # Mock the status endpoint to return a 500 error
    page.route("**/api/status", lambda route: route.fulfill(status=500))
    page.goto(BASE_URL)
    
    error_state_text = page.get_by_text(re.compile(r"disconnected|error|offline", re.IGNORECASE))
    expect(error_state_text).to_be_visible()

# SCENARIO_ID: 7be1822c-0a1d-4d4a-9260-29d65f8258dc
def test_status_indicator_shows_loading_state_during_fetch(page: Page):
    # Navigate and check for aria-busy attribute indicating loading state
    page.goto(BASE_URL)
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_have_attribute("aria-busy", "true")

# SCENARIO_ID: 649615fa-1f67-4d19-ab94-b4700df6608f
def test_status_indicator_is_responsive_on_mobile(page: Page):
    page.set_viewport_size({"width": 375, "height": 667})
    page.goto(BASE_URL)
    
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_be_in_viewport()

# SCENARIO_ID: 416682af-655d-4746-b9c9-ed89e1e1ff74
def test_status_indicator_prevents_xss_injection(page: Page):
    # Inject a malicious payload via mocked API
    xss_payload = {"status": "<img src=x onerror=alert(1)>"}
    page.route("**/api/status", lambda route: route.fulfill(json=xss_payload))
    page.goto(BASE_URL)
    
    # Verify that the image with onerror is not attached to the DOM
    malicious_element = page.locator("img[onerror]")
    expect(malicious_element).not_to_be_attached()

# SCENARIO_ID: 58570876-1ba5-4495-aba6-4f2e3866d736
def test_status_indicator_updates_dynamically_without_reload(page: Page):
    # Set initial healthy state
    page.route("**/api/status", lambda route: route.fulfill(json={"status": "Connected"}))
    page.goto(BASE_URL)
    expect(page.get_by_text(re.compile(r"connected", re.IGNORECASE))).to_be_visible()
    
    # Mock a state change to Maintenance
    page.route("**/api/status", lambda route: route.fulfill(json={"status": "Maintenance"}))
    
    # Playwright's expect will poll until the text appears or times out
    maintenance_text = page.get_by_text(re.compile(r"maintenance", re.IGNORECASE))
    expect(maintenance_text).to_be_visible()

# SCENARIO_ID: 0059b567-d253-4f68-a45c-56ec8f9e71a0
def test_status_indicator_has_correct_accessibility_attributes(page: Page):
    page.goto(BASE_URL)
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_have_attribute("aria-live", "polite")
