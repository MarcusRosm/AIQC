"""Integration tests – FastAPI routes"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "AI-Driven QA Platform" in data["message"]


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "ollama" in data
    assert "chromadb" in data


@pytest.mark.asyncio
async def test_reports_empty_list(client: AsyncClient) -> None:
    resp = await client.get("/api/reports")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_reports_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/reports/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_pipeline_run_returns_run_id(client: AsyncClient) -> None:
    body = {
        "diff_text": "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x=1\n+x=2\n",
        "skip_healing": True,
    }
    resp = await client.post("/api/pipeline/run", json=body)
    assert resp.status_code == 202
    data = resp.json()
    assert "run_id" in data


@pytest.mark.asyncio
async def test_pipeline_status_not_found(client: AsyncClient) -> None:
    resp = await client.get("/api/pipeline/status/nonexistent-run-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_openapi_schema_available(client: AsyncClient) -> None:
    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
