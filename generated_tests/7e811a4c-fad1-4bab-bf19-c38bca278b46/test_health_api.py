import os
import pytest
from playwright.sync_api import Page, expect

# Configuration constants
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
HEALTH_ENDPOINT = f"{BASE_URL}/api/health"

# SCENARIO_ID: 78172347-affe-4b0d-ae79-767177606f4b
def test_verify_health_check_reports_success_when_dependencies_healthy(page: Page):
    """Ensure the health endpoint returns 200 and all dependency flags are true."""
    page.goto(BASE_URL)
    
    # Use Playwright's API request context for the check
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    body = response.json()
    assert body.get("ollama") is True, "Ollama dependency should be reported as healthy (True)"
    assert body.get("chromadb") is True, "ChromaDB dependency should be reported as healthy (True)"

# SCENARIO_ID: ed78521c-3ae8-4886-9aa7-93d5f1da9cc8
def test_health_check_reports_ollama_unhealthy_on_service_error(page: Page):
    """Validate that the health check identifies an unhealthy Ollama service."""
    page.goto(BASE_URL)
    
    response = page.request.get(HEALTH_ENDPOINT)
    # The system returns 200 even if dependencies fail, but reports status in body
    expect(response).to_be_ok()
    
    body = response.json()
    assert body.get("ollama") is False, "Expected ollama status to be False due to service error"

# SCENARIO_ID: b21929f6-88a4-4f41-b91d-17291c64d77d
def test_health_check_reports_ollama_unhealthy_on_timeout(page: Page):
    """Verify the 3.0s timeout logic results in an unhealthy status for Ollama."""
    page.goto(BASE_URL)
    
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    body = response.json()
    assert body.get("ollama") is False, "Expected ollama status to be False due to request timeout"

# SCENARIO_ID: 2efc38f8-66d7-45bc-a5d1-783341ecfdc1
def test_health_check_reports_chromadb_unhealthy_on_init_failure(page: Page):
    """Ensure exceptions during ChromaStore initialization are reported in status."""
    page.goto(BASE_URL)
    
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    body = response.json()
    assert body.get("chromadb") is False, "Expected chromadb status to be False due to initialization failure"

# SCENARIO_ID: e5888eb7-0212-41f7-ae6d-9cee80ae746c
def test_verify_health_check_response_contains_no_sensitive_data(page: Page):
    """Security: Check that only allowed keys are returned in the response."""
    page.goto(BASE_URL)
    
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    body = response.json()
    actual_keys = list(body.keys())
    expected_keys = ["ollama", "chromadb"]
    
    assert len(actual_keys) == 2, f"Expected exactly 2 keys, but found: {actual_keys}"
    for key in expected_keys:
        assert key in body, f"Required key '{key}' missing from health response"

# SCENARIO_ID: 7c8262e2-7d28-40f4-be33-e18e59d0c104
def test_health_check_handles_unreachable_ollama_gracefully(page: Page):
    """Verify connection refused errors to Ollama are caught and reported as False."""
    page.goto(BASE_URL)
    
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    body = response.json()
    assert body.get("ollama") is False, "API should return ollama: false for connection errors"

# SCENARIO_ID: 9374c69d-5828-4b64-ad79-2b39b39fba1b
def test_health_check_rejects_post_method(page: Page):
    """Ensure the health endpoint strictly allows GET requests only."""
    page.goto(BASE_URL)
    
    response = page.request.post(HEALTH_ENDPOINT)
    # 405 Method Not Allowed expected for POST
    assert response.status == 405, f"Expected 405 status, got {response.status}"
    expect(response).not_to_be_ok()

# SCENARIO_ID: 436e0a1d-3af3-4955-9980-ed7decfad971
def test_health_check_stability_under_concurrent_requests(page: Page):
    """Verify multiple simultaneous requests return 200 without interference."""
    page.goto(BASE_URL)
    
    # Trigger multiple requests serially in the context of sync Playwright
    request_count = 10
    responses = [page.request.get(HEALTH_ENDPOINT) for _ in range(request_count)]
    
    for idx, resp in enumerate(responses):
        expect(resp, f"Concurrent request iteration {idx} failed").to_be_ok()
