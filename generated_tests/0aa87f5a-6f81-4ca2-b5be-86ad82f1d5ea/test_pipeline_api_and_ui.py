import os
import pytest
from playwright.sync_api import Page, expect, APIRequestContext

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: df6d22bb-d205-477e-b632-eca737fc5216
def test_successfully_trigger_new_pipeline_run_via_api(page: Page):
    payload = {
        "run_label": "Initial UI Test",
        "diff_text": "+ div { color: red; }"
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    expect(response).to_be_ok()
    assert response.status == 202
    
    res_json = response.json()
    assert res_json.get("run_id") is not None

# SCENARIO_ID: 3eace9b7-3872-4622-bf42-e8f2d19c1f35
def test_monitor_pipeline_progress_through_sse_stream(page: Page):
    # Setup: Create a run to get a valid run_id
    setup_payload = {
        "run_label": "SSE Monitor Test",
        "diff_text": "+ some changes"
    }
    setup_res = page.request.post(f"{BASE_URL}/api/pipeline/run", data=setup_payload)
    run_id = setup_res.json().get("run_id")
    
    # Test SSE connection
    response = page.request.get(f"{BASE_URL}/api/pipeline/status/{run_id}")
    
    expect(response).to_be_ok()
    assert "text/event-stream" in response.headers.get("content-type", "")
    
    # SSE responses in Playwright request API are returned as text once stream ends or buffer fills
    content = response.text()
    assert "event: STARTED" in content
    assert "Pipeline initialised." in content

# SCENARIO_ID: 2e6a85ec-2fdd-4a0a-a5c1-7c25913e4723
def test_verify_newly_created_run_appears_in_reports_list(page: Page):
    # Setup: Create a run
    setup_payload = {
        "run_label": "Persistence Test",
        "diff_text": "+ persistence check"
    }
    setup_res = page.request.post(f"{BASE_URL}/api/pipeline/run", data=setup_payload)
    run_id = setup_res.json().get("run_id")
    
    # Navigate to API reports
    response = page.request.get(f"{BASE_URL}/api/reports")
    expect(response).to_be_ok()
    
    reports = response.json()
    found = any(report.get("run_id") == run_id for report in reports)
    assert found is True, f"Run ID {run_id} not found in reports list"

# SCENARIO_ID: 1df0dbbe-d5a4-43fb-b401-2b2a2142dcfb
def test_reject_pipeline_run_request_with_missing_run_label(page: Page):
    # Missing 'run_label' as per PipelineRunRequest
    invalid_payload = {
        "diff_text": "some diff content"
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=invalid_payload)
    
    assert response.status == 422
    # Ensure the error message specifically mentions the missing field
    errors = response.json().get("detail", [])
    assert any("run_label" in str(err) for err in errors)

# SCENARIO_ID: 2acc3d25-55be-4159-a94b-e8a99cdaa445
def test_handle_non_existent_run_id_in_sse_connection(page: Page):
    invalid_id = "invalid-uuid-12345"
    response = page.request.get(f"{BASE_URL}/api/pipeline/status/{invalid_id}")
    
    assert response.status == 404

# SCENARIO_ID: 91e873bb-5279-4799-ad0b-db29aeb8899d
def test_initiate_pipeline_with_empty_diff_content(page: Page):
    payload = {
        "run_label": "Empty Diff Test",
        "diff_text": ""
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    assert response.status == 202
    run_id = response.json().get("run_id")
    
    status_response = page.request.get(f"{BASE_URL}/api/pipeline/status/{run_id}")
    assert "Analysed 0 changed file(s)" in status_response.text()

# SCENARIO_ID: de2c091a-5c75-457b-8415-54eea5af83ec
def test_handle_large_diff_payloads(page: Page):
    large_diff = "+ line
" * 10000
    payload = {
        "run_label": "Large Payload",
        "diff_text": large_diff
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    # The system should accept large payloads within limits (202 Accepted)
    expect(response).to_be_ok()
    assert response.status == 202

# SCENARIO_ID: 1a3005ae-9d99-47ff-8509-955afebaa5b3
def test_prevent_xss_via_run_label_in_reports_view(page: Page):
    xss_payload = "<script>alert('xss')</script>"
    payload = {
        "run_label": xss_payload,
        "diff_text": "valid diff"
    }
    
    # Step 1: Inject via API
    api_response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    expect(api_response).to_be_ok()
    
    # Step 2: Verify in UI
    page.goto(f"{BASE_URL}/reports")
    
    # If properly escaped, the raw string should be visible as text
    # rather than being interpreted as a script element.
    report_entry = page.get_by_text(xss_payload)
    expect(report_entry).to_be_visible()