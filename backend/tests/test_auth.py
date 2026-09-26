from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
def test_dang_ki_thanh_cong():
    response=client.post(
        "/register",
        json={
            "email":"user@example.com",
            "password":"123"
        }
    )
    assert response.status_code==201
def test_email_khong_hop_le():
    response=client.post(
        "/register",
        json={
            "email":"abc",
            "password":123
        }
    )
    assert response.status_code==422

def test_mat_khau_de_trong():
    response=client.post(
        "/register",
        json={
            "email": "user@example.com",
            "password": ""
        }
    )
    assert response.status_code == 400
def test_response_khong_chua_password():
    response = client.post(
        "/register",
        json={
            "email": "user@example.com",
            "password": "123"
        }
    )
    du_lieu = response.json()
    assert "password" not in du_lieu
def test_thieu_email():
    response = client.post(
        "/register",
        json={
            "password": "123"
        }
    )

    assert response.status_code == 422
def test_thieu_password():
    response = client.post(
        "/register",
        json={
            "email": "user@example.com"
        }
    )

    assert response.status_code == 422
    