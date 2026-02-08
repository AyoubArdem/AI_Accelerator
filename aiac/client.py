from aiac.config import get_config, load_config
import requests
'''
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
'''
from aiac.config import get_config, load_config
import requests


class AIACClient:
    def __init__(self):
        self.config = get_config()
        self.tokens = load_config()

    def api_request(self, endpoint: str, method: str = "GET", data: dict = None):
        # Ensure endpoint is appended cleanly
        endpoint_url = f"{self.config.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {"Content-Type": "application/json"}

        # Add Authorization header if token is available
        if self.tokens and "access" in self.tokens:
            headers["Authorization"] = f"Bearer {self.tokens['access']}"

        try:
            response = requests.request(
                method=method,
                url=endpoint_url,
                headers=headers,
                json=data
            )
            # Raise for HTTP errors
            response.raise_for_status()
            # Return JSON safely
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise Exception(f"API request failed: {response.status_code} - {response.text}") from e
        except requests.RequestException as e:
            raise Exception(f"Network error: {str(e)}") from e

    def post(self, endpoint: str, json: dict = None):
        """Convenience method for POST requests"""
        return self.api_request(endpoint, method="POST", data=json)

    def get(self, endpoint: str):
        """Convenience method for GET requests"""
        return self.api_request(endpoint, method="GET") 
client = AIACClient()

# Register a new user
try:
    result = client.post("api/users/register/", {
        "email": "test@example.com",
        "username": "tester",
        "password": "securepass123",
        "role": "client"
    })
    print(result)
except Exception as e:
    print("Error:", e)

# Fetch schema
try:
    schema = client.get("api/schema/")
    print(schema)
except Exception as e:
    print("Error:", e)