import pytest

def test_health_check(client):
    """Test API kiểm tra trạng thái hệ thống"""
    # Gọi đúng đường dẫn /health (không có dấu / ở cuối)
    response = client.get("/health")
    
    # Kiểm tra mã trạng thái phải là 200 OK
    assert response.status_code == 200
    
    # Lấy dữ liệu JSON trả về
    data = response.json()
    
    # Kiểm tra các trường dữ liệu khớp với code thật của mày
    assert data["status"] == "ok"
    assert "app" in data
    assert "embedding" in data