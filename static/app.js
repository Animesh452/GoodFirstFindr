const clientIdKey = "goodfirstfindr_client_id";
const clientId = getClientId();

const searchForm = document.querySelector("#searchForm");
const keywordInput = document.querySelector("#keywordInput");
const limitInput = document.querySelector("#limitInput");
const searchButton = document.querySelector("#searchButton");
const clearButton = document.querySelector("#clearButton");
const refreshSavedButton = document.querySelector("#refreshSavedButton");
const resultsList = document.querySelector("#resultsList");
const savedList = document.querySelector("#savedList");
const savedCount = document.querySelector("#savedCount");
const statusLine = document.querySelector("#statusLine");
const errorBox = document.querySelector("#errorBox");
const emptyTemplate = document.querySelector("#emptyTemplate");

let currentResults = [];

document.addEventListener("DOMContentLoaded", () => {
  renderEmpty(resultsList);
  loadSaved();
  wireEvents();
  hydrateIcons();
});

function wireEvents() {
  searchForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runSearch();
  });

  clearButton.addEventListener("click", () => {
    currentResults = [];
    statusLine.textContent = "";
    hideError();
    renderEmpty(resultsList);
  });

  refreshSavedButton.addEventListener("click", () => loadSaved());
}

async function runSearch() {
  const keyword = keywordInput.value.trim();
  const limit = clamp(Number(limitInput.value || 10), 1, 25);
  setLoading(true);
  hideError();
  statusLine.textContent = "Searching GitHub issues...";

  try {
    const url = new URL("/search", window.location.origin);
    url.searchParams.set("keyword", keyword);
    url.searchParams.set("limit", String(limit));
    const response = await fetch(url);
    const payload = await parseResponse(response);
    currentResults = payload.items || [];
    renderResults(currentResults);
    statusLine.textContent = `${payload.returned} ranked from ${payload.total_count.toLocaleString()} GitHub matches.`;
  } catch (error) {
    renderEmpty(resultsList);
    showError(error.message || "Search failed.");
    statusLine.textContent = "";
  } finally {
    setLoading(false);
  }
}

function renderResults(issues) {
  resultsList.replaceChildren();
  if (!issues.length) {
    renderEmpty(resultsList);
    return;
  }

  for (const issue of issues) {
    const card = document.createElement("article");
    card.className = "issue-card";

    const scoreTile = document.createElement("div");
    scoreTile.className = "score-tile";
    scoreTile.innerHTML = `<span>${Math.round(issue.score)}</span><small>score</small>`;

    const main = document.createElement("div");
    main.className = "issue-main";

    const titleRow = document.createElement("div");
    titleRow.className = "issue-title-row";

    const titleLink = document.createElement("a");
    titleLink.className = "issue-title";
    titleLink.href = issue.html_url;
    titleLink.target = "_blank";
    titleLink.rel = "noreferrer";
    const title = document.createElement("h3");
    title.textContent = issue.title;
    titleLink.append(title);

    const saveButton = document.createElement("button");
    saveButton.className = "save-button";
    saveButton.type = "button";
    saveButton.innerHTML = `<i data-lucide="bookmark-plus"></i><span>Save</span>`;
    saveButton.addEventListener("click", () => saveIssue(issue, saveButton));

    titleRow.append(titleLink, saveButton);

    const repoLine = document.createElement("div");
    repoLine.className = "repo-line";
    if (issue.author_avatar_url) {
      const avatar = document.createElement("img");
      avatar.className = "avatar";
      avatar.src = issue.author_avatar_url;
      avatar.alt = "";
      repoLine.append(avatar);
    }
    const repoText = document.createElement("span");
    repoText.textContent = `${issue.repository} #${issue.number}`;
    repoLine.append(repoText);

    const labelRow = document.createElement("div");
    labelRow.className = "label-row";
    for (const skill of issue.matched_skills.slice(0, 5)) {
      labelRow.append(makePill(skill, "skill-pill"));
    }
    for (const label of issue.labels.slice(0, 4)) {
      labelRow.append(makePill(label, "label-pill"));
    }

    const metrics = document.createElement("div");
    metrics.className = "metric-grid";
    metrics.append(
      makeMetric("target", "Skill", issue.score_breakdown.skill_match),
      makeMetric("activity", "Health", issue.score_breakdown.repo_health),
      makeMetric("message-circle", "Competition", issue.score_breakdown.competition),
      makeMetric("clock-3", "Freshness", issue.score_breakdown.freshness)
    );

    const reason = document.createElement("p");
    reason.className = "reason";
    reason.textContent = issue.reason;

    const meta = document.createElement("p");
    meta.className = "meta-line";
    meta.textContent = `${issue.repo_stars.toLocaleString()} stars | ${issue.comments} comments | ${formatDate(issue.created_at)}`;

    const actions = document.createElement("div");
    actions.className = "issue-actions";
    const external = document.createElement("a");
    external.className = "external-link";
    external.href = issue.html_url;
    external.target = "_blank";
    external.rel = "noreferrer";
    external.innerHTML = `<i data-lucide="external-link"></i><span>Open issue</span>`;
    actions.append(external);

    main.append(titleRow, repoLine, labelRow, metrics, reason, meta, actions);
    card.append(scoreTile, main);
    resultsList.append(card);
  }

  hydrateIcons();
}

