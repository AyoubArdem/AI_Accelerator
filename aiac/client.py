from aiac.config import get_config, load_config
import requests

class AIACClient:
    def __init__(self):
        self.config = get_config()
        self.tokens = load_config()

    def api_request(self, endpoint: str, method: str = "GET", data: dict = None):
        endpoint_url = f"{self.config.api_base_url}/{endpoint.lstrip('/')}"
        headers = {}
        if self.tokens and "access" in self.tokens:
            headers["Authorization"] = f"Bearer {self.tokens['access']}"

        try:
            response = requests.request(method=method, url=endpoint_url, headers=headers, json=data)
            if response.status_code >= 400:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Network error: {str(e)}")

    def post(self, endpoint: str, json: dict = None):
        """Convenience method for POST requests"""
        return self.api_request(endpoint, method="POST", data=json)

    def get(self, endpoint: str):
        """Convenience method for GET requests"""
        return self.api_request(endpoint, method="GET")