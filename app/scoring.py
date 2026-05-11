from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any

from app.models import IssueRecommendation, ScoreBreakdown


SKILL_PROFILE = [
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
]


SKILL_ALIASES = {
    "Python": ["python", ".py"],
    "PyTorch": ["pytorch", "torch"],
    "TensorFlow": ["tensorflow", "tf.keras"],
    "Keras": ["keras"],
    "HuggingFace": ["huggingface", "hugging face", "transformers", "datasets"],
    "FastAPI": ["fastapi"],
    "NLP": ["nlp", "natural language", "text classification", "tokenizer"],
    "Computer Vision": ["computer vision", "cv", "image", "opencv", "segmentation"],
    "RAG": ["rag", "retrieval augmented", "retriever", "vector store"],
    "LLMs": ["llm", "llms", "large language", "prompt", "chatbot"],
    "scikit-learn": ["scikit-learn", "sklearn"],
    "Docker": ["docker", "dockerfile", "container"],
    "PostgreSQL": ["postgresql", "postgres"],
    "Pandas": ["pandas", "dataframe"],
    "NumPy": ["numpy", "ndarray"],
    "MLOps": ["mlops", "model serving", "deployment", "pipeline", "monitoring"],
}


def parse_github_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _round_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _label_names(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels") or []
    names: list[str] = []
    for label in labels:
        if isinstance(label, dict) and label.get("name"):
            names.append(str(label["name"]))
        elif isinstance(label, str):
            names.append(label)
    return names


def _repo_name_from_issue(issue: dict[str, Any], repo: dict[str, Any]) -> str:
    if repo.get("full_name"):
        return str(repo["full_name"])
    html_url = str(issue.get("html_url", ""))
    match = re.search(r"github\.com/([^/]+/[^/]+)/issues/", html_url)
    return match.group(1) if match else "unknown/repository"


def _haystack(issue: dict[str, Any], repo: dict[str, Any], labels: list[str]) -> str:
    pieces = [
        issue.get("title", ""),
        issue.get("body", ""),
        repo.get("name", ""),
        repo.get("full_name", ""),
        repo.get("description", ""),
        repo.get("language", ""),
        " ".join(repo.get("topics") or []),
        " ".join(labels),
    ]
    return " ".join(str(piece or "") for piece in pieces).lower()


def matched_skills(issue: dict[str, Any], repo: dict[str, Any], labels: list[str]) -> list[str]:
    text = _haystack(issue, repo, labels)
    matches: list[str] = []
    for skill, aliases in SKILL_ALIASES.items():
        if any(alias.lower() in text for alias in aliases):
            matches.append(skill)
    return matches


def skill_score(matches: list[str], issue: dict[str, Any]) -> float:
    if not matches:
        return 10.0
    title = str(issue.get("title", "")).lower()
    title_hits = sum(
        1
        for skill in matches
        if any(alias in title for alias in SKILL_ALIASES.get(skill, []))
    )
    score = 24 + (len(matches) * 12) + (title_hits * 7)
    return _round_score(score)


def repo_health_score(repo: dict[str, Any]) -> float:
    stars = int(repo.get("stargazers_count") or 0)
    forks = int(repo.get("forks_count") or 0)
    open_issues = int(repo.get("open_issues_count") or 0)
    pushed_at = parse_github_datetime(repo.get("pushed_at"))
    days_since_push = max(0, (datetime.now(timezone.utc) - pushed_at).days)

    activity = 100 if days_since_push <= 7 else 85 if days_since_push <= 30 else 65 if days_since_push <= 90 else 35
    star_signal = min(100, math.log10(stars + 1) * 25)
    fork_signal = min(100, math.log10(forks + 1) * 30)
    issue_load = 100 if open_issues <= 100 else 75 if open_issues <= 500 else 45

    return _round_score((activity * 0.4) + (star_signal * 0.35) + (fork_signal * 0.15) + (issue_load * 0.1))


def competition_score(issue: dict[str, Any]) -> float:
    comments = int(issue.get("comments") or 0)
    if comments == 0:
        return 100.0
    return _round_score(100 - (comments * 11))


def freshness_score(issue: dict[str, Any]) -> float:
    created_at = parse_github_datetime(issue.get("created_at"))
    age_days = max(0, (datetime.now(timezone.utc) - created_at).days)
    if age_days <= 3:
        return 92.0
    if age_days <= 14:
        return 100.0
    if age_days <= 30:
        return 86.0
    if age_days <= 90:
        return 66.0
    if age_days <= 180:
        return 44.0
    return 24.0


def fallback_reason(issue: IssueRecommendation) -> str:
    skills = ", ".join(issue.matched_skills[:3]) or "the v1 skill profile"
    return (
        f"Strong match for {skills}; repo health is {issue.score_breakdown.repo_health:.0f}/100 "
        f"with {issue.comments} comments, so it looks approachable."
    )


def build_recommendation(issue: dict[str, Any], repo: dict[str, Any]) -> IssueRecommendation:
    labels = _label_names(issue)
    matches = matched_skills(issue, repo, labels)
    skill = skill_score(matches, issue)
    health = repo_health_score(repo)
    competition = competition_score(issue)
    freshness = freshness_score(issue)
    overall = _round_score((skill * 0.4) + (health * 0.25) + (competition * 0.2) + (freshness * 0.15))

    recommendation = IssueRecommendation(
        id=str(issue.get("id") or issue.get("node_id") or issue.get("html_url")),
        title=str(issue.get("title", "Untitled issue")),
        html_url=str(issue.get("html_url", "")),
        repository=_repo_name_from_issue(issue, repo),
        repository_url=issue.get("repository_url"),
        number=int(issue.get("number") or 0),
        labels=labels,
        state=str(issue.get("state", "open")),
        author=(issue.get("user") or {}).get("login"),
        author_avatar_url=(issue.get("user") or {}).get("avatar_url"),
        comments=int(issue.get("comments") or 0),
        created_at=parse_github_datetime(issue.get("created_at")),
        updated_at=parse_github_datetime(issue.get("updated_at")),
        repo_language=repo.get("language"),
        repo_stars=int(repo.get("stargazers_count") or 0),
        repo_forks=int(repo.get("forks_count") or 0),
        repo_open_issues=int(repo.get("open_issues_count") or 0),
        repo_pushed_at=parse_github_datetime(repo.get("pushed_at")) if repo.get("pushed_at") else None,
        score=overall,
        score_breakdown=ScoreBreakdown(
            skill_match=skill,
            repo_health=health,
            competition=competition,
            freshness=freshness,
        ),
        matched_skills=matches,
    )
    recommendation.reason = fallback_reason(recommendation)
    return recommendation