function renderSaved(items) {
  savedList.replaceChildren();
  savedCount.textContent = String(items.length);
  if (!items.length) {
    renderEmpty(savedList);
    return;
  }

  for (const item of items) {
    const issue = item.issue;
    const card = document.createElement("article");
    card.className = "saved-card";

    const title = document.createElement("h3");
    title.textContent = issue.title;

    const meta = document.createElement("div");
    meta.className = "saved-meta";
    meta.textContent = `${issue.repository} | ${Math.round(issue.score)}/100`;

    const actions = document.createElement("div");
    actions.className = "saved-actions";

    const open = document.createElement("a");
    open.className = "external-link";
    open.href = issue.html_url;
    open.target = "_blank";
    open.rel = "noreferrer";
    open.innerHTML = `<i data-lucide="external-link"></i><span>Open</span>`;

    const remove = document.createElement("button");
    remove.className = "danger-button";
    remove.type = "button";
    remove.title = "Remove saved issue";
    remove.setAttribute("aria-label", "Remove saved issue");
    remove.innerHTML = `<i data-lucide="trash-2"></i>`;
    remove.addEventListener("click", () => deleteSaved(item.saved_id));

    actions.append(open, remove);
    card.append(title, meta, actions);
    savedList.append(card);
  }

  hydrateIcons();
}

async function saveIssue(issue, button) {
  button.disabled = true;
  const previous = button.innerHTML;
  button.innerHTML = `<i data-lucide="loader-2"></i><span>Saving</span>`;
  hydrateIcons();
  hideError();

  try {
    const response = await fetch("/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Client-Id": clientId,
      },
      body: JSON.stringify({ issue }),
    });
    await parseResponse(response);
    await loadSaved();
    button.innerHTML = `<i data-lucide="bookmark-check"></i><span>Saved</span>`;
  } catch (error) {
    showError(error.message || "Save failed.");
    button.innerHTML = previous;
  } finally {
    button.disabled = false;
    hydrateIcons();
  }
}

async function loadSaved() {
  hideError();
  try {
    const response = await fetch("/saved", {
      headers: { "X-Client-Id": clientId },
    });
    const items = await parseResponse(response);
    renderSaved(items);
  } catch (error) {
    showError(error.message || "Could not load saved issues.");
  }
}

async function deleteSaved(savedId) {
  hideError();
  try {
    const response = await fetch(`/saved/${savedId}`, {
      method: "DELETE",
      headers: { "X-Client-Id": clientId },
    });
    await parseResponse(response);
    await loadSaved();
  } catch (error) {
    showError(error.message || "Could not remove saved issue.");
  }
}

async function parseResponse(response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail || response.statusText || "Request failed.";
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload;
}

function makePill(text, className) {
  const pill = document.createElement("span");
  pill.className = className;
  pill.textContent = text;
  return pill;
}

function makeMetric(icon, label, value) {
  const metric = document.createElement("div");
  metric.className = "metric";
  metric.innerHTML = `
    <span class="metric-icon"><i data-lucide="${icon}"></i></span>
    <span>
      <span class="meter" style="--value: ${clamp(value, 0, 100)}%"><span></span></span>
      <span class="metric-label">${label} ${Math.round(value)}</span>
    </span>
  `;
  return metric;
}

function renderEmpty(container) {
  const clone = emptyTemplate.content.cloneNode(true);
  container.replaceChildren(clone);
  hydrateIcons();
}

function setLoading(isLoading) {
  searchButton.disabled = isLoading;
  searchButton.innerHTML = isLoading
    ? `<i data-lucide="loader-2"></i><span>Searching</span>`
    : `<i data-lucide="search"></i><span>Search</span>`;
  hydrateIcons();
}

function showError(message) {
  errorBox.hidden = false;
  errorBox.textContent = message;
}

function hideError() {
  errorBox.hidden = true;
  errorBox.textContent = "";
}

function getClientId() {
  let value = localStorage.getItem(clientIdKey);
  if (!value) {
    value = window.crypto && window.crypto.randomUUID
      ? window.crypto.randomUUID()
      : `client-${Date.now()}-${Math.random()}`;
    localStorage.setItem(clientIdKey, value);
  }
  return value;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, Number.isFinite(value) ? value : min));
}

function formatDate(value) {
  try {
    return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" }).format(new Date(value));
  } catch {
    return "unknown date";
  }
}

function hydrateIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}
