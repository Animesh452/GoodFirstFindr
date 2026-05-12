from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

import httpx

from app.models import IssueRecommendation
from app.scoring import fallback_reason


@dataclass(frozen=True)
class IssueAnalysis:
    fit_score: float
    primary_language: str
    red_flags: list[str] = field(default_factory=list)
    reason: str = ""


class GroqReasoner:
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float = 20.0):
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def explain(
        self,
        issues: list[IssueRecommendation],
        descriptions: dict[str, str] | None = None,
    ) -> dict[str, IssueAnalysis]:
        if not issues:
            return {}
        if not self.api_key:
            return self._fallback_analyses(issues)

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Analyze open source GitHub issues against a Python-heavy ML/backend skill profile. "
                        "Read the issue description, not just labels or repository metadata. "
                        "Return only a valid JSON array. Each item must have exactly these keys: "
                        "url, fit_score, primary_language, red_flags, reason. "
                        "fit_score must be an integer from 0 to 100. "
                        "primary_language must be the main implementation language required by the issue, "
                        "or any if language is not important. "
                        "red_flags must be an array of short strings for concerns like written in Go, "
                        "requires JS, already has PR, already claimed, or unclear requirements. "
                        "reason must be exactly one full sentence between 15 and 28 words explaining "
                        "specifically why this issue matches or does not match the skill profile. "
                        "Never write fewer than 10 words. Bad example: 'Python ML resources'. "
                        "Good example: 'Strong fit for PyTorch and NLP skills with an active repo "
                        "and no competing claimants.'"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        self._prompt_items(issues, descriptions or {}),
                        ensure_ascii=True,
                    ),
                },
            ],
            "temperature": 0.2,
            "max_completion_tokens": 1200,
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
            print(f"[DEBUG] Groq raw response: {content[:500]}")
            return self._parse_response(content, issues)
        except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, TypeError, ValueError):
            return self._fallback_analyses(issues)

    def _prompt_items(
        self,
        issues: list[IssueRecommendation],
        descriptions: dict[str, str],
    ) -> dict[str, Any]:
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
                    "description": self._trim_description(descriptions.get(issue.html_url, "")),
                }
                for issue in issues
            ],
        }

    def _parse_response(self, content: str, issues: list[IssueRecommendation]) -> dict[str, IssueAnalysis]:
        start = content.find("[")
        end = content.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON array found")
        parsed = json.loads(content[start : end + 1])
        analyses: dict[str, IssueAnalysis] = {}
        issues_by_url = {issue.html_url: issue for issue in issues}
        for item in parsed:
            url = str(item.get("url", ""))
            reason = " ".join(str(item.get("reason", "")).split())
            if url in issues_by_url and reason:
                analyses[url] = IssueAnalysis(
                    fit_score=self._coerce_score(item.get("fit_score"), issues_by_url[url].score),
                    primary_language=self._coerce_language(item.get("primary_language")),
                    red_flags=self._coerce_red_flags(item.get("red_flags")),
                    reason=reason[:320],
                )
        fallbacks = self._fallback_analyses(issues)
        for issue in issues:
            analyses.setdefault(issue.html_url, fallbacks[issue.html_url])
        return analyses

    def _fallback_analyses(self, issues: list[IssueRecommendation]) -> dict[str, IssueAnalysis]:
        return {
            issue.html_url: IssueAnalysis(
                fit_score=issue.score,
                primary_language="any",
                red_flags=[],
                reason=fallback_reason(issue),
            )
            for issue in issues
        }

    def _trim_description(self, description: str) -> str:
        cleaned = " ".join(description.split())
        return cleaned[:800]

    def _coerce_score(self, value: object, default: float = 0.0) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = default
        return max(0.0, min(100.0, score))

    def _coerce_language(self, value: object) -> str:
        language = " ".join(str(value or "any").split())
        return language[:60] or "any"

    def _coerce_red_flags(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        flags: list[str] = []
        for flag in value:
            cleaned = " ".join(str(flag).split())
            if cleaned:
                flags.append(cleaned[:80])
        return flags[:8]
