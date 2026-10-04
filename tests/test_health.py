from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
# pyrefly: ignore [missing-import]
import pytest
from app.health_check import check_health
from app.main import app
from app.database import get_db
from app.models import Base
from unittest.mock import patch
import requests
from app.deployment import trigger_deployment, get_latest_rollback_run ,get_workflow_run_status

# Test database: SQLite in memor
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


Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)  

def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "Active"}


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {"message": "This is the Release Guard"}


def test_version_endpoint():
    response = client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "0.0.1"}


def test_create_order():
    payload = {"customer_name": "Rameshwar", "item": "Laptop", "quantity": 1}

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
        "commit_sha": "a7f3c92",
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
        "commit_sha": "b82d1f4",
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


def test_previous_healthy_release():
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92",
    }

    create_response = client.post("/release", json=payload)
    release1_id = create_response.json()["id"]

    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNHEALTHY",
        "commit_sha": "b82d1f4",
    }
    response2 = client.post("/release", json=payload2)
    release2_id = response2.json()["id"]

    response = client.get(f"/releases/{release2_id}/previous-healthy")
    assert response.status_code == 200
    assert response.json()["id"] == release1_id
    assert response.json()["version"] == "1.0.0"
    assert response.json()["health_status"] == "HEALTHY"
    assert response.json()["commit_sha"] == "a7f3c92"


def test_rollback_target():
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92",
    }
    create_response = client.post("/release", json=payload)
    healthy_release = create_response.json()["id"]

    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNHEALTHY",
        "commit_sha": "b82d1f4",
    }
    response2 = client.post("/release", json=payload2)
    unhealthy_release = response2.json()["id"]

    response = client.get(f"/releases/{unhealthy_release}/rollback-target")

    assert response.status_code == 200
    assert response.json()["rollback_to_release_id"] == healthy_release
    assert response.json()["version"] == "1.0.0"
    assert response.json()["commit_sha"] == "a7f3c92"


def test_rollback_release():
    # Create healthy release
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response1 = client.post("/release", json=payload)
    healthy_release_id = response1.json()["id"]

    # Create unhealthy release
    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNHEALTHY",
        "commit_sha": "b82d1f4"
    }

    response2 = client.post("/release", json=payload2)
    unhealthy_release_id = response2.json()["id"]

    # Request rollback
    response = client.post(
        f"/releases/{unhealthy_release_id}/rollback"
    )

    # Check response
    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Rollback completed"
    assert data["rolled_back_release_id"] == unhealthy_release_id
    assert data["rollback_target_id"] == healthy_release_id
    assert data["rollback_version"] == "1.0.0"
    assert data["rollback_commit_sha"] == "a7f3c92"

def test_rollback_not_required_for_healthy_release():
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response = client.post("/release", json=payload)

    release_id = response.json()["id"]

    response = client.post(
        f"/releases/{release_id}/rollback"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Rollback not required"
    assert data["release_id"] == release_id

def test_rollback_when_no_target_exists():
    payload = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNHEALTHY",
        "commit_sha": "b82d1f4"
    }

    response = client.post("/release", json=payload)

    release_id = response.json()["id"]

    response = client.post(
        f"/releases/{release_id}/rollback"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "No rollback target found"
    }

def test_check_health_success():
    result = check_health("http://localhost:8000/health")

    assert result is True

def test_check_health_failure():
    with patch("app.health_check.requests.get") as mock_get:
        mock_get.return_value.status_code = 500

        result = check_health("http://fake-url/health")

        assert result is False

def test_check_health_server_unreachable():
    with patch("app.health_check.requests.get") as mock_get:
        mock_get.side_effect = requests.RequestException

        result = check_health("http://fake-url/health")

        assert result is False

