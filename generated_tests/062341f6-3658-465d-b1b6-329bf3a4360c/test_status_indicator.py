import os
import re
import time
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: 9220fe51-86e4-4342-b043-6fec072a1598
def test_status_indicator_displays_initial_idle_state(page: Page):
    page.goto(BASE_URL)
    status_indicator = page.get_by_role("status")
    
    expect(status_indicator).to_be_visible()
    # Check for expected default state text like 'Idle' or 'Ready'
    expect(status_indicator).to_contain_text(re.compile(r"Idle|Ready", re.IGNORECASE))

# SCENARIO_ID: 9c081d48-e6e4-49fb-a305-76cf89714c49
def test_status_indicator_updates_during_diff_analysis(page: Page):
    page.goto(BASE_URL)
    diff_input = page.get_by_placeholder("Paste git diff here")
    analyze_button = page.get_by_role("button", name="Analyze")

    diff_text = """diff --git a/file.txt b/file.txt
+added line"""
    
    diff_input.fill(diff_text)
    analyze_button.click()

    # Verify transition states
    expect(page.get_by_text("Analyzing")).to_be_visible()
    expect(page.get_by_text("Success")).to_be_visible()

# SCENARIO_ID: 6ae41d2e-2be8-4a60-9cbb-1a3ddb6965c7
def test_handle_api_errors_in_status_indicator(page: Page):
    page.goto(BASE_URL)
    # Mock the analyze endpoint to return a 500 error
    page.route("**/analyze**", lambda route: route.fulfill(status=500))

    analyze_button = page.get_by_role("button", name="Analyze")
    analyze_button.click()

    # Indicator should reflect the error state
    expect(page.get_by_role("status")).to_contain_text("Error")

# SCENARIO_ID: 3b2e3c15-b70f-4d3a-beab-9cefad9a72cc
def test_status_indicator_resilience_to_long_component_names(page: Page):
    page.goto(BASE_URL)
    diff_input = page.get_by_placeholder("Paste git diff here")
    analyze_button = page.get_by_role("button", name="Analyze")

    long_name = "VeryLongComponentNameThatMightBreakTheLayoutTransitionIndicator"
    diff_content = f"""diff --git a/UI.tsx b/UI.tsx
+export const {long_name} = () => {{}};"""

    diff_input.fill(diff_content)
    analyze_button.click()

    # Assert layout remains functional and status is visible
    expect(page.get_by_role("status")).to_be_visible()
    expect(page.get_by_text(long_name)).to_be_visible()

# SCENARIO_ID: 831e1c7f-fc91-4296-94de-db18fc74fae3
def test_rapid_consecutive_diff_submissions(page: Page):
    page.goto(BASE_URL)
    analyze_button = page.get_by_role("button", name="Analyze")

    # Trigger multiple actions rapidly
    analyze_button.click()
    analyze_button.click()

    # Ensure the status indicator is not stuck and eventually shows a non-idle state
    expect(page.get_by_role("status")).not_to_have_text("Idle")

# SCENARIO_ID: 3317f9da-8f0a-4f41-8c1e-1b9fc17ab84a
def test_prevent_xss_via_diff_metadata_in_status_indicator(page: Page):
    page.goto(BASE_URL)
    # Setup listener to fail if any alert/dialog is triggered
    page.on("dialog", lambda dialog: pytest.fail(f"XSS vulnerability detected: {dialog.message}"))

    diff_input = page.get_by_placeholder("Paste git diff here")
    analyze_button = page.get_by_role("button", name="Analyze")

    malicious_diff = """diff --git a/<img src=x onerror=alert(1)>.tsx b/file.tsx
+const XSS = () => {};"""

    diff_input.fill(malicious_diff)
    analyze_button.click()

    # Malicious string should be rendered as text, not executed as HTML
    expect(page.get_by_text("<img src=x onerror=alert(1)>")).to_be_visible()

# SCENARIO_ID: 19f2ae09-4ece-41db-b4cd-28791f040b6b
def test_empty_diff_submission_handling(page: Page):
    page.goto(BASE_URL)
    diff_input = page.get_by_placeholder("Paste git diff here")
    analyze_button = page.get_by_role("button", name="Analyze")

    diff_input.fill("   ")
    analyze_button.click()

    # The UI should indicate a validation error or remain idle with a warning
    status_indicator = page.get_by_role("status")
    expect(status_indicator).to_contain_text(re.compile(r"Error|Warning|Idle", re.IGNORECASE))

# SCENARIO_ID: 7daf0dc5-6df7-4eed-8465-cd90a010ebe4
def test_network_latency_simulation_feedback(page: Page):
    page.goto(BASE_URL)

    def handle_route(route):
        time.sleep(5)
        route.continue_()

    # Simulate high network latency for analysis
    page.route("**/analyze**", handle_route)

    analyze_button = page.get_by_role("button", name="Analyze")
    analyze_button.click()

    # Analyzing state must persist while the request is pending
    expect(page.get_by_text("Analyzing")).to_be_visible()