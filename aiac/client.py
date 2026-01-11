from aiac.config import get_config, load_config
import requests

class AIACClient:
    def __init__(self):
        self.url = get_config()
        self.tokens = load_config()

    def api_request(self, endpoint: str, method: str,data: dict =None):
        endpoint_url = f"{self.url.api_base_url}/{endpoint.lstrip('/')}"
        headers = {}
        if self.tokens and "access" in self.tokens and "refresh" in self.tokens:
            headers["Authorization"] = f"Bearer {self.tokens['access']}"
            response = requests.request(method=method, url=endpoint_url , headers=headers, json=data)
            if response.status_code >= 400 :
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            return response.json()
        else:
            raise Exception("Authentication tokens not found. Please login first.")