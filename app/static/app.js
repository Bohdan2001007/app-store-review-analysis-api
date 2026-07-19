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

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const payload = buildPayload();
  setLoading(true);
  clearError();

  try {
    const response = await fetch("/api/v1/reviews/collect", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

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

function setLoading(isLoading) {
  submitButton.disabled = isLoading;
  statusPill.textContent = isLoading ? "Running" : "Ready";
  statusPill.classList.toggle("loading", isLoading);
  statusPill.classList.remove("error");
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
    return;
  }

  for (const insight of insights) {
    insightList.appendChild(renderInsight(insight));
  }
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
    <p class="insight-summary">${escapeHtml(insight.summary || "")}</p>
    <div class="keyword-row">${keywords}</div>
    <ol class="actions">${actions}</ol>
  `;

  return card;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