def test_check_application_health():
    response = client.get(
        "/check-health",
        params={"url": "http://localhost:8000/health"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "HEALTHY"
    }

def test_check_application_health_healthy():
    with patch("app.main.check_health") as mock_check:
        mock_check.return_value = True

        response = client.get(
            "/check-health",
            params={"url": "http://fake-url/health"}
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "HEALTHY"
        }

def test_check_application_health_unhealthy():
    with patch("app.main.check_health") as mock_check:
        mock_check.return_value = False

        response = client.get(
            "/check-health",
            params={"url": "http://fake-url/health"}
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "UNHEALTHY"
        }

def test_check_release_health_healthy():
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNHEALTHY",
        "commit_sha": "a7f3c92"
    }

    create_response = client.post(
        "/release",
        json=payload
    )

    release_id = create_response.json()["id"]

    with patch("app.main.check_health") as mock_check:
        mock_check.return_value = True

        response = client.post(
            f"/releases/{release_id}/check-health",
            params={"url": "http://fake-url/health"}
        )

    assert response.status_code == 200

    data = response.json()

    assert data["release_id"] == release_id
    assert data["health_status"] == "HEALTHY"


def test_check_release_health_unhealthy():
    payload = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "b82d1f4"
    }

    create_response = client.post(
        "/release",
        json=payload
    )

    release_id = create_response.json()["id"]

    with patch("app.main.check_health") as mock_check:
        mock_check.return_value = False

        response = client.post(
            f"/releases/{release_id}/check-health",
            params={"url": "http://fake-url/health"}
        )

    assert response.status_code == 200

    data = response.json()

    assert data["release_id"] == release_id
    assert data["health_status"] == "UNHEALTHY"

def test_auto_rollback_healthy_release():
    payload = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    create_response = client.post(
        "/release",
        json=payload
    )

    release_id = create_response.json()["id"]

    with patch("app.main.check_health") as mock_check:
        mock_check.return_value = True

        response = client.post(
            f"/releases/{release_id}/auto-rollback",
            params={"url": "http://fake-url/health"}
        )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Release is healthy"
    assert data["health_status"] == "HEALTHY"
    assert data["rollback_required"] is False

def test_auto_rollback_unhealthy_release():
    # Create previous healthy release
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response1 = client.post(
        "/release",
        json=payload
    )

    healthy_release_id = response1.json()["id"]

    # Create current release
    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    response2 = client.post(
        "/release",
        json=payload2
    )

    unhealthy_release_id = response2.json()["id"]

    # Simulate failed health check
    with patch("app.main.check_health") as mock_check:
        mock_check.side_effect = [False, True]
        with patch("app.main.trigger_deployment") as mock_deployment:
            mock_deployment.return_value = True
            with patch("app.main.wait_for_rollback_run") as mock_run:
                mock_run.return_value = 12345
                with patch("app.main.wait_for_rollback_completion") as mock_completion:
                    mock_completion.return_value = True
                    response = client.post(
                        f"/releases/{unhealthy_release_id}/auto-rollback",
                        params={"url": "http://fake-url/health"}
                    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Automatic rollback completed"
    assert data["health_status"] == "HEALTHY"
    assert data["rollback_required"] is True
    assert data["rollback_target_id"] == healthy_release_id
    assert data["rollback_version"] == "1.0.0"
    assert data["rollback_commit_sha"] == "a7f3c92"

def test_auto_rollback_no_target():
    payload = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    response1 = client.post(
        "/release",
        json=payload
    )

    release_id = response1.json()["id"]

    with patch("app.main.check_health") as mock_check:
        mock_check.return_value = False

        response = client.post(
            f"/releases/{release_id}/auto-rollback",
            params={"url": "http://fake-url/health"}
        )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "No rollback target found"
    }

def test_trigger_deployment():
    with patch("app.deployment.os.getenv") as mock_env, \
         patch("app.deployment.requests.post") as mock_post:
        mock_env.return_value = "fake-token"
        mock_post.return_value.status_code = 204
        result = trigger_deployment("a7f3c92")

    assert result is True

