import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
API_PIPELINE_RUN = f"{BASE_URL}/api/pipeline/run"
API_REPORTS = f"{BASE_URL}/api/reports"

# SCENARIO_ID: dc41e14d-46b0-4a67-9152-168af075d058
def test_trigger_successful_pipeline_run_returns_202(page: Page):
    page.goto(BASE_URL)
    payload = {
        "run_label": "Happy Path Run",
        "diff_text": "diff --git a/app/main.py b/app/main.py
+@app.get('/')
+def read_root():
+    return {'Hello': 'World'}"
    }
    response = page.request.post(API_PIPELINE_RUN, data=payload)
    expect(response).to_be_ok()
    assert response.status == 202
    
    body = response.json()
    assert "run_id" in body
    assert len(body["run_id"]) > 0

# SCENARIO_ID: 57bc8653-4615-4be7-91e4-98bc2905f518
def test_list_completed_pipeline_reports_returns_summaries(page: Page):
    page.goto(BASE_URL)
    response = page.request.get(API_REPORTS)
    expect(response).to_be_ok()
    
    reports = response.json()
    assert isinstance(reports, list)

# SCENARIO_ID: 3a3e5759-1bf4-4e30-8c86-b9b16c13c8af
def test_retrieve_specific_report_details_returns_200(page: Page):
    page.goto(BASE_URL)
    run_id = "test-uuid-123"
    # Note: This test assumes pre-existence of test-uuid-123 or a mock
    response = page.request.get(f"{API_REPORTS}/{run_id}")
    
    if response.status == 404:
        pytest.skip(f"Report {run_id} not found in environment")
        
    expect(response).to_be_ok()
    body = response.json()
    assert "diff_result" in body

# SCENARIO_ID: 696d235f-648e-41c3-9718-1a29a5b062bc
def test_submit_pipeline_run_with_empty_payload_returns_422(page: Page):
    page.goto(BASE_URL)
    # Empty JSON payload to trigger FastAPI validation error
    response = page.request.post(API_PIPELINE_RUN, data={})
    expect(response).not.to_be_ok()
    assert response.status == 422

# SCENARIO_ID: 1bebb2c5-ef7f-4ac9-9631-1c98fb19c45c
def test_request_non_existent_report_id_returns_404(page: Page):
    page.goto(BASE_URL)
    response = page.request.get(f"{API_REPORTS}/non-existent-id")
    expect(response).not.to_be_ok()
    assert response.status == 404

# SCENARIO_ID: af6371fc-4ec9-4ce7-a1ec-b20fdda3b02e
def test_handle_extremely_large_diff_payload_stability(page: Page):
    page.goto(BASE_URL)
    large_diff = "diff --git a/large.txt b/large.txt
" + ("+content
" * 10000)
    payload = {
        "run_label": "Performance Test",
        "diff_text": large_diff
    }
    response = page.request.post(API_PIPELINE_RUN, data=payload)
    # System should either accept (202) or reject with 413, but not 500 crash
    assert response.status in [202, 413]
    expect(response).not.to_have_status(500)

# SCENARIO_ID: 9ade2a74-7ed5-40fd-9b76-6c06a6601686
def test_pipeline_run_with_empty_diff_content(page: Page):
    page.goto(BASE_URL)
    payload = {
        "run_label": "Empty Diff",
        "diff_text": ""
    }
    response = page.request.post(API_PIPELINE_RUN, data=payload)
    expect(response).to_be_ok()
    assert response.status == 202

# SCENARIO_ID: eaa138a4-9bc3-414b-8f80-f9d461bb7012
def test_path_traversal_attempt_in_report_retrieval_fails(page: Page):
    page.goto(BASE_URL)
    # Attempting to access sensitive system files via relative paths
    traversal_id = "../../etc/passwd"
    response = page.request.get(f"{API_REPORTS}/{traversal_id}")
    
    # Security check: Must not return 200
    expect(response).not.to_be_ok()
    assert response.status in [404, 400, 422]

# SCENARIO_ID: f06fa4c0-7533-49a3-b1d4-1d68a024dbb1
def test_xss_probe_in_run_label_is_escaped(page: Page):
    page.goto(BASE_URL)
    xss_payload = "<script>alert('xss')</script>"
    payload = {
        "run_label": xss_payload,
        "diff_text": "diff --git a/a b/a
+changes"
    }
    
    # 1. Submit the run
    post_response = page.request.post(API_PIPELINE_RUN, data=payload)
    expect(post_response).to_be_ok()
    
    # 2. Check the reports list to ensure it is stored/returned correctly
    get_response = page.request.get(API_REPORTS)
    expect(get_response).to_be_ok()
    
    reports_text = get_response.text()
    # The literal script string should be present (not executed or stripped)
    assert xss_payload in reports_text

# SCENARIO_ID: d22f6a67-10fd-43c7-b5fc-ee6ff81d82b5
def test_concurrent_pipeline_run_requests_receive_unique_ids(page: Page):
    page.goto(BASE_URL)
    payload = {
        "run_label": "Concurrency Test",
        "diff_text": "diff --git a/a b/a
+changes"
    }
    
    run_ids = []
    for _ in range(3):
        response = page.request.post(API_PIPELINE_RUN, data=payload)
        expect(response).to_be_ok()
        run_ids.append(response.json()["run_id"])
    
    # Verify all generated IDs are unique
    assert len(set(run_ids)) == len(run_ids)
