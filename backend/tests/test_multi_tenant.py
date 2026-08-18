import pytest

pytestmark = pytest.mark.asyncio


async def _register(client, email: str, name: str = "Test User") -> str:
    response = await client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": "password123", "role": "Analyst"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


async def test_health_reports_database_and_vector_store(client, monkeypatch):
    from src.services.vector_store import VectorStore

    monkeypatch.setattr(VectorStore, "is_ready", property(lambda self: True))

    response = await client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["database"] == "connected"


async def test_protected_endpoints_reject_anonymous_requests(client):
    for path in ("/api/documents", "/api/conversations", "/api/auth/me"):
        response = await client.get(path)
        assert response.status_code == 401, f"{path} did not require authentication"


async def test_register_login_and_identity_roundtrip(client):
    email = "roundtrip@docqa.ai"
    await _register(client, email)

    login = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert login.status_code == 200
    assert login.json()["token_type"] == "bearer"

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == email


async def test_duplicate_email_registration_is_rejected(client):
    await _register(client, "duplicate@docqa.ai")

    response = await client.post(
        "/api/auth/register",
        json={"name": "Impostor", "email": "duplicate@docqa.ai", "password": "password123"},
    )
    assert response.status_code == 409


async def test_login_with_wrong_password_is_rejected(client):
    await _register(client, "wrongpass@docqa.ai")

    response = await client.post(
        "/api/auth/login", json={"email": "wrongpass@docqa.ai", "password": "not-the-password"}
    )
    assert response.status_code == 401


async def test_tampered_token_is_rejected(client):
    token = await _register(client, "tampered@docqa.ai")

    response = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token[:-4]}AAAA"}
    )
    assert response.status_code == 401


async def test_conversations_are_isolated_between_tenants(client):
    alice = await _register(client, "alice@docqa.ai", "Alice")
    bob = await _register(client, "bob@docqa.ai", "Bob")

    created = await client.post(
        "/api/conversations",
        headers={"Authorization": f"Bearer {alice}"},
        json={"title": "Alice Confidential Session"},
    )
    assert created.status_code == 201
    alice_conversation_id = created.json()["id"]

    listed = await client.get("/api/conversations", headers={"Authorization": f"Bearer {bob}"})
    assert listed.status_code == 200
    assert alice_conversation_id not in [c["id"] for c in listed.json()]

    read = await client.get(
        f"/api/conversations/{alice_conversation_id}",
        headers={"Authorization": f"Bearer {bob}"},
    )
    assert read.status_code == 404

    deleted = await client.delete(
        f"/api/conversations/{alice_conversation_id}",
        headers={"Authorization": f"Bearer {bob}"},
    )
    assert deleted.status_code == 404

    still_there = await client.get(
        f"/api/conversations/{alice_conversation_id}",
        headers={"Authorization": f"Bearer {alice}"},
    )
    assert still_there.status_code == 200


async def test_documents_are_isolated_between_tenants(client, stub_vector_store):
    alice = await _register(client, "alice.docs@docqa.ai", "Alice")
    bob = await _register(client, "bob.docs@docqa.ai", "Bob")

    upload = await client.post(
        "/api/documents/upload",
        headers={"Authorization": f"Bearer {alice}"},
        files={
            "file": (
                "alice-notes.md",
                b"# Alice\n\nQuarterly revenue was 42 million.",
                "text/markdown",
            )
        },
    )
    assert upload.status_code == 202, upload.text
    document_id = upload.json()["id"]

    bob_documents = await client.get("/api/documents", headers={"Authorization": f"Bearer {bob}"})
    assert bob_documents.status_code == 200
    assert bob_documents.json()["total"] == 0

    bob_delete = await client.delete(
        f"/api/documents/{document_id}", headers={"Authorization": f"Bearer {bob}"}
    )
    assert bob_delete.status_code == 404

    alice_documents = await client.get(
        "/api/documents", headers={"Authorization": f"Bearer {alice}"}
    )
    assert [d["id"] for d in alice_documents.json()["documents"]] == [document_id]


async def test_health_reports_degraded_when_vector_store_is_down(client, monkeypatch):
    from src.services.vector_store import VectorStore

    monkeypatch.setattr(VectorStore, "is_ready", property(lambda self: False))

    response = await client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
