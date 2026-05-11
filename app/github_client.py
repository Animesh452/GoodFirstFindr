from __future__ import annotations

import asyncio
from typing import Any

import httpx


class GitHubClient:
    base_url = "https://api.github.com"

    def __init__(self, token: str | None = None, timeout_seconds: float = 15.0):
        self.token = token
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "GitHubClient":
        self._client = httpx.AsyncClient(
            headers=self._headers(),
            timeout=httpx.Timeout(self.timeout_seconds),
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
        self._client = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "GoodFirstFindr",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._client:
            async with httpx.AsyncClient(headers=self._headers(), timeout=self.timeout_seconds) as client:
                response = await client.get(url, params=params)
        else:
            response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def search_good_first_issues(self, keyword: str, per_page: int = 40) -> dict[str, Any]:
        query = self._build_query(keyword, exclude_linked_prs=True)
        params = {
            "q": query,
            "sort": "updated",
            "order": "desc",
            "per_page": max(1, min(per_page, 100)),
        }
        try:
            return await self._get(f"{self.base_url}/search/issues", params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 422:
                raise
            params["q"] = self._build_query(keyword, exclude_linked_prs=False)
            return await self._get(f"{self.base_url}/search/issues", params=params)

    def _build_query(self, keyword: str, exclude_linked_prs: bool) -> str:
        parts = ['is:issue', 'is:open', 'label:"good first issue"', 'no:assignee']
        if exclude_linked_prs:
            parts.append("-linked:pr")
        cleaned_keyword = " ".join(keyword.split())
        if cleaned_keyword:
            parts.append(cleaned_keyword)
        return " ".join(parts)

    async def fetch_repositories(self, repository_urls: list[str]) -> dict[str, dict[str, Any]]:
        unique_urls = list(dict.fromkeys(url for url in repository_urls if url))
        semaphore = asyncio.Semaphore(8)

        async def fetch_one(url: str) -> tuple[str, dict[str, Any]]:
            async with semaphore:
                try:
                    return url, await self._get(url)
                except httpx.HTTPError:
                    return url, {}

        results = await asyncio.gather(*(fetch_one(url) for url in unique_urls))
        return dict(results)


def is_available_issue(issue: dict[str, Any]) -> bool:
    if issue.get("pull_request"):
        return False
    if issue.get("assignee"):
        return False
    if issue.get("assignees"):
        return False
    return True
