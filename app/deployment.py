import os
import requests
import time

GITHUB_OWNER = "RameshwarKatoch"
GITHUB_REPO = "ReleaseGuard"
WORKFLOW_FILE = "rollback.yml"


def trigger_deployment(commit_sha: str) -> bool:
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return False

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/"
        f"{WORKFLOW_FILE}/dispatches"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    payload = {
        "ref": "main",
        "inputs": {
            "commit_sha": commit_sha
        }
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=10
    )

    return response.status_code == 204

def get_latest_rollback_run():
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return None

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/"
        f"{WORKFLOW_FILE}/runs"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    params = {
        "branch": "main",
        "per_page": 1
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=10
    )

    if response.status_code != 200:
        return None

    data = response.json()

    runs = data.get("workflow_runs", [])

    if not runs:
        return None

    return runs[0]["id"]

def get_workflow_run_status(run_id: int):
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return None

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/actions/runs/"
        f"{run_id}"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=10
    )

    if response.status_code != 200:
        return None

    data = response.json()

    return {
        "status": data.get("status"),
        "conclusion": data.get("conclusion")
    }

def wait_for_rollback_run(timeout=30):
    token = os.getenv("GITHUB_TOKEN")

    if not token:
        return None

    url = (
        f"https://api.github.com/repos/"
        f"{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/"
        f"{WORKFLOW_FILE}/runs"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    for _ in range(timeout):
        response = requests.get(
            url,
            headers=headers,
            params={
                "branch": "main",
                "event": "workflow_dispatch",
                "per_page": 1,
            },
            timeout=10,
        )

        if response.status_code != 200:
            return None

        runs = response.json().get("workflow_runs", [])

        if runs:
            return runs[0]["id"]

        time.sleep(1)

    return None

def wait_for_rollback_completion(run_id: int, timeout=120):
    for _ in range(timeout):
        result = get_workflow_run_status(run_id)

        if result is None:
            return False

        if result["status"] == "completed":
            return result["conclusion"] == "success"

        time.sleep(1)

    return False