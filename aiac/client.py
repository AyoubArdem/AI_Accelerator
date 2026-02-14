from aiac.config import get_config, load_config, save_config
from aiac.console import print_info
import requests


class AIACClient:
    def __init__(self, base_path: str = ""):
        self.config = get_config()
        self.tokens = load_config()
        self.base_url = self.config.api_base_url.rstrip("/")
        self.base_path = base_path.strip("/") if base_path else ""

    def _build_url(self, endpoint: str) -> str:
        base = f"{self.base_url}/api"
        if self.base_path:
            base = f"{base}/{self.base_path}"
        return f"{base}/{endpoint.lstrip('/')}"

    def _refresh_access_token(self) -> bool:
        if not self.tokens or "refresh" not in self.tokens:
            return False
        refresh_url = f"{self.base_url}/api/users/token/refresh/"
        try:
            resp = requests.post(refresh_url, json={"refresh": self.tokens["refresh"]})
            if resp.status_code != 200:
                print_info("Refresh token expired. Please login again.")
                return False
            access = resp.json().get("access")
            if not access:
                return False
            self.tokens["access"] = access
            save_config({"access": access, "refresh": self.tokens["refresh"]}, self.base_url)
            print_info("Access token refreshed.")
            return True
        except requests.RequestException:
            return False

    def api_request(self, endpoint: str, method: str = "GET", data: dict = None, files: dict = None, _retried: bool = False):
        endpoint_url = self._build_url(endpoint)
        headers = {}

        if self.tokens and "access" in self.tokens:
            headers["Authorization"] = f"Bearer {self.tokens['access']}"

        try:
            request_kwargs = {
                "method": method,
                "url": endpoint_url,
                "headers": headers,
            }
            if files:
                request_kwargs["data"] = data
                request_kwargs["files"] = files
            else:
                headers["Content-Type"] = "application/json"
                request_kwargs["json"] = data

            response = requests.request(**request_kwargs)
            if response.status_code == 401 and not _retried and self._refresh_access_token():
                return self.api_request(endpoint, method=method, data=data, files=files, _retried=True)
            if response.status_code >= 400:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            return response
        except requests.RequestException as e:
            raise Exception(f"Network error: {str(e)}") from e

    def post(self, endpoint: str, json: dict = None, files: dict = None):
        return self.api_request(endpoint, method="POST", data=json, files=files)

    def get(self, endpoint: str):
        return self.api_request(endpoint, method="GET")

    def delete(self, endpoint: str):
        return self.api_request(endpoint, method="DELETE")
