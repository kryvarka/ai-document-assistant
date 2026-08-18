import pytest

pytestmark = pytest.mark.asyncio


async def _token(client, email: str) -> str:
    response = await client.post(
        "/api/auth/register",
        json={"name": "Ingest User", "email": email, "password": "password123"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


async def test_upload_returns_immediately_then_settles_ready(client, stub_vector_store):
    token = await _token(client, "ingest.ready@docqa.ai")

    upload = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.md", b"# Report\n\nRevenue grew by 42 percent.", "text/markdown")},
    )

    assert upload.status_code == 202
    assert upload.json()["status"] == "processing"
    assert upload.json()["chunk_count"] == 0

    listed = await client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    document = listed.json()["documents"][0]
    assert document["status"] == "ready"
    assert document["chunk_count"] >= 1
    assert document["error_message"] is None
    stub_vector_store.aadd_documents.assert_awaited_once()


async def test_unreadable_document_settles_failed_with_reason(client, stub_vector_store):
    token = await _token(client, "ingest.failed@docqa.ai")

    upload = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("broken.pdf", b"this is definitely not a pdf", "application/pdf")},
    )
    assert upload.status_code == 202

    listed = await client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
    document = listed.json()["documents"][0]
    assert document["status"] == "failed"
    assert document["error_message"]
    assert document["chunk_count"] == 0
    stub_vector_store.aadd_documents.assert_not_awaited()


async def test_failed_ingestion_does_not_break_later_uploads(client, stub_vector_store):
    token = await _token(client, "ingest.mixed@docqa.ai")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("broken.pdf", b"not a pdf", "application/pdf")},
    )
    await client.post(
        "/api/documents/upload",
        headers=headers,
        files={"file": ("good.txt", b"Latency budget is 250 milliseconds.", "text/plain")},
    )

    listed = await client.get("/api/documents", headers=headers)
    statuses = {d["filename"]: d["status"] for d in listed.json()["documents"]}
    assert statuses == {"broken.pdf": "failed", "good.txt": "ready"}


async def test_unsupported_extension_is_rejected_at_upload(client):
    token = await _token(client, "ingest.badtype@docqa.ai")

    upload = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
    )

    assert upload.status_code == 422
    assert "Unsupported file type" in upload.json()["detail"]


async def test_empty_file_is_rejected_at_upload(client):
    token = await _token(client, "ingest.empty@docqa.ai")

    upload = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("empty.txt", b"", "text/plain")},
    )

    assert upload.status_code == 422
    assert "empty" in upload.json()["detail"].lower()
