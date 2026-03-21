from __future__ import annotations

import json
import os
from typing import Any, Optional, Union
from urllib.request import Request, urlopen


class GitHubClient:
    def __init__(self, token: Optional[str] = None) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN")

    def configured(self) -> bool:
        return bool(self.token)

    def get_json(self, url: str) -> Union[list[dict[str, Any]], dict[str, Any]]:
        request = Request(url, headers=self._headers())
        with urlopen(request, timeout=20) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "low-vram-institute",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def list_issues(self, owner: str, repo: str, state: str = "open", per_page: int = 20) -> list[dict[str, Any]]:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues?state={state}&per_page={per_page}"
        payload = self.get_json(url)
        assert isinstance(payload, list)
        return [item for item in payload if "pull_request" not in item]