def test_auto_rollback_deployment_failure():
    # Create previous healthy release
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response1 = client.post(
        "/release",
        json=payload
    )

    healthy_release_id = response1.json()["id"]

    # Create unhealthy release
    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    response2 = client.post(
        "/release",
        json=payload2
    )

    unhealthy_release_id = response2.json()["id"]

    # Simulate health check failure
    with patch("app.main.check_health") as mock_health:
        mock_health.return_value = False

        # Simulate deployment trigger failure
        with patch("app.main.trigger_deployment") as mock_deployment:
            mock_deployment.return_value = False

            response = client.post(
                f"/releases/{unhealthy_release_id}/auto-rollback",
                params={"url": "http://fake-url/health"}
            )

    assert response.status_code == 500

    assert response.json() == {
        "detail": "Rollback deployment failed to start"
    }

def test_auto_rollback_uses_correct_commit():
    # Create previous healthy release
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response1 = client.post("/release", json=payload)
    healthy_release_id = response1.json()["id"]

    # Create current unhealthy release
    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    response2 = client.post("/release", json=payload2)
    unhealthy_release_id = response2.json()["id"]

    with patch("app.main.check_health") as mock_health:
        mock_health.side_effect = [False, True]

        with patch("app.main.trigger_deployment") as mock_deployment:
            mock_deployment.return_value = True
            with patch("app.main.wait_for_rollback_run") as mock_run:
                mock_run.return_value = 12345
                with patch("app.main.wait_for_rollback_completion") as mock_completion:
                    mock_completion.return_value = True
                    response = client.post(
                        f"/releases/{unhealthy_release_id}/auto-rollback",
                        params={"url": "http://fake-url/health"}
                    )

    assert response.status_code == 200

    mock_deployment.assert_called_once_with("a7f3c92")

def test_auto_rollback_success():
    # Create previous healthy release
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response1 = client.post(
        "/release",
        json=payload
    )

    healthy_release_id = response1.json()["id"]

    # Create current release
    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    response2 = client.post(
        "/release",
        json=payload2
    )

    unhealthy_release_id = response2.json()["id"]

    # Simulate unhealthy application
    with patch("app.main.check_health") as mock_health:
        mock_health.side_effect = [False, True]

        # Simulate successful rollback deployment
        with patch("app.main.trigger_deployment") as mock_deployment:
            mock_deployment.return_value = True
            with patch("app.main.wait_for_rollback_run") as mock_run:
                mock_run.return_value = 12345
                with patch("app.main.wait_for_rollback_completion") as mock_completion:
                    mock_completion.return_value = True
                    response = client.post(
                        f"/releases/{unhealthy_release_id}/auto-rollback",
                        params={"url": "http://fake-url/health"}
                    )

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == "Automatic rollback completed"
    assert data["health_status"] == "HEALTHY"
    assert data["rollback_required"] is True
    assert data["rollback_target_id"] == healthy_release_id
    assert data["rollback_version"] == "1.0.0"
    assert data["rollback_commit_sha"] == "a7f3c92"

