from datetime import datetime
from pydantic import BaseModel, Field


class ScoreBreakdown(BaseModel):
    skill_match: float = Field(..., ge=0, le=100)
    repo_health: float = Field(..., ge=0, le=100)
    competition: float = Field(..., ge=0, le=100)
    freshness: float = Field(..., ge=0, le=100)


class IssueRecommendation(BaseModel):
    id: str
    title: str
    html_url: str
    repository: str
    repository_url: str | None = None
    number: int
    labels: list[str] = Field(default_factory=list)
    state: str = "open"
    author: str | None = None
    author_avatar_url: str | None = None
    comments: int = 0
    created_at: datetime
    updated_at: datetime
    repo_language: str | None = None
    repo_stars: int = 0
    repo_forks: int = 0
    repo_open_issues: int = 0
    repo_pushed_at: datetime | None = None
    score: float
    score_breakdown: ScoreBreakdown
    matched_skills: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    reason: str = ""


class SearchResponse(BaseModel):
    keyword: str
    total_count: int
    returned: int
    items: list[IssueRecommendation]


class SavedIssueCreate(BaseModel):
    issue: IssueRecommendation


class SavedIssueResponse(BaseModel):
    saved_id: int
    saved_at: datetime
    issue: IssueRecommendation
