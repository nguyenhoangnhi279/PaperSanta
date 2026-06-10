# test/test_pdf_service.py
import pytest
import uuid

def test_get_pdf_list(client):
    """Test lấy danh sách PDF"""
    # Cái này trong router là @router.get("/") nên phải có dấu /
    response = client.get("/api/pdf/")
    assert response.status_code == 200

def test_upload_invalid_file_type(client):
    """Test chặn file không phải PDF"""
    files = {"file": ("test.txt", b"Day la file text", "text/plain")}
    # SỬA ĐÚNG TÊN API THÊM CHỮ /upload
    response = client.post("/api/pdf/upload", files=files)
    assert response.status_code == 400

def test_upload_large_file(client):
    """Test từ chối file vượt dung lượng (HTTP 413)"""
    large_content = b"0" * (51 * 1024 * 1024)
    files = {"file": ("big_paper.pdf", large_content, "application/pdf")}
    # SỬA ĐÚNG TÊN API THÊM CHỮ /upload
    response = client.post("/api/pdf/upload", files=files)
    assert response.status_code == 413

def test_cross_user_access_denied(client):
    """Test truy cập doc_id của user khác trả về 404"""
    # Phải truyền đúng định dạng UUID để không bị lỗi 422
    fake_uuid = str(uuid.uuid4())
    response = client.get(f"/api/pdf/{fake_uuid}")
    assert response.status_code == 404