def test_auto_rollback_updates_release_status():
    # Create previous healthy release
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response1 = client.post(
        "/release",
        json=payload
    )

    healthy_release_id = response1.json()["id"]

    # Create current release
    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    response2 = client.post(
        "/release",
        json=payload2
    )

    unhealthy_release_id = response2.json()["id"]

    # Simulate failed health check
    with patch("app.main.check_health") as mock_health:
        mock_health.side_effect = [False, True]

        # Simulate successful rollback deployment
        with patch("app.main.trigger_deployment") as mock_deployment:
            mock_deployment.return_value = True
            with patch("app.main.wait_for_rollback_run") as mock_run:
                mock_run.return_value = 12345
                with patch("app.main.wait_for_rollback_completion") as mock_completion:
                    mock_completion.return_value = True
                    response = client.post(
                        f"/releases/{unhealthy_release_id}/auto-rollback",
                        params={"url": "http://fake-url/health"}
                    )

    assert response.status_code == 200

    # Get the release again from the database through the API
    response = client.get(
        f"/releases/{unhealthy_release_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["rollback_status"] == "ROLLED_BACK"

def test_failed_auto_rollback_does_not_update_status():
    # Create previous healthy release
    payload = {
        "version": "1.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "HEALTHY",
        "commit_sha": "a7f3c92"
    }

    response1 = client.post(
        "/release",
        json=payload
    )

    # Create current release
    payload2 = {
        "version": "2.0.0",
        "environment": "production",
        "deployment_status": "SUCCESS",
        "health_status": "UNKNOWN",
        "commit_sha": "b82d1f4"
    }

    response2 = client.post(
        "/release",
        json=payload2
    )

    unhealthy_release_id = response2.json()["id"]

    # Simulate unhealthy application
    with patch("app.main.check_health") as mock_health:
        mock_health.return_value = False

        # Simulate failed deployment trigger
        with patch("app.main.trigger_deployment") as mock_deployment:
            mock_deployment.return_value = False

            response = client.post(
                f"/releases/{unhealthy_release_id}/auto-rollback",
                params={"url": "http://fake-url/health"}
            )

    assert response.status_code == 500

    # Check the release again
    response = client.get(
        f"/releases/{unhealthy_release_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["rollback_status"] == "ROLLBACK_FAILED"
    
def test_trigger_deployment_github_success():
    with patch("app.deployment.requests.post") as mock_post:
        mock_post.return_value.status_code = 204

        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "test-token"}
        ):
            result = trigger_deployment("81c3609")

        assert result is True

        mock_post.assert_called_once()

        call_args = mock_post.call_args

        assert "api.github.com/repos/RameshwarKatoch/ReleaseGuard" in call_args.args[0]

        assert call_args.kwargs["json"] == {
            "ref": "main",
            "inputs": {
                "commit_sha": "81c3609"
            }
        }
def test_trigger_deployment_github_failure():
    with patch("app.deployment.requests.post") as mock_post:
        mock_post.return_value.status_code = 403

        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "test-token"}
        ):
            result = trigger_deployment("81c3609")

        assert result is False

        mock_post.assert_called_once()

def test_trigger_deployment_without_github_token():
    with patch.dict(
        "os.environ",
        {},
        clear=True
    ):
        result = trigger_deployment("81c3609")

    assert result is False

def test_get_latest_rollback_run_success():
    with patch("app.deployment.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "workflow_runs": [
                {
                    "id": 123456789
                }
            ]
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "test-token"}
        ):
            result = get_latest_rollback_run()

        assert result == 123456789
        mock_get.assert_called_once()

def test_get_latest_rollback_run_failure():
    with patch("app.deployment.requests.get") as mock_get:
        mock_get.return_value.status_code = 500

        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "test-token"}
        ):
            result = get_latest_rollback_run()

        assert result is None

def test_get_latest_rollback_run_no_runs():
    with patch("app.deployment.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "workflow_runs": []
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "test-token"}
        ):
            result = get_latest_rollback_run()

        assert result is None

def test_get_workflow_run_status_success():
    with patch("app.deployment.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "completed",
            "conclusion": "success"
        }

        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "test-token"}
        ):
            result = get_workflow_run_status(123456789)

        assert result == {
            "status": "completed",
            "conclusion": "success"
        }

        mock_get.assert_called_once()

def test_get_workflow_run_status_failure():
    with patch("app.deployment.requests.get") as mock_get:
        mock_get.return_value.status_code = 500

        with patch.dict(
            "os.environ",
            {"GITHUB_TOKEN": "test-token"}
        ):
            result = get_workflow_run_status(123456789)

        assert result is None

def test_get_workflow_run_status_without_github_token():
    with patch.dict(
        "os.environ",
        {},
        clear=True
    ):
        result = get_workflow_run_status(123456789)

    assert result is None