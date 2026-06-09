# test/test_analyze.py
import pytest
import uuid

def test_analyzer_requires_at_least_two_pdfs(client):
    """Test chức năng phân tích bắt buộc phải có từ 2 PDF trở lên"""
    payload = {
        "pdf_ids": [str(uuid.uuid4())], # Chỉ truyền đúng 1 file
        "analysis_type": "benchmark_matrix"
    }
    
    response = client.post("/api/analyze/run", json=payload)
    
    assert response.status_code == 400

def test_invalid_analysis_type(client):
    """Test loại phân tích không hợp lệ bị reject"""
    payload = {
        "pdf_ids": [str(uuid.uuid4()), str(uuid.uuid4())], # Truyền đủ 2 file
        "analysis_type": "loai_phan_tich_ma_dao_nao_do"    # Nhưng loại phân tích xạo
    }
    
    response = client.post("/api/analyze/run", json=payload)
    
    assert response.status_code in [404, 422]