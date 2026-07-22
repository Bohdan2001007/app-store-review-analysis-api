const form = document.querySelector("#analysis-form");
const submitButton = document.querySelector("#submit-button");
const statusPill = document.querySelector("#status-pill");
const emptyState = document.querySelector("#empty-state");
const errorState = document.querySelector("#error-state");
const resultsPanel = document.querySelector("#results");
const summaryTitle = document.querySelector("#summary-title");
const returnedReviews = document.querySelector("#returned-reviews");
const availableReviews = document.querySelector("#available-reviews");
const analyzedReviews = document.querySelector("#analyzed-reviews");
const insightCount = document.querySelector("#insight-count");
const insightList = document.querySelector("#insight-list");
const loadingOverlay = document.querySelector("#loading-overlay");
const ratingTotal = document.querySelector("#rating-total");
const ratingChart = document.querySelector("#rating-chart");
const sentimentTotal = document.querySelector("#sentiment-total");
const sentimentChart = document.querySelector("#sentiment-chart");
const keywordTotal = document.querySelector("#keyword-total");
const keywordAnalysisList = document.querySelector("#keyword-analysis-list");
const MAX_FETCH_ATTEMPTS = 4;
const RETRY_DELAYS_MS = [2000, 5000, 10000];

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = buildPayload();
  setLoading(true);
  clearError();

  try {
    const response = await fetchWithRetry(payload);
    const data = await parseResponse(response);

    if (!response.ok) {
      throw new Error(data.detail || "Review analysis failed.");
    }

    renderResults(data);
  } catch (error) {
    renderError(error.message);
  } finally {
    setLoading(false);
  }
});

async function fetchWithRetry(payload) {
  let lastError = null;

  for (let attempt = 1; attempt <= MAX_FETCH_ATTEMPTS; attempt += 1) {
    try {
      setLoadingAttempt(attempt);
      const response = await fetch("/api/v1/reviews/collect", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
        keepalive: false,
      });

      if (!shouldRetryResponse(response) || attempt === MAX_FETCH_ATTEMPTS) {
        return response;
      }

      lastError = new Error(`Server returned HTTP ${response.status}.`);
    } catch (error) {
      lastError = error;

      if (attempt === MAX_FETCH_ATTEMPTS) {
        break;
      }
    }

    await wait(
      RETRY_DELAYS_MS[attempt - 1] || RETRY_DELAYS_MS[RETRY_DELAYS_MS.length - 1]
    );
  }

  throw new Error(
    lastError?.message === "Load failed"
      ? "The connection was interrupted. Please try again with a smaller limit or run the request again."
      : lastError?.message || "Review analysis request failed."
  );
}

function shouldRetryResponse(response) {
  return [408, 429, 500, 502, 503, 504].includes(response.status);
}

function wait(delayMs) {
  return new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  });
}

function buildPayload() {
  const formData = new FormData(form);
  const fromDate = formData.get("from_date");

  return {
    app_id: Number(formData.get("app_id")),
    country: String(formData.get("country")).trim().toLowerCase(),
    from_date: fromDate || null,
    limit: Number(formData.get("limit")),
  };
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();

  return {
    detail: text || `Request failed with HTTP ${response.status}.`,
  };
}

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  statusPill.textContent = isLoading ? "Running" : "Ready";
  statusPill.classList.toggle("loading", isLoading);
  statusPill.classList.remove("error");
  loadingOverlay.classList.toggle("hidden", !isLoading);
}

function setLoadingAttempt(attempt) {
  if (attempt === 1) {
    statusPill.textContent = "Running";
    return;
  }

  statusPill.textContent = `Retry ${attempt}`;
}

function clearError() {
  errorState.classList.add("hidden");
  errorState.textContent = "";
}

function renderError(message) {
  statusPill.textContent = "Error";
  statusPill.classList.remove("loading");
  statusPill.classList.add("error");
  emptyState.classList.add("hidden");
  resultsPanel.classList.add("hidden");
  errorState.textContent = message;
  errorState.classList.remove("hidden");
}

function renderResults(data) {
  emptyState.classList.add("hidden");
  errorState.classList.add("hidden");
  resultsPanel.classList.remove("hidden");

  const actionable = data.actionable_insights || {};
  const insights = actionable.insights || [];

  summaryTitle.textContent = actionable.summary || actionable.skipped_reason || "No actionable summary was generated.";
  returnedReviews.textContent = data.returned_reviews ?? 0;
  availableReviews.textContent = data.available_reviews ?? 0;
  analyzedReviews.textContent = data.keyword_insights?.analyzed_reviews ?? 0;
  insightCount.textContent = `${insights.length} ${insights.length === 1 ? "area" : "areas"}`;

  insightList.innerHTML = "";

  if (!insights.length) {
    insightList.appendChild(renderEmptyInsight(actionable));
  } else {
    for (const insight of insights) {
      insightList.appendChild(renderInsight(insight));
    }
  }

  renderRatingChart(data.reviews || []);
  renderSentimentChart(data.reviews || []);
  renderKeywordAnalysis(data.keyword_insights?.keywords || []);
}

