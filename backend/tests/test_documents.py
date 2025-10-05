"""
Test document endpoints
"""

import pytest
from httpx import AsyncClient
from io import BytesIO


@pytest.mark.asyncio
async def test_upload_pdf(client: AsyncClient, auth_headers: dict):
    """Test PDF upload"""
    pdf_content = b"%PDF-1.4 fake pdf content"
    
    response = await client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")},
        data={"document_type": "pdf"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "test.pdf"
    assert data["content_type"] == "pdf"
    assert data["status"] in ["pending", "processing", "completed"]


@pytest.mark.asyncio
async def test_list_documents(client: AsyncClient, auth_headers: dict):
    """Test listing documents"""
    response = await client.get("/api/documents", headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total" in data
    assert isinstance(data["data"], list)


@pytest.mark.asyncio
async def test_delete_own_document(client: AsyncClient, auth_headers: dict):
    """Test user can delete their own document"""
    # First upload
    pdf_content = b"%PDF-1.4 test"
    upload_response = await client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("test.pdf", BytesIO(pdf_content), "application/pdf")},
        data={"document_type": "pdf"}
    )
    doc_id = upload_response.json()["id"]
    
    # Then delete
    delete_response = await client.delete(
        f"/api/documents/{doc_id}",
        headers=auth_headers
    )
    
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_upload_unsupported_file(client: AsyncClient, auth_headers: dict):
    """Test uploading unsupported file type fails"""
    exe_content = b"fake executable"
    
    response = await client.post(
        "/api/documents/upload",
        headers=auth_headers,
        files={"file": ("virus.exe", BytesIO(exe_content), "application/exe")},
        data={"document_type": "exe"}
    )
    
    assert response.status_code == 400