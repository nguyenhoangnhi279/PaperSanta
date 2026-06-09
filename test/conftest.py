import sys
import os
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

import pytest
from fastapi.testclient import TestClient
from main import app 
from app.core.auth import get_current_user

# Giả lập User đã đăng nhập
def mock_get_current_user():
    return {
        "user_id": "user_khtn_123", 
        "email": "test@student.hcmus.edu.vn"
    }
@pytest.fixture(autouse=True)
def override_dependency():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.clear()

@pytest.fixture(scope="session")  # <--- Bùa chống sập Event Loop
def client():
    with TestClient(app) as c:
        yield c