from fastapi.testclient import TestClient


def test_cors_post_register_origin_localhost_hop_le(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "cors_user1@example.com",
            "name": "Cors User One",
            "password": "Password123",
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 201
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_post_register_origin_127_0_0_1_hop_le(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "cors_user2@example.com",
            "name": "Cors User Two",
            "password": "Password123",
        },
        headers={"Origin": "http://127.0.0.1:5173"},
    )
    assert response.status_code == 201
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_preflight_options_hop_le(client: TestClient):
    response = client.options(
        "/api/auth/register",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert "content-type" in response.headers.get("access-control-allow-headers", "").lower()


def test_cors_origin_khong_hop_le_bi_tu_choi(client: TestClient):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "cors_bad@example.com",
            "name": "Cors Bad User",
            "password": "Password123",
        },
        headers={"Origin": "http://malicious-site.com"},
    )
    assert response.status_code == 201
    assert "access-control-allow-origin" not in response.headers


def test_cors_preflight_options_origin_khong_hop_le(client: TestClient):
    response = client.options(
        "/api/auth/register",
        headers={
            "Origin": "http://malicious-site.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert "access-control-allow-origin" not in response.headers
