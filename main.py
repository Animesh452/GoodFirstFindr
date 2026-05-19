from __future__ import annotations

from contextlib import asynccontextmanager
import logging

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.digest import start_digest_scheduler
from app.models import SavedIssueCreate, SavedIssueResponse, SearchResponse
from app.recommender import find_recommendations
from app.scoring import SKILL_PROFILE
from app.storage import SavedIssueStore


logging.basicConfig(level=logging.INFO)

store = SavedIssueStore(settings.database_url)
templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    try:
        store.init()
        scheduler = start_digest_scheduler(settings)
        app.state.scheduler = scheduler
        yield
    finally:
        if scheduler:
            scheduler.shutdown(wait=False)
        store.close()


app = FastAPI(title="GoodFirstFindr", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "skills": SKILL_PROFILE,
        },
    )


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/search", response_model=SearchResponse)
async def search(
    keyword: str = Query("", max_length=160),
    q: str | None = Query(None, max_length=160),
    topic: str | None = Query(None, max_length=160),
    limit: int = Query(10, ge=1, le=25),
    include_reasons: bool = Query(True),
):
    search_term = (q or topic or keyword or "").strip()
    try:
        items, total_count = await find_recommendations(
            keyword=search_term,
            limit=limit,
            settings=settings,
            include_reasons=include_reasons,
        )
    except httpx.HTTPStatusError as exc:
        raise _github_exception(exc) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GitHub request failed: {exc.__class__.__name__}",
        ) from exc

    return SearchResponse(
        keyword=search_term,
        total_count=total_count,
        returned=len(items),
        items=items,
    )


@app.get("/saved", response_model=list[SavedIssueResponse])
async def saved(x_client_id: str | None = Header(default=None, alias="X-Client-Id")):
    return store.list_saved(_client_id(x_client_id))


@app.post("/save", response_model=SavedIssueResponse, status_code=status.HTTP_201_CREATED)
async def save_issue(
    payload: SavedIssueCreate,
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    return store.save_issue(_client_id(x_client_id), payload.issue)


@app.delete("/saved/{saved_id}")
async def delete_saved(
    saved_id: int,
    x_client_id: str | None = Header(default=None, alias="X-Client-Id"),
):
    deleted = store.delete_issue(_client_id(x_client_id), saved_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved issue not found")
    return {"deleted": True}


def _client_id(value: str | None) -> str:
    cleaned = (value or "anonymous").strip()
    return cleaned[:120] or "anonymous"


def _github_exception(exc: httpx.HTTPStatusError) -> HTTPException:
    status_code = exc.response.status_code
    if status_code == 401:
        detail = "GitHub authentication failed. Check GITHUB_TOKEN."
    elif status_code == 403:
        detail = "GitHub rate limit or permissions blocked the search."
    elif status_code == 422:
        detail = "GitHub rejected the search query."
    else:
        detail = f"GitHub returned HTTP {status_code}."
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
