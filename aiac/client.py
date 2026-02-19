from aiac.config import get_config, load_config, save_config
from aiac.console import print_info
import requests
import subprocess
import sys
import time
from urllib.parse import urlparse


class AIACClient:
    _server_autostart_attempted = False

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

    def _local_server_addr(self):
        parsed = urlparse(self.base_url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return parsed.scheme, host, port

    def _can_autostart_local_server(self) -> bool:
        scheme, host, _ = self._local_server_addr()
        return scheme == "http" and host in {"127.0.0.1", "localhost"}

    def _autostart_local_server(self) -> bool:
        if AIACClient._server_autostart_attempted:
            return False
        if not self._can_autostart_local_server():
            return False

        AIACClient._server_autostart_attempted = True
        _, host, port = self._local_server_addr()
        command = [
            sys.executable,
            "-m",
            "django",
            "runserver",
            f"{host}:{port}",
            "--settings=AI_Accelerator.settings",
            "--noreload",
        ]
        try:
            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print_info(f"API server not reachable. Starting local server on {host}:{port}...")
            time.sleep(2.0)
            return True
        except Exception:
            return False

    def api_request(self, endpoint: str, method: str = "GET", data: dict = None, files: dict = None, _retried: bool = False, _autostart_retried: bool = False):
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
                return self.api_request(endpoint, method=method, data=data, files=files, _retried=True, _autostart_retried=_autostart_retried)
            if response.status_code >= 400:
                raise Exception(f"API request failed: {response.status_code} - {response.text}")
            return response
        except requests.RequestException as e:
            if (
                not _autostart_retried
                and isinstance(e, requests.ConnectionError)
                and self._autostart_local_server()
            ):
                return self.api_request(
                    endpoint,
                    method=method,
                    data=data,
                    files=files,
                    _retried=_retried,
                    _autostart_retried=True,
                )
            if self._can_autostart_local_server():
                _, host, port = self._local_server_addr()
                raise Exception(
                    f"Network error: {str(e)}. "
                    f"Try running `aiac server run --host {host} --port {port}`."
                ) from e
            raise Exception(f"Network error: {str(e)}") from e

    def post(self, endpoint: str, json: dict = None, files: dict = None):
        return self.api_request(endpoint, method="POST", data=json, files=files)

    def get(self, endpoint: str):
        return self.api_request(endpoint, method="GET")

    def delete(self, endpoint: str):
        return self.api_request(endpoint, method="DELETE")
