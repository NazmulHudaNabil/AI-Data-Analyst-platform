from fastapi.testclient import TestClient
import sys
import os

# Ensure the backend directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "online" in data["message"].lower()

def test_get_connections_empty():
    response = client.get("/api/v1/connections")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_add_connection():
    payload = {
        "name": "Test DB",
        "connection_string": "postgresql://test_user:pass@localhost/testdb"
    }
    response = client.post("/api/v1/connections", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test DB"
    assert "id" in data
    
    # Store ID globally so the delete test can use it
    global test_conn_id
    test_conn_id = data["id"]

def test_delete_connection():
    # Delete the connection created in the previous test
    response = client.delete(f"/api/v1/connections/{test_conn_id}")
    assert response.status_code == 200
    assert "deleted successfully" in response.json()["message"]
    
    # Verify it is actually deleted
    verify_response = client.get("/api/v1/connections")
    connections = verify_response.json()
    assert not any(conn["id"] == test_conn_id for conn in connections)
