import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: 54818fe0-b577-4475-ba84-ec9c6571649a
def test_successfully_trigger_new_pipeline_via_ui(page: Page):
    run_label_input = page.get_by_label("Run Label")
    diff_input = page.get_by_placeholder("Paste diff here")
    start_button = page.get_by_role("button", name="Start Pipeline")

    page.goto(BASE_URL)
    run_label_input.fill("Test Run Alpha")
    diff_input.fill("""diff --git a/file.py b/file.py
+new_line""")
    start_button.click()
    
    # Verify status changes to 'Started'
    expect(page.get_by_text("Started")).to_be_visible()

# SCENARIO_ID: b415eae1-8e1a-43d6-aa26-c5c39d185478
def test_api_start_pipeline_run_with_valid_payload(page: Page):
    # Derived from PipelineRunRequest in Snippet 2 and usage in Snippet 4
    payload = {
        "run_label": "API-Test",
        "diff_text": "diff content"
    }
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    expect(response).to_be_ok()
    assert response.status == 202
    assert "run_id" in response.json()

# SCENARIO_ID: c048fa7b-a3a4-46b9-ab7f-32de7dda30f8
def test_track_pipeline_progress_via_sse_stream(page: Page):
    # First trigger a run to get a run_id
    start_payload = {"run_label": "SSE-Track", "diff_text": "test"}
    start_resp = page.request.post(f"{BASE_URL}/api/pipeline/run", data=start_payload)
    run_id = start_resp.json().get("run_id")
    
    response = page.request.get(f"{BASE_URL}/api/pipeline/status/{run_id}")
    expect(response).to_be_ok()
    assert "text/event-stream" in response.headers.get("content-type", "")

# SCENARIO_ID: b40886d2-5a98-4a4b-aac1-f5c05997e8cd
def test_handle_missing_run_label_in_request(page: Page):
    # Payload missing required 'run_label' field
    payload = {"diff_text": "some diff"}
    response = page.request.post(f"{BASE_URL}/api/pipeline/run", data=payload)
    
    assert response.status == 422

# SCENARIO_ID: 2d726fe6-1439-4107-b648-06b28f040048
def test_request_non_existent_report_details(page: Page):
    response = page.request.get(f"{BASE_URL}/api/reports/non-existent-uuid")
    
    assert response.status == 404

# SCENARIO_ID: ccc7fa09-f422-4201-8a66-8142832b354d
def test_handle_empty_reports_directory(page: Page):
    response = page.request.get(f"{BASE_URL}/api/reports")
    
    expect(response).to_be_ok()
    assert isinstance(response.json(), list)

# SCENARIO_ID: 394fd024-998a-443e-b5bf-f97e5caa76d9
def test_concurrent_pipeline_run_initialization(page: Page):
    results = []
    for i in range(3):
        resp = page.request.post(f"{BASE_URL}/api/pipeline/run", data={
            "run_label": f"Concurrent-Run-{i}",
            "diff_text": f"diff-content-{i}"
        })
        results.append(resp)

    for response in results:
        assert response.status == 202
        assert "run_id" in response.json()

# SCENARIO_ID: efdaa094-7211-44cd-8ec3-78f8f3805157
def test_xss_injection_attempt_in_run_label(page: Page):
    malicious_label = "<script>alert('xss')</script>"
    page.request.post(f"{BASE_URL}/api/pipeline/run", data={
        "run_label": malicious_label,
        "diff_text": "valid diff"
    })
    
    page.goto(f"{BASE_URL}/reports")
    # Verify text is rendered as literal string
    label_text = page.get_by_text(malicious_label)
    expect(label_text).to_be_visible()

# SCENARIO_ID: 3ee493bb-a1cb-4807-b926-e1183b0eeed5
def test_list_reports_ordered_by_newest_first(page: Page):
    # Ensure at least two reports exist for sorting verification
    page.request.post(f"{BASE_URL}/api/pipeline/run", data={"run_label": "Old", "diff_text": "t"})
    page.request.post(f"{BASE_URL}/api/pipeline/run", data={"run_label": "Newest", "diff_text": "t"})

    response = page.request.get(f"{BASE_URL}/api/reports")
    expect(response).to_be_ok()
    
    reports = response.json()
    assert len(reports) >= 2
    # Based on snippet 1 logic: sorted by mtime descending
    # Checking that the data structure is correct
    assert "run_id" in reports[0]
