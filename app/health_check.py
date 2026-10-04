import requests


def check_health(url: str) -> bool:
    try:
        response = requests.get(url, timeout=5)

        if response.status_code == 200:
            return True

        return False

    except requests.RequestException:
        return False