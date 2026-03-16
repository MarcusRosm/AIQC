import os
import re
import pytest
from concurrent.futures import ThreadPoolExecutor
from playwright.sync_api import Page, APIRequestContext, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: 04b1e161-5cbd-466f-822c-77b9851252d7
def test_successfully_trigger_new_pipeline_run_via_api(page: Page):
    """Verify that a POST request to the pipeline run endpoint initiates the process."""
    diff_content = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-old
+new"""
    
    payload = {
        "run_label": "Feature Test",
        "diff_text": diff_content
    }
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    expect(response).to_be_ok()
    assert response.status == 202
    
    body = response.json()
    assert "run_id" in body
    # Verify UUID format
    assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", body["run_id"])

# SCENARIO_ID: beecaaab-326b-4203-8444-5ac5149a35a2
def test_verify_sse_status_stream_for_active_run(page: Page):
    """Ensure the client can connect to the SSE endpoint and receive events."""
    # 1. Create a run to get a run_id
    setup_response = page.request.post(
        f"{BASE_URL}/api/pipeline/run", 
        data={"run_label": "SSE Test", "diff_text": "valid diff"}
    )
    run_id = setup_response.json()["run_id"]
    
    # 2. Check SSE endpoint headers
    # Note: APIRequestContext.get waits for the stream to finish/timeout. 
    # We primarily verify the connection type here.
    response = page.request.get(f"{BASE_URL}/api/pipeline/status/{run_id}")
    
    assert response.headers.get("content-type") == "text/event-stream"
    expect(response).to_be_ok()

# SCENARIO_ID: bba5a6e8-6d61-4d96-ae3a-0a3b03a68833
def test_list_completed_pipeline_reports_in_ui(page: Page):
    """Check that the reports list correctly displays the summary of recent runs."""
    page.goto(f"{BASE_URL}/reports")
    
    expect(page).to_have_url(re.compile(r".*/reports"))
    
    # Locate the list of reports
    reports_list_item = page.get_by_role("listitem").first
    expect(reports_list_item).to_be_visible()

# SCENARIO_ID: ec1903ed-d4c9-4acf-abe2-3aa1380372a1
def test_trigger_run_with_missing_required_fields(page: Page):
    """Verify the API handles missing 'diff_text' gracefully (422)."""
    # missing diff_text
    payload = {"run_label": "Incomplete Run"}
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    assert response.status == 422
    error_detail = response.json()["detail"]
    assert any("diff_text" in str(err) for err in error_detail)

# SCENARIO_ID: 3b9d0cd2-48a0-441f-895c-fa61945faf9b
def test_attempt_to_retrieve_non_existent_report_detail(page: Page):
    """Ensure a 404 is returned when querying a run_id that does not exist."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = page.request.get(f"{BASE_URL}/api/reports/{fake_id}")
    
    assert response.status == 404
    expect(response).not_to_be_ok()

# SCENARIO_ID: f4bea069-2560-4c34-83cb-6d96bc4bfd28
def test_concurrent_pipeline_execution_handling(page: Page):
    """Simulate multiple simultaneous pipeline requests."""
    payload = {"run_label": "Concurrent Test", "diff_text": "simple diff"}
    
    def make_request():
        return page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: make_request(), range(5)))

    run_ids = []
    for res in results:
        assert res.status == 202
        run_id = res.json().get("run_id")
        assert run_id is not None
        run_ids.append(run_id)

    # Ensure all run_ids are unique
    assert len(set(run_ids)) == 5

# SCENARIO_ID: 6cd233e2-f27e-4ebe-b7d2-426de1fefb88
def test_pipeline_run_with_extremely_large_diff_text(page: Page):
    """Test the limits of the diff analyzer with a multi-megabyte payload."""
    large_diff = "diff --git a/large.txt b/large.txt
" + ("+new content line
" * 50000)
    payload = {"run_label": "Large Payload Test", "diff_text": large_diff}
    
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    # Should either accept (202) or reject with 413, but not 500
    assert response.status in [202, 413]
    if response.status == 202:
        assert "run_id" in response.json()

# SCENARIO_ID: 8d5397bc-ade8-4366-b7ff-b96750179486
def test_input_validation_for_malicious_payload_in_run_label(page: Page):
    """Check for XSS vulnerabilities in the run_label field."""
    malicious_label = "<script>alert('xss')</script>"
    payload = {
        "run_label": malicious_label, 
        "diff_text": "valid diff context"
    }
    
    # Trigger via API
    api_response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    expect(api_response).to_be_ok()

    # Check UI sanitization
    page.goto(f"{BASE_URL}/reports")
    
    # If properly escaped, the literal string should be visible as text, 
    # and no alert should have triggered (though Playwright handles alerts automatically).
    # We verify the text content exists exactly as provided.
    label_element = page.get_by_text(malicious_label)
    expect(label_element).to_be_visible()

# SCENARIO_ID: 5b42c83d-7dff-4016-8899-bf1d253f3305
def test_direct_access_to_internal_reports_directory_mapping(page: Page):
    """Attempt to access reports outside the intended directory via path traversal."""
    traversal_path = "../../etc/passwd"
    response = page.request.get(f"{BASE_URL}/api/reports/{traversal_path}")
    
    # Security check: status should be error code, not success
    assert response.status in [400, 404, 422]
    expect(response).not_to_be_ok()
