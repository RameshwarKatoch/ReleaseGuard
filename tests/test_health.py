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
