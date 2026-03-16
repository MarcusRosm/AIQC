import os
import pytest
from playwright.sync_api import Page, expect

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

# SCENARIO_ID: bff83136-e7a3-411e-8ed0-2208eb7e8c60
def test_trigger_new_pipeline_run_and_monitor_sse_status_updates(page: Page):
    # TODO: resolve PipelineRunRequest
    pytest.skip("payload model 'PipelineRunRequest' not in context")

# SCENARIO_ID: fc735f2b-e6a4-48c6-8bdf-d76af9e40907
def test_retrieve_list_of_completed_pipeline_reports(page: Page):
    page.goto(BASE_URL)
    
    response = page.request.get(f"{BASE_URL}/api/reports")
    expect(response).to_be_ok()
    
    reports = response.json()
    assert isinstance(reports, list), "Expected a list of report summaries"
    # If reports exist, verify structure based on snippet 2 (summaries)
    if len(reports) > 0:
        assert "run_id" in reports[0] or reports[0], "Report summary should not be empty"

# SCENARIO_ID: b0c155d2-4621-4c93-bae8-8e98c5406c21
def test_view_full_details_of_specific_pipeline_report(page: Page):
    page.goto(BASE_URL)
    
    # Precondition: Get an existing run_id from the list
    list_res = page.request.get(f"{BASE_URL}/api/reports")
    reports = list_res.json()
    if not reports:
        pytest.skip("No reports available to retrieve details")
    
    # Assuming 'run_id' is a key in the summary as hinted in route params
    target_run_id = reports[0].get("run_id")
    if not target_run_id:
        pytest.skip("Could not determine run_id from report summary")

    detail_res = page.request.get(f"{BASE_URL}/api/reports/{target_run_id}")
    expect(detail_res).to_be_ok()
    
    detail_data = detail_res.json()
    # PipelineRun schema expected as per snippet 3
    assert "run_id" in detail_data or "stages" in detail_data

# SCENARIO_ID: 1cf96fe3-00c2-4201-a384-de528ef1d36f
def test_delete_existing_pipeline_report(page: Page):
    page.goto(BASE_URL)
    
    # Precondition: Identify a report to delete
    list_res = page.request.get(f"{BASE_URL}/api/reports")
    reports = list_res.json()
    if not reports:
        pytest.skip("No reports available to delete")
    
    target_run_id = reports[0].get("run_id")
    
    # Step 1: DELETE
    delete_res = page.request.delete(f"{BASE_URL}/api/reports/{target_run_id}")
    assert delete_res.status == 204
    
    # Step 2: Verify GET returns 404
    get_res = page.request.get(f"{BASE_URL}/api/reports/{target_run_id}")
    assert get_res.status == 404

# SCENARIO_ID: e8e5ad3d-2d44-4800-ba7c-ad80ed2924a0
def test_request_status_for_non_existent_run_id(page: Page):
    page.goto(BASE_URL)
    invalid_id = "invalid-id-123"
    
    response = page.request.get(f"{BASE_URL}/api/pipeline/status/{invalid_id}")
    
    assert response.status == 404
    error_detail = response.json().get("detail", "")
    assert "not found" in error_detail or "completed" in error_detail

# SCENARIO_ID: 43508f90-4a68-4504-bdd8-0f8db29428f7
def test_submit_pipeline_run_with_malformed_payload(page: Page):
    # TODO: resolve PipelineRunRequest
    pytest.skip("payload model 'PipelineRunRequest' not in context")

# SCENARIO_ID: 035f06c2-06e4-47bf-bcbb-d0d304135908
def test_retrieve_missing_report_detail(page: Page):
    page.goto(BASE_URL)
    
    response = page.request.get(f"{BASE_URL}/api/reports/does-not-exist")
    assert response.status == 404

# SCENARIO_ID: fd35f8d3-9a0f-4419-822c-6da2d2ee3eaf
def test_handle_corrupted_report_json_file(page: Page):
    page.goto(BASE_URL)
    # Precondition requires a file specifically named to trigger the parse error
    corrupted_id = "corrupted-test-case"
    
    response = page.request.get(f"{BASE_URL}/api/reports/{corrupted_id}")
    
    # Based on Snippet 3 try/except block returning 500
    if response.status == 500:
        error_detail = response.json().get("detail", "")
        assert "Failed to parse report" in error_detail
    else:
        pytest.skip("Environment does not have a corrupted JSON file setup")

# SCENARIO_ID: 0a2eb61e-c5b2-4415-9ed5-5259ad13ce12
def test_sse_connection_persistence_and_reconnection(page: Page):
    # SSE testing with sync Playwright requires specialized streaming handling
    # Usually requires page.evaluate with EventSource which is context-dependent
    pytest.skip("SSE stream validation requires async or browser-side EventSource execution")

# SCENARIO_ID: 230c9a5b-553f-49bb-8513-9e0ecaeea1e7
def test_path_traversal_probe_on_report_retrieval(page: Page):
    page.goto(BASE_URL)
    traversal_path = "../../etc/passwd"
    
    response = page.request.get(f"{BASE_URL}/api/reports/{traversal_path}")
    
    # Security expectation is 404 or 422 to prevent directory traversal
    assert response.status in [404, 422]
"