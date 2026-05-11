from __future__ import annotations

import json
from typing import Any

import httpx

from app.models import IssueRecommendation
from app.scoring import fallback_reason


class GroqReasoner:
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float = 20.0):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def explain(self, issues: list[IssueRecommendation]) -> dict[str, str]:
        if not issues:
            return {}
        if not self.api_key:
            return {issue.html_url: fallback_reason(issue) for issue in issues}

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You write concise recommendation reasons for open source issue matches. "
                        "Return only a valid JSON array. Each item must have url and reason keys. "
                        "Each reason must be one sentence under 28 words."
                    ),
                },
                {"role": "user", "content": json.dumps(self._prompt_items(issues), ensure_ascii=True)},
            ],
            "temperature": 0.2,
            "max_completion_tokens": 900,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout_seconds)) as client:
                response = await client.post(self.endpoint, headers=headers, json=payload)
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return self._parse_response(content, issues)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, TypeError, ValueError):
            return {issue.html_url: fallback_reason(issue) for issue in issues}

    def _prompt_items(self, issues: list[IssueRecommendation]) -> dict[str, Any]:
        return {
            "skill_profile": [
                "Python",
                "PyTorch",
                "TensorFlow",
                "Keras",
                "HuggingFace",
                "FastAPI",
                "NLP",
                "Computer Vision",
                "RAG",
                "LLMs",
                "scikit-learn",
                "Docker",
                "PostgreSQL",
                "Pandas",
                "NumPy",
                "MLOps",
            ],
            "issues": [
                {
                    "url": issue.html_url,
                    "title": issue.title,
                    "repository": issue.repository,
                    "labels": issue.labels,
                    "matched_skills": issue.matched_skills,
                    "comments": issue.comments,
                    "score": issue.score,
                    "score_breakdown": issue.score_breakdown.model_dump()
                    if hasattr(issue.score_breakdown, "model_dump")
                    else issue.score_breakdown.dict(),
                    "repo_stars": issue.repo_stars,
                    "repo_language": issue.repo_language,
                }
                for issue in issues
            ],
        }

    def _parse_response(self, content: str, issues: list[IssueRecommendation]) -> dict[str, str]:
        start = content.find("[")
        end = content.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON array found")
        parsed = json.loads(content[start : end + 1])
        reasons: dict[str, str] = {}
        allowed_urls = {issue.html_url for issue in issues}
        for item in parsed:
            url = str(item.get("url", ""))
            reason = " ".join(str(item.get("reason", "")).split())
            if url in allowed_urls and reason:
                reasons[url] = reason[:320]
        for issue in issues:
            reasons.setdefault(issue.html_url, fallback_reason(issue))
        return reasons
