from __future__ import annotations

from app.config import Settings
from app.github_client import GitHubClient, is_available_issue
from app.llm import GroqReasoner, IssueAnalysis
from app.models import IssueRecommendation
from app.scoring import build_recommendation


PYTHON_COMPATIBLE_LANGUAGES = {"python", "any"}


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
        descriptions = {
            str(item.get("html_url", "")): str(item.get("body") or "")
            for item in raw_items
        }
        sample = list(descriptions.values())[0] if descriptions else ""
        print(f"[DEBUG] Sample description length: {len(sample)} chars")
        print(f"[DEBUG] Sample: {sample[:200]}")
        reasoner = GroqReasoner(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
            timeout_seconds=settings.groq_timeout_seconds,
        )
        analyses = await reasoner.explain(selected, descriptions=descriptions)
        for issue in selected:
            analysis = analyses.get(issue.html_url)
            if analysis:
                _apply_llm_analysis(issue, analysis)
        selected.sort(key=lambda item: item.score, reverse=True)

    return selected, int(search_data.get("total_count") or 0)


def _apply_llm_analysis(issue: IssueRecommendation, analysis: IssueAnalysis) -> None:
    rule_based_score = issue.score
    blended_score = (rule_based_score * 0.5) + (analysis.fit_score * 0.5)
    penalty = _language_penalty(analysis.primary_language) + min(len(analysis.red_flags) * 15, 50)

    issue.score = round(max(0.0, blended_score - penalty), 1)
    issue.red_flags = analysis.red_flags
    issue.reason = analysis.reason


def _language_penalty(primary_language: str) -> int:
    normalized = primary_language.strip().lower()
    if normalized in PYTHON_COMPATIBLE_LANGUAGES:
        return 0
    return 40
