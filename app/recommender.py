from __future__ import annotations

from app.config import Settings
from app.github_client import GitHubClient, is_available_issue
from app.llm import GroqReasoner
from app.models import IssueRecommendation
from app.scoring import build_recommendation


async def find_recommendations(
    keyword: str,
    limit: int,
    settings: Settings,
    include_reasons: bool = True,
) -> tuple[list[IssueRecommendation], int]:
    candidate_limit = max(limit * 3, settings.github_candidate_limit)
    async with GitHubClient(settings.github_token, settings.github_timeout_seconds) as github:
        search_data = await github.search_good_first_issues(keyword, per_page=candidate_limit)
        raw_items = [item for item in search_data.get("items", []) if is_available_issue(item)]
        repo_urls = [item.get("repository_url", "") for item in raw_items]
        repos = await github.fetch_repositories(repo_urls)

    recommendations = [
        build_recommendation(item, repos.get(item.get("repository_url", ""), {}))
        for item in raw_items
    ]
    recommendations.sort(key=lambda item: item.score, reverse=True)
    selected = recommendations[:limit]

    if include_reasons:
        reasoner = GroqReasoner(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            timeout_seconds=settings.groq_timeout_seconds,
        )
        reasons = await reasoner.explain(selected)
        for issue in selected:
            issue.reason = reasons.get(issue.html_url, issue.reason)

    return selected, int(search_data.get("total_count") or 0)
