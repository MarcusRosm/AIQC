import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: ca6d9e97-5fc0-4be2-9122-b5b011c7d349
def test_successfully_trigger_pipeline_run_via_api(page: Page):
    """Ensure that a POST request to /api/pipeline/run with valid data returns a 202 status and a run_id."""
    endpoint = f"{BASE_URL}/api/pipeline/run"
    payload = {
        "run_label": "Test Run",
        "diff_text": "diff --git a/file.py b/file.py
+new line"
    }
    
    response = page.request.post(endpoint, data=payload)
    
    expect(response).to_be_ok()
    assert response.status == 202
    
    res_body = response.json()
    assert "run_id" in res_body
    assert isinstance(res_body["run_id"], str)

# SCENARIO_ID: 2fe85810-54a4-4a14-95d0-b4bb0ecde4e5
def test_monitor_pipeline_progress_via_sse(page: Page):
    """Verify that after starting a run, the SSE stream provides STARTED and DIFF_ANALYZED events."""
    # Trigger run to get run_id
    setup_res = page.request.post(
        f"{BASE_URL}/api/pipeline/run",
        data={"run_label": "SSE Monitor Test", "diff_text": "diff --git a/a.py b/a.py
+print(1)"}
    )
    run_id = setup_res.json()["run_id"]
    
    # Navigate to status endpoint
    status_url = f"{BASE_URL}/api/pipeline/status/{run_id}"
    page.goto(status_url)
    
    # SSE streams in browser usually render as text in the body or pre tag
    # We expect the stream to contain the event names and data descriptions
    body = page.locator("body")
    expect(body).to_contain_text("event: STARTED")
    expect(body).to_contain_text("Pipeline initialised.")
    expect(body).to_contain_text("event: DIFF_ANALYZED")

# SCENARIO_ID: f8808843-1d37-4cee-8926-516a0eb6c8e2
def test_verify_completed_run_appears_in_reports_list(page: Page):
    """Ensure the GET /api/reports endpoint includes the newly created run after it finishes."""
    # 1. Create a run
    setup_res = page.request.post(
        f"{BASE_URL}/api/pipeline/run",
        data={"run_label": "Report Visibility Test", "diff_text": "diff --git a/b.py b/b.py
+pass"}
    )
    run_id = setup_res.json()["run_id"]
    
    # 2. Check reports list
    # Note: In a real environment, we might need a small retry/wait for the background task to finish
    reports_response = page.request.get(f"{BASE_URL}/api/reports")
    expect(reports_response).to_be_ok()
    
    reports = reports_response.json()
    matching_report = next((r for r in reports if r.get("run_id") == run_id), None)
    assert matching_report is not None, f"Run ID {run_id} not found in reports list"

# SCENARIO_ID: 534c1591-4388-4d07-8355-a5955e5058f8
def test_trigger_run_with_missing_required_fields(page: Page):
    """Validate that the API rejects requests missing mandatory fields like run_label."""
    endpoint = f"{BASE_URL}/api/pipeline/run"
    # Missing 'run_label'
    payload = {"diff_text": "some diff"}
    
    response = page.request.post(endpoint, data=payload)
    
    assert response.status == 422
    error_detail = response.json().get("detail", [])
    assert any("run_label" in str(err) for err in error_detail)

# SCENARIO_ID: 9626355c-9df5-478c-989f-2595f9dfe1e4
def test_access_status_for_non_existent_run_id(page: Page):
    """Ensure the system handles requests for status of invalid or missing run IDs gracefully."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    endpoint = f"{BASE_URL}/api/pipeline/status/{fake_id}"
    
    response = page.request.get(endpoint)
    
    # Depending on SSE implementation, it might be a 404 or an immediate stream termination
    assert response.status in [404, 200]
    if response.status == 404:
        assert True
    else:
        # If 200, check if it emits an error event or is empty
        text = response.text()
        assert "error" in text.lower() or text == ""

# SCENARIO_ID: 36eb3c08-1250-4345-a08c-2375385077fa
def test_submit_extremely_large_diff_text(page: Page):
    """Test the system's resilience when processing a very large diff payload."""
    large_diff = "a" * (1024 * 1024 + 1024)  # ~1MB
    payload = {
        "run_label": "Large Diff Test",
        "diff_text": f"diff --git a/big.txt b/big.txt
+{large_diff}"
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    # System should either accept (202) or reject (413)
    assert response.status in [202, 413]
    if response.status == 202:
        assert "run_id" in response.json()

# SCENARIO_ID: e65064da-5090-452d-a7b8-8df30d972307
def test_ui_start_pipeline_run_and_check_status_list(page: Page):
    """End-to-end flow from the UI to trigger a run and verify visibility."""
    page.goto(f"{BASE_URL}/pipeline")
    
    run_label_input = page.get_by_label("Run Label")
    diff_input = page.get_by_placeholder("Paste diff here")
    start_button = page.get_by_role("button", name="Start Run")
    
    run_label_input.fill("UI Integration Test")
    diff_input.fill("diff --git a/a.txt b/a.txt")
    start_button.click()
    
    # Verify transition to monitoring state via expected text
    expect(page.get_by_text("Pipeline initialised")).to_be_visible()

# SCENARIO_ID: 1eb13592-5ed1-400b-99f6-8d0db4fe48dc
def test_prevent_xss_via_run_label_in_reports(page: Page):
    """Verify that a malicious run_label containing script tags is handled safely."""
    xss_payload = {
        "run_label": "<script>alert('xss')</script>",
        "diff_text": "valid diff"
    }
    
    # 1. Inject via API
    post_res = page.request.post(f"{BASE_URL}/api/pipeline/run", data=xss_payload)
    expect(post_res).to_be_ok()
    
    # 2. Check Reports View
    page.goto(f"{BASE_URL}/api/reports")
    
    # If rendered as HTML, the tag shouldn't exist as a literal element or should be escaped
    # get_by_text in Playwright looks for the rendered text content
    expect(page.get_by_text("<script>")).not_to_be_visible()