function renderEmptyInsight(actionable) {
  const card = document.createElement("article");
  card.className = "insight-card";
  card.innerHTML = `
    <header>
      <h4>Insights not generated</h4>
      <span class="severity medium">Pending</span>
    </header>
    <p class="insight-summary">${escapeHtml(actionable.skipped_reason || "No improvement areas were returned.")}</p>
  `;

  return card;
}

function renderInsight(insight) {
  const card = document.createElement("article");
  const severity = String(insight.severity || "medium").toLowerCase();
  card.className = "insight-card";

  const keywords = (insight.evidence_keywords || [])
    .map((keyword) => `<span>${escapeHtml(keyword)}</span>`)
    .join("");
  const actions = (insight.recommended_actions || [])
    .map((action) => `<li>${escapeHtml(action)}</li>`)
    .join("");

  card.innerHTML = `
    <header>
      <h4>${escapeHtml(insight.area || "Improvement area")}</h4>
      <span class="severity ${escapeHtml(severity)}">${escapeHtml(severity)}</span>
    </header>
    <p class="insight-summary">${escapeHtml(insight.area_summary || "")}</p>
    <div class="keyword-row">${keywords}</div>
    <ol class="actions">${actions}</ol>
  `;

  return card;
}

function renderRatingChart(reviews) {
  const total = reviews.length;
  ratingTotal.textContent = `${total} ${total === 1 ? "review" : "reviews"}`;
  ratingChart.innerHTML = "";

  for (const rating of [5, 4, 3, 2, 1]) {
    const count = reviews.filter((review) => Number(review.rating) === rating).length;
    const percentage = getPercentage(count, total);
    const row = document.createElement("div");
    row.className = "rating-row";
    row.innerHTML = `
      <div class="rating-label">
        <span>${rating}</span>
        <span class="stars">${rating} stars</span>
      </div>
      <div class="chart-track">
        <span class="chart-fill rating-${rating}" style="width: ${percentage}%"></span>
      </div>
      <div class="chart-value">
        <strong>${percentage}%</strong>
        <span>${count}</span>
      </div>
    `;
    ratingChart.appendChild(row);
  }
}

function renderSentimentChart(reviews) {
  const total = reviews.length;
  const sentiments = [
    { label: "positive", title: "Positive" },
    { label: "neutral", title: "Neutral" },
    { label: "negative", title: "Negative" },
  ];

  sentimentTotal.textContent = `${total} ${total === 1 ? "review" : "reviews"}`;
  sentimentChart.innerHTML = "";

  for (const sentiment of sentiments) {
    const count = reviews.filter((review) => review.sentiment?.label === sentiment.label).length;
    const percentage = getPercentage(count, total);
    const item = document.createElement("div");
    item.className = `sentiment-item ${sentiment.label}`;
    item.innerHTML = `
      <div class="sentiment-ring" style="--value: ${percentage * 3.6}deg">
        <span>${percentage}%</span>
      </div>
      <strong>${sentiment.title}</strong>
      <p>${count} ${count === 1 ? "comment" : "comments"}</p>
    `;
    sentimentChart.appendChild(item);
  }
}

function renderKeywordAnalysis(keywordGroups) {
  keywordTotal.textContent = `${keywordGroups.length} ${keywordGroups.length === 1 ? "group" : "groups"}`;
  keywordAnalysisList.innerHTML = "";

  if (!keywordGroups.length) {
    const empty = document.createElement("div");
    empty.className = "keyword-empty";
    empty.textContent = "No issue keyword groups were found in negative, neutral, or low-rated reviews.";
    keywordAnalysisList.appendChild(empty);
    return;
  }

  for (const group of keywordGroups.slice(0, 12)) {
    const item = document.createElement("article");
    item.className = "keyword-analysis-item";
    const comments = group.comments || [];
    const previewComments = comments
      .slice(0, 2)
      .map((comment) => `
        <li>
          <strong>${escapeHtml(comment.title || "Untitled")}</strong>
          <span>${escapeHtml(truncateText(comment.text || "", 140))}</span>
        </li>
      `)
      .join("");

    item.innerHTML = `
      <header>
        <div>
          <h4>${escapeHtml(group.keyword)}</h4>
          <p>${group.count} ${group.count === 1 ? "comment" : "comments"} | ${group.percentage}% coverage</p>
        </div>
        <span>${comments.length}</span>
      </header>
      <ul>${previewComments}</ul>
    `;
    keywordAnalysisList.appendChild(item);
  }
}

function getPercentage(count, total) {
  if (!total) {
    return 0;
  }

  return Math.round((count / total) * 10000) / 100;
}

function truncateText(value, maxLength) {
  if (value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 3)}...`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
