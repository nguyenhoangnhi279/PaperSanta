import pytest

def test_missing_auth_header(client):
    from main import app
    app.dependency_overrides.clear() 
    
    response = client.get("/api/pdf/")
    assert response.status_code == 401

def test_invalid_token_signature(client):
    """Test token xạo / sai chữ ký -> Trả về 401"""
    from main import app
    app.dependency_overrides = {}
    
    headers = {"Authorization": "Bearer fake_and_invalid_token_string"}
    response = client.get("/api/pdf/", headers=headers)
    assert response.status_code == 401