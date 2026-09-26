from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models import Base


# Test database: SQLite in memory
TEST_DATABASE_URL = "sqlite://"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
)


# Create tables in the test database
Base.metadata.create_all(bind=test_engine)


# Provide a test database session
def override_get_db():
    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()


# Replace the application's database dependency
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "Active"}


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "This is the Release Guard"
    }


def test_version_endpoint():
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {
        "version": "0.0.1"
    }


def test_create_order():
    payload = {
        "customer_name": "Rameshwar",
        "item": "Laptop",
        "quantity": 1
    }

    response = client.post("/order", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["customer_name"] == "Rameshwar"
    assert data["item"] == "Laptop"
    assert data["quantity"] == 1
    assert data["status"] == "PENDING"
    assert "id" in data

def test_create_release():
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response = client.post("/release", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert data["version"] == "1.0.0"
    assert data["environment"] == "production"
    assert data["deployment_status"] == "SUCCESS"
    assert data["health_status"] == "HEALTHY"
    assert data["commit_sha"] == "a7f3c92"
    assert "id" in data

def test_get_release():
    payload = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "b82d1f4"
    }

    create_response = client.post("/release", json=payload)

    release_id = create_response.json()["id"]

    response = client.get(f"/releases/{release_id}")

    assert response.status_code == 200
    assert response.json()["version"] == "2.0.0"
    assert response.json()["commit_sha"] == "b82d1f4"


def test_get_nonexistent_release():
    response = client.get("/releases/9999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Release not found"}

