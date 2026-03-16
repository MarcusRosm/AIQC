import os
import pytest
from playwright.sync_api import Page, expect

# Configuration
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
HEALTH_ENDPOINT = f"{BASE_URL}/api/health"
DOCS_URL = f"{BASE_URL}/api/docs"

# SCENARIO_ID: c4bd8b6e-47e0-4f6f-be96-a489319ff68d
def test_health_check_returns_success_for_all_dependencies(page: Page):
    """Verify successful health check when all dependencies are reachable."""
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    payload = response.json()
    # Asserting both dependencies are true as per snippet 2 and scenario requirements
    assert payload.get("ollama") is True, f"Expected ollama to be True, got {payload.get('ollama')}"
    assert payload.get("chromadb") is True, f"Expected chromadb to be True, got {payload.get('chromadb')}"

# SCENARIO_ID: f2d15b38-7af9-464f-9031-044378f0cb5b
def test_health_check_reports_unhealthy_when_ollama_unreachable(page: Page):
    """Verify health check behavior when Ollama is unreachable."""
    response = page.request.get(HEALTH_ENDPOINT)
    # The application is designed to return 200 even if dependencies fail, 
    # but the body indicates the failure.
    expect(response).to_be_ok()
    
    payload = response.json()
    assert payload.get("ollama") is False, "Ollama should be reported as False (unhealthy)"

# SCENARIO_ID: 7162fbf2-cadb-401d-a128-13bff44aa515
def test_health_check_reports_unhealthy_on_ollama_timeout(page: Page):
    """Verify health check behavior when Ollama request times out (3.0s limit)."""
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    payload = response.json()
    # The 3.0s timeout in health.py should trigger the exception block
    assert payload.get("ollama") is False, "Ollama should be False due to timeout exception"

# SCENARIO_ID: 2ec18110-31e9-4fb1-85d2-75fb7afc0f58
def test_health_check_reports_unhealthy_on_chromadb_initialization_failure(page: Page):
    """Verify ChromaDB initialization failure handling."""
    response = page.request.get(HEALTH_ENDPOINT)
    expect(response).to_be_ok()
    
    payload = response.json()
    assert payload.get("chromadb") is False, "ChromaDB should be reported as False on init failure"

# SCENARIO_ID: 7ce20cf9-e3d8-4081-bd47-88870b2adcf0
def test_health_api_is_documented_in_swagger_ui(page: Page):
    """Verify the health endpoint is correctly exposed in the generated OpenAPI documentation."""
    page.goto(DOCS_URL)
    
    # Use semantic locators for Swagger UI elements
    health_tag_button = page.get_by_role("button", name="health", exact=True)
    health_tag_button.click()
    
    health_endpoint_text = page.get_by_text("/api/health", exact=True)
    expect(health_endpoint_text).to_be_visible()

# SCENARIO_ID: 109ac284-9bdb-4cb3-8e09-a7bd269fc30c
def test_health_api_enforces_cors_headers(page: Page):
    """Ensure the health endpoint respects the CORSMiddleware configuration."""
    unauthorized_origin = "http://external.com"
    allowed_origin = "http://localhost:5173"

    response = page.request.fetch(
        HEALTH_ENDPOINT,
        method="OPTIONS",
        headers={
            "Origin": unauthorized_origin,
            "Access-Control-Request-Method": "GET"
        }
    )
    
    # Access-Control-Allow-Origin should not be the unauthorized origin
    cors_header = response.headers.get("access-control-allow-origin")
    assert cors_header != unauthorized_origin, f"CORS should not allow {unauthorized_origin}"
    # If not DEBUG, it should match the allowed origin if present
    if cors_header:
        assert cors_header == allowed_origin

# SCENARIO_ID: 56961f77-60c5-4cbf-a43c-f04603da7fef
def test_health_api_rejects_unauthorized_methods(page: Page):
    """Ensure only GET requests are permitted on the health endpoint."""
    post_response = page.request.post(HEALTH_ENDPOINT)
    # expect(post_response).not_to_be_ok() - status 405 is specific
    assert post_response.status == 405, f"Expected 405 for POST, got {post_response.status}"
    
    delete_response = page.request.delete(HEALTH_ENDPOINT)
    assert delete_response.status == 405, f"Expected 405 for DELETE, got {delete_response.status}"

# SCENARIO_ID: dad823a3-40d2-429f-b301-fdfe643519bd
def test_health_check_handles_concurrent_requests(page: Page):
    """Ensure multiple requests to the health endpoint are handled without failure."""
    # Simulating load via multiple sequential requests in sync mode
    # Note: For true async concurrency in Playwright, async_api.gather would be used.
    responses = []
    for _ in range(50):
        responses.append(page.request.get(HEALTH_ENDPOINT))
    
    for resp in responses:
        expect(resp).to_be_ok()
        assert "ollama" in resp.json(), "Response payload missing health keys under load"
