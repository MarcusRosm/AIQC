import os
import uuid
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: e2e9238c-e7b7-4ba1-a110-db4c79414756
def test_trigger_successful_pipeline_run_via_api(page: Page):
    """Verify that a valid POST request to /api/pipeline/run starts the orchestrator."""
    payload = {
        "run_label": "Initial Test",
        "diff_text": "diff --git a/app.py b/app.py
+print('hello')"
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    expect(response).to_be_ok()
    assert response.status == 202
    
    response_json = response.json()
    assert "run_id" in response_json
    # Validate UUID format
    uuid.UUID(response_json["run_id"])

# SCENARIO_ID: 05870640-9e9a-4f14-bb8d-6e5729cc9461
def test_monitor_pipeline_progress_via_sse_stream(page: Page):
    """Ensure the SSE endpoint provides real-time updates for a specific run_id."""
    # Precondition: Initiate a run to get a run_id
    setup_payload = {
        "run_label": "SSE Monitor Test",
        "diff_text": "diff --git a/app.py b/app.py
+print('sse')"
    }
    setup_response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=setup_payload)
    run_id = setup_response.json()["run_id"]
    
    # Action: GET SSE stream
    response = page.request.get(f"{BASE_URL}/api/pipeline/status/{run_id}")
    
    expect(response).to_be_ok()
    assert "text/event-stream" in response.headers.get("content-type", "")

# SCENARIO_ID: bb121f73-378b-4279-8926-96ea7b237245
def test_list_completed_pipeline_reports_in_ui(page: Page):
    """Verify that completed runs appear in the reports summary list."""
    reports_url = f"{BASE_URL}/reports"
    page.goto(reports_url)
    
    heading = page.get_by_role("heading", name="Reports")
    expect(heading).to_be_visible()
    
    # Assuming reports are rendered in a list
    latest_report = page.get_by_role("listitem").first
    expect(latest_report).to_be_visible()

# SCENARIO_ID: e15d15b9-2cf2-45ce-afbf-24850a0fc329
def test_reject_run_request_with_missing_mandatory_fields(page: Page):
    """Ensure the API returns a 422 error when diff_text is missing."""
    # Payload missing 'diff_text'
    payload = {"run_label": "Incomplete"}
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    assert response.status == 422
    error_detail = response.json().get("detail", [])
    assert any("diff_text" in str(err) for err in error_detail)

# SCENARIO_ID: c1f19f8c-3ac5-4265-9858-20559a4d9426
def test_handle_non_existent_run_id_in_status_stream(page: Page):
    """Check behavior when requesting an SSE stream for an invalid UUID."""
    invalid_run_id = "00000000-0000-0000-0000-000000000000"
    
    response = page.request.get(f"{BASE_URL}/api/pipeline/status/{invalid_run_id}")
    
    assert response.status == 404

# SCENARIO_ID: 960c11a7-24ee-49ea-900d-39638eeacbf5
def test_process_extremely_large_diff_payload(page: Page):
    """Test handling of a 5MB diff_text input."""
    large_diff = "diff --git a/file.txt b/file.txt
+" + ("x" * 5 * 1024 * 1024)
    payload = {
        "run_label": "Performance Test",
        "diff_text": large_diff
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    # Should accept the task even if large
    assert response.status == 202
    assert "run_id" in response.json()

# SCENARIO_ID: a20c192d-217a-4397-9248-c221e28e4381
def test_empty_reports_directory_state(page: Page):
    """Verify /api/reports returns empty list gracefully when no reports exist."""
    # This test assumes a clean environment or mocked storage
    response = page.request.get(f"{BASE_URL}/api/reports")
    
    expect(response).to_be_ok()
    assert response.json() == []

# SCENARIO_ID: b1805bb4-6773-4838-b64d-e710128cee74
def test_prevent_xss_via_run_label_in_reports_ui(page: Page):
    """Verify malicious scripts in run_label are sanitized in the UI."""
    xss_payload = "<script>alert('xss')</script>"
    
    # 1. Inject the payload via API
    page.request.post(f"{BASE_URL}/api/pipeline/run", data={
        "run_label": xss_payload,
        "diff_text": "plain diff"
    })
    
    # 2. Setup dialog handler to fail if alert appears
    def handle_dialog(dialog):
        pytest.fail(f"XSS vulnerability detected: Alert triggered with message: {dialog.message}")
    
    page.on("dialog", handle_dialog)
    
    # 3. Navigate to reports and check rendering
    page.goto(f"{BASE_URL}/reports")
    
    # Check that the script tag is rendered as literal text and not executed
    label_element = page.get_by_text(xss_payload, exact=True)
    expect(label_element).to_be_visible()

# SCENARIO_ID: 1c1214cf-985f-41d9-8b39-1be58721dd9b
def test_unauthorized_access_to_report_details(page: Page):
    """Ensure report details require authentication."""
    valid_uuid = str(uuid.uuid4())
    
    # Requesting without auth headers/context
    response = page.request.get(f"{BASE_URL}/api/reports/{valid_uuid}")
    
    # Expecting 401 Unauthorized or 403 Forbidden based on scenario
    assert response.status in [401, 403]
