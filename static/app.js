/**
 * CaseLens — app.js
 * Single-Page Application with Hash Routing
 * Legal / Judicial Intelligence System
 */

// ============================================================
// Global State & API Layer
// ============================================================

const state = {
  currentRoute: "",
  routeParam: null,
  corpusCount: 400,
  docket: {
    bucket: "",
    caseType: "",
    q: "",
    sort: "priority",
    page: 1,
    pageSize: 25,
    totalPages: 1,
    totalCount: 0,
  },
};

/**
 * Robust fetch wrapper with error handling & JSON parsing.
 */
async function apiCall(endpoint, options = {}) {
  try {
    const res = await fetch(endpoint, options);
    if (!res.ok) {
      let errMsg = `Server returned status ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson && errJson.detail) errMsg = errJson.detail;
      } catch (_) {
        const text = await res.text();
        if (text) errMsg = text.slice(0, 150);
      }
      const error = new Error(errMsg);
      error.status = res.status;
      throw error;
    }
    return await res.json();
  } catch (err) {
    if (err.name === "TypeError" && err.message.includes("fetch")) {
      const netErr = new Error("Could not reach server. Network connection failed.");
      netErr.isNetwork = true;
      throw netErr;
    }
    throw err;
  }
}

// ============================================================
// API Methods
// ============================================================

/** GET /api/overview */
export async function fetchOverview() {
  return apiCall("/api/overview");
}

/** POST /api/search */
export async function fetchSearch(params) {
  return apiCall("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
}

/** GET /api/cases with query params */
export async function fetchCases({ bucket, case_type, status, q, sort, page = 1, page_size = 25 } = {}) {
  const query = new URLSearchParams();
  if (bucket) query.set("bucket", bucket);
  if (case_type) query.set("case_type", case_type);
  if (status) query.set("status", status);
  if (q) query.set("q", q);
  if (sort) query.set("sort", sort);
  if (page) query.set("page", page);
  if (page_size) query.set("page_size", page_size);

  const qs = query.toString();
  return apiCall(`/api/cases${qs ? `?${qs}` : ""}`);
}

/** GET /api/cases/{id} */
export async function fetchCase(id) {
  return apiCall(`/api/cases/${encodeURIComponent(id)}`);
}

/** POST /api/cases (fallback to /api/cases/score) */
export async function addCase(formData) {
  try {
    return await apiCall("/api/cases", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formData),
    });
  } catch (err) {
    if (err.status === 404 || err.status === 405) {
      return await apiCall("/api/cases/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
    }
    throw err;
  }
}

// ============================================================
// UI Utilities & Formatters
// ============================================================

export function esc(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 
 * Render 4px similarity bar (max 60px) + numeric value 
 */
export function renderSimBar(score, label = "") {
  const val = typeof score === "number" ? score : parseFloat(score) || 0;
  const clamped = Math.max(0, Math.min(1, val));
  const widthPx = Math.round(clamped * 60);

  return `
    <div class="precedent-bar-wrap" title="${(val * 100).toFixed(1)}% similarity">
      <div class="sim-track">
        <div class="sim-fill" style="width: ${widthPx}px;"></div>
      </div>
      <span class="sim-val">${val.toFixed(2)}</span>
      ${label ? `<span class="law-sim-label" style="margin-left:4px;">${esc(label)}</span>` : ""}
    </div>
  `;
}

/**
 * Bucket badge component
 * Fast-track = teal bg #1E3B3A, Standard = grey bg #E3DDD0, Needs attention = oxblood bg #7A1F2B
 */
export function renderBucketBadge(bucket) {
  if (!bucket) return `<span class="badge badge--standard">Standard</span>`;
  const b = String(bucket).toLowerCase();
  if (b.includes("fast")) {
    return `<span class="badge badge--fast">Fast-track</span>`;
  }
  if (b.includes("attention") || b.includes("needs")) {
    return `<span class="badge badge--attention">Needs Attention</span>`;
  }
  return `<span class="badge badge--standard">Standard</span>`;
}

/** Error box with retry action */
function renderErrorBox(message, onRetry) {
  const box = document.createElement("div");
  box.className = "state-box";
  box.innerHTML = `
    <h3 class="state-title" style="color: #7A1F2B;">Operation Failed</h3>
    <p class="state-desc">${esc(message || "Could not reach server.")}</p>
    <button class="btn btn-primary" type="button">Retry</button>
  `;
  if (onRetry) {
    box.querySelector("button").addEventListener("click", onRetry);
  }
  return box;
}

/** Loading skeleton/spinner element */
function renderLoading(text = "Loading data from judicial registry…") {
  const box = document.createElement("div");
  box.className = "state-box";
  box.innerHTML = `
    <div class="spinner"></div>
    <p class="state-desc">${esc(text)}</p>
  `;
  return box;
}

// ============================================================
// View: Overview (#/)
// ============================================================

async function renderOverviewView() {
  const container = document.getElementById("view-overview");
  const tbody = document.getElementById("queue-tbody");
  tbody.innerHTML = `<tr><td colspan="7" class="td-status"><div class="spinner"></div><br/>Loading priority queue…</td></tr>`;

  try {
    const data = await fetchOverview();

    // Update KPI cards
    const totalActive = data.total_active ?? 0;
    const byStatus = data.by_status || {};
    const byBucket = data.by_bucket || {};

    document.getElementById("kpi-total-active").textContent = totalActive;
    document.getElementById("kpi-under-hearing").textContent = byStatus["Under Hearing"] ?? 0;
    document.getElementById("kpi-reserved").textContent = byStatus["Judgment Reserved"] ?? 0;
    document.getElementById("kpi-fast-track").textContent = byBucket["Fast-track"] ?? 0;

    if (data.judgment_count || data.index_size) {
      state.corpusCount = data.judgment_count || data.index_size;
      const corpusEl = document.getElementById("corpus-info");
      if (corpusEl) corpusEl.textContent = `Corpus: ${state.corpusCount} cases`;
    }

    // Top Priority Queue Table (top 10)
    const queue = data.top_queue || [];
    if (!queue.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="td-status">No matters in the priority queue.</td></tr>`;
      return;
    }

    tbody.innerHTML = queue.map((c, idx) => {
      const isAttention = (c.bucket || "").toLowerCase().includes("attention") ||
                          (c.bucket || "").toLowerCase().includes("needs");
      const estDays = c.predicted_days != null ? Math.round(c.predicted_days) : "—";
      const sim = c.mean_top5_similarity ?? c.top1_similarity ?? 0;
      const score = c.priority_score != null ? Math.round(c.priority_score) : "—";
      const caseId = c.id != null ? c.id : c.case_no;

      return `
        <tr class="row-clickable${isAttention ? " row-attention" : ""}" data-id="${esc(caseId)}">
          <td class="td-mono">${idx + 1}</td>
          <td class="td-mono">${esc(c.case_no)}</td>
          <td class="td-title-cell">${esc(c.title || "Untitled Matter")}</td>
          <td>${renderBucketBadge(c.bucket)}</td>
          <td class="td-mono">${estDays} d</td>
          <td>${renderSimBar(sim)}</td>
          <td class="td-mono"><strong>${score}</strong></td>
        </tr>
      `;
    }).join("");

    // Bind row clicks
    tbody.querySelectorAll("tr.row-clickable").forEach(row => {
      row.addEventListener("click", () => {
        const id = row.dataset.id;
        if (id) window.location.hash = `#/case/${id}`;
      });
    });

  } catch (err) {
    tbody.innerHTML = "";
    const errBox = renderErrorBox(err.message, () => renderOverviewView());
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 7;
    td.appendChild(errBox);
    tr.appendChild(td);
    tbody.appendChild(tr);
  }
}

// Overview quick search form handler
function setupOverviewSearch() {
  const form = document.getElementById("overview-search-form");
  if (!form) return;
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("overview-search-input");
    const val = (input?.value || "").trim();
    if (val) {
      window.location.hash = `#/search?q=${encodeURIComponent(val)}`;
    } else {
      window.location.hash = `#/search`;
    }
  });
}

// ============================================================
// View: Precedent Search (#/search)
// ============================================================

async function executeSearch(queryOverride = null) {
  const inputEl = document.getElementById("search-input");
  const caseTypeEl = document.getElementById("filter-case-type");
  const courtEl = document.getElementById("filter-court");
  const yearMinEl = document.getElementById("filter-year-min");
  const yearMaxEl = document.getElementById("filter-year-max");
  const stateArea = document.getElementById("search-state-area");
  const resultsList = document.getElementById("search-results-list");
  const resultsHeader = document.getElementById("search-results-header");
  const metaText = document.getElementById("search-meta-text");
  const backendTag = document.getElementById("search-backend-tag");
  const btn = document.getElementById("btn-search-exec");

  if (queryOverride != null) {
    inputEl.value = queryOverride;
  }

  const query = (inputEl.value || "").trim();
  resultsList.innerHTML = "";
  stateArea.innerHTML = "";

  if (!query) {
    resultsHeader.hidden = true;
    stateArea.innerHTML = `
      <div class="state-box">
        <h3 class="state-title">Enter a Search Query or Legal Controversy</h3>
        <p class="state-desc">Type facts, statutes, or pick one of the example queries above to search matching Indian judgments.</p>
      </div>
    `;
    return;
  }

  // Loading state
  btn.disabled = true;
  stateArea.appendChild(renderLoading("Evaluating query against judgment corpus…"));
  resultsHeader.hidden = true;

  const payload = {
    query,
    top_k: 8,
  };
  if (caseTypeEl.value) payload.case_type = caseTypeEl.value;
  if (courtEl.value.trim()) payload.court = courtEl.value.trim();
  if (yearMinEl.value) payload.year_min = parseInt(yearMinEl.value, 10);
  if (yearMaxEl.value) payload.year_max = parseInt(yearMaxEl.value, 10);

  try {
    const res = await fetchSearch(payload);
    stateArea.innerHTML = "";

    const results = Array.isArray(res) ? res : (res?.results || []);
    const backend = res?.backend || "sentence-transformers";
    const totalCorpus = res?.total_corpus || state.corpusCount || 400;

    resultsHeader.hidden = false;
    metaText.textContent = `Showing ${results.length} of ${totalCorpus} judgments`;
    backendTag.textContent = `backend: ${backend}`;

    if (!results.length) {
      resultsList.innerHTML = `
        <div class="state-box">
          <h3 class="state-title">No Matching Precedents Found</h3>
          <p class="state-desc">No judgments matched your criteria. Try widening filter bounds or adjusting keywords.</p>
        </div>
      `;
      return;
    }

    // Render law-report entries
    resultsList.innerHTML = results.map((item, idx) => {
      const rank = idx + 1;
      const citation = item.citation || `[${item.year || 2023}] INSC ${item.id || rank}`;
      const title = item.title || "Untitled Judgment";
      const meta = `${esc(item.court || "High Court")} &middot; ${esc(String(item.year || "2023"))} &middot; ${esc(item.case_type || "Civil")}`;
      
      const summaryText = item.summary || item.text_content?.slice(0, 360) || "Extractive summary unavailable.";
      // Check if snippet contains <mark> tags, if so keep HTML, else escape
      const summaryHtml = summaryText.includes("<mark>") ? summaryText : esc(summaryText);
      const rawSim = item.score ?? item.similarity ?? 0;
      const sim = typeof rawSim === "number" ? rawSim : parseFloat(rawSim) || 0;
      const fullText = item.text_content || "";

      return `
        <article class="law-entry">
          <div class="law-entry-header">
            <div class="law-title-wrap">
              <span class="law-rank">${rank}.</span>
              <h2 class="law-title">${esc(title)}</h2>
            </div>
            <span class="law-citation">${esc(citation)}</span>
          </div>

          <div class="law-meta">${meta}</div>

          <div class="law-summary">${summaryHtml}</div>

          <div class="law-footer">
            <div class="law-sim-row">
              <span class="law-sim-label">Similarity</span>
              ${renderSimBar(sim)}
            </div>
            ${fullText ? `<button type="button" class="law-toggle-btn" data-toggle="ft-${idx}">Show full judgment &darr;</button>` : ""}
          </div>

          ${fullText ? `<div id="ft-${idx}" class="law-full-text" hidden>${esc(fullText)}</div>` : ""}
        </article>
      `;
    }).join("");

    // Bind full text toggles
    resultsList.querySelectorAll(".law-toggle-btn").forEach(toggle => {
      toggle.addEventListener("click", () => {
        const targetId = toggle.dataset.toggle;
        const target = document.getElementById(targetId);
        if (target) {
          const isHidden = target.hidden;
          target.hidden = !isHidden;
          toggle.innerHTML = isHidden ? "Hide full judgment &uarr;" : "Show full judgment &darr;";
        }
      });
    });

  } catch (err) {
    stateArea.innerHTML = "";
    stateArea.appendChild(renderErrorBox(err.message, () => executeSearch()));
  } finally {
    btn.disabled = false;
  }
}

function setupSearchListeners() {
  const form = document.getElementById("search-form");
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      executeSearch();
    });
  }

  // Example links click
  const examplesContainer = document.getElementById("search-examples");
  if (examplesContainer) {
    examplesContainer.addEventListener("click", (e) => {
      const link = e.target.closest(".ex-link");
      if (link) {
        e.preventDefault();
        const q = link.dataset.query;
        executeSearch(q);
      }
    });
  }
}

// ============================================================
// View: Docket & Cause List (#/docket)
// ============================================================

async function renderDocketTable() {
  const tbody = document.getElementById("docket-tbody");
  const paginationBar = document.getElementById("docket-pagination");
  const paginationInfo = document.getElementById("pagination-info");
  const prevBtn = document.getElementById("btn-page-prev");
  const nextBtn = document.getElementById("btn-page-next");

  tbody.innerHTML = `<tr><td colspan="9" class="td-status"><div class="spinner"></div><br/>Loading docket cause list…</td></tr>`;

  try {
    const params = {
      bucket: state.docket.bucket,
      case_type: state.docket.caseType,
      q: state.docket.q,
      sort: state.docket.sort,
      page: state.docket.page,
      page_size: state.docket.pageSize,
    };

    const res = await fetchCases(params);

    const cases = Array.isArray(res) ? res : (res?.cases || []);
    const total = res?.total ?? cases.length;
    const page = res?.page ?? state.docket.page;
    const pages = res?.pages ?? Math.max(1, Math.ceil(total / state.docket.pageSize));

    state.docket.totalPages = pages;
    state.docket.totalCount = total;

    if (!cases.length) {
      tbody.innerHTML = `<tr><td colspan="9" class="td-status">No cases found matching the criteria.</td></tr>`;
      paginationBar.hidden = true;
      return;
    }

    tbody.innerHTML = cases.map(c => {
      const isAttention = (c.bucket || "").toLowerCase().includes("attention") ||
                          (c.bucket || "").toLowerCase().includes("needs");
      const estDays = c.predicted_days != null ? Math.round(c.predicted_days) : "—";
      const band = (c.lower_band != null && c.upper_band != null)
        ? `&plusmn;${Math.round((c.upper_band - c.lower_band) / 2)}`
        : "";
      const estDisplay = estDays !== "—" ? `${estDays} ${band}` : "—";
      const score = c.priority_score != null ? Math.round(c.priority_score) : "—";
      const caseId = c.id != null ? c.id : c.case_no;

      return `
        <tr class="row-clickable${isAttention ? " row-attention" : ""}" data-id="${esc(caseId)}">
          <td class="td-mono">${esc(c.case_no)}</td>
          <td class="td-title-cell">${esc(c.title || "—")}</td>
          <td>${esc(c.case_type || "—")}</td>
          <td>${esc(c.court || "High Court")}</td>
          <td><span class="mono-badge">${esc(c.status || "Pending")}</span></td>
          <td class="td-mono">${esc(String(c.hearings_so_far ?? 0))}</td>
          <td class="td-mono">${estDisplay}</td>
          <td>${renderBucketBadge(c.bucket)}</td>
          <td class="td-mono"><strong>${score}</strong></td>
        </tr>
      `;
    }).join("");

    // Bind row clicks
    tbody.querySelectorAll("tr.row-clickable").forEach(row => {
      row.addEventListener("click", () => {
        const id = row.dataset.id;
        if (id) window.location.hash = `#/case/${id}`;
      });
    });

    // Update pagination
    paginationBar.hidden = false;
    paginationInfo.textContent = `Page ${page} of ${pages} (${total} cases)`;
    prevBtn.disabled = page <= 1;
    nextBtn.disabled = page >= pages;

  } catch (err) {
    tbody.innerHTML = "";
    const errBox = renderErrorBox(err.message, () => renderDocketTable());
    const tr = document.createElement("tr");
    const td = document.createElement("td");
    td.colSpan = 9;
    td.appendChild(errBox);
    tr.appendChild(td);
    tbody.appendChild(tr);
    paginationBar.hidden = true;
  }
}

function setupDocketListeners() {
  // Bucket tabs
  const bucketTabs = document.getElementById("docket-bucket-tabs");
  if (bucketTabs) {
    bucketTabs.addEventListener("click", (e) => {
      const tab = e.target.closest(".bucket-tab");
      if (tab) {
        bucketTabs.querySelectorAll(".bucket-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        state.docket.bucket = tab.dataset.bucket;
        state.docket.page = 1;
        renderDocketTable();
      }
    });
  }

  // Search input with enter/change
  const qInput = document.getElementById("docket-q-input");
  if (qInput) {
    let debounceTimer = null;
    qInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        state.docket.q = qInput.value.trim();
        state.docket.page = 1;
        renderDocketTable();
      }, 350);
    });
  }

  // Case Type filter
  const typeFilter = document.getElementById("docket-type-filter");
  if (typeFilter) {
    typeFilter.addEventListener("change", () => {
      state.docket.caseType = typeFilter.value;
      state.docket.page = 1;
      renderDocketTable();
    });
  }

  // Sort select
  const sortSelect = document.getElementById("docket-sort-select");
  if (sortSelect) {
    sortSelect.addEventListener("change", () => {
      state.docket.sort = sortSelect.value;
      state.docket.page = 1;
      renderDocketTable();
    });
  }

  // Pagination prev/next
  const prevBtn = document.getElementById("btn-page-prev");
  const nextBtn = document.getElementById("btn-page-next");
  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (state.docket.page > 1) {
        state.docket.page -= 1;
        renderDocketTable();
      }
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (state.docket.page < state.docket.totalPages) {
        state.docket.page += 1;
        renderDocketTable();
      }
    });
  }
}

// ============================================================
// View: Case Detail (#/case/:id)
// ============================================================

async function renderCaseDetailView(caseId) {
  const contentEl = document.getElementById("case-detail-content");
  const titleEl = document.getElementById("case-detail-title");
  const subEl = document.getElementById("case-detail-sub");
  const precList = document.getElementById("case-precedents-list");

  titleEl.textContent = `Case #${esc(caseId)}`;
  subEl.textContent = "Loading judicial intelligence record…";
  precList.innerHTML = `<div class="td-status"><div class="spinner"></div><br/>Retrieving precedent matches…</div>`;

  try {
    const data = await fetchCase(caseId);

    const c = data.case || data;
    const prediction = data.prediction || c;
    const precedents = data.precedents || data.top_precedents || [];
    const precFeat = data.precedent_features || c;

    // Header title
    titleEl.textContent = c.title || `Case ${c.case_no}`;
    subEl.textContent = `${c.case_no} · ${c.court || "High Court"} · Filed on ${c.filing_date || "—"}`;

    // Case info particulars
    document.getElementById("c-caseno").textContent = c.case_no || "—";
    document.getElementById("c-title").textContent = c.title || "—";
    document.getElementById("c-type").textContent = c.case_type || "—";
    document.getElementById("c-court").textContent = c.court || "High Court";
    document.getElementById("c-filing").textContent = c.filing_date || "—";
    document.getElementById("c-status").textContent = c.status || "Pending";
    document.getElementById("c-hearings").textContent = c.hearings_so_far ?? 0;
    document.getElementById("c-parties").textContent = c.num_parties ?? 2;
    document.getElementById("c-appeal").textContent = c.is_appeal ? "Yes (Appellate Proceeding)" : "No (Original Jurisdiction)";
    document.getElementById("c-desc").textContent = c.description || "No pleadings summary filed.";

    // Prediction Card
    const predDays = prediction.predicted_days != null ? Math.round(prediction.predicted_days) : "—";
    document.getElementById("c-pred-days").textContent = predDays;

    if (prediction.lower_band != null && prediction.upper_band != null) {
      document.getElementById("c-pred-band").textContent = `Confidence Band: ${Math.round(prediction.lower_band)} – ${Math.round(prediction.upper_band)} days`;
    } else {
      document.getElementById("c-pred-band").textContent = "Confidence Band: ±45 days";
    }

    // Bucket badge
    const bucketEl = document.getElementById("c-bucket-badge");
    const bucketVal = prediction.bucket || c.bucket || "Standard";
    bucketEl.className = "badge";
    const bLower = bucketVal.toLowerCase();
    if (bLower.includes("fast")) {
      bucketEl.className = "badge badge--fast";
      bucketEl.textContent = "Fast-track";
    } else if (bLower.includes("attention") || bLower.includes("needs")) {
      bucketEl.className = "badge badge--attention";
      bucketEl.textContent = "Needs Attention";
    } else {
      bucketEl.className = "badge badge--standard";
      bucketEl.textContent = "Standard";
    }

    // Priority gauge (0-100)
    const pScore = prediction.priority_score != null ? Math.round(prediction.priority_score) : 50;
    document.getElementById("c-priority-score").textContent = `${pScore} / 100`;
    const fillPercent = Math.max(0, Math.min(100, pScore));
    document.getElementById("c-priority-fill").style.width = `${fillPercent}%`;
    if (fillPercent > 70) {
      document.getElementById("c-priority-fill").style.backgroundColor = "#7A1F2B";
    } else {
      document.getElementById("c-priority-fill").style.backgroundColor = "#1E3B3A";
    }

    // Plain English why
    const whyText = prediction.why_text || c.why_text || "Case duration calculated based on statutory category baseline, hearings overhead, and precedent density.";
    document.getElementById("c-why-text").textContent = whyText;

    // 4 Precedent Indicators
    const top1 = precFeat.top1_similarity != null ? Number(precFeat.top1_similarity).toFixed(2) : "—";
    const mean5 = precFeat.mean_top5_similarity != null ? Number(precFeat.mean_top5_similarity).toFixed(2) : "—";
    const countAbove = precFeat.count_above_threshold != null ? precFeat.count_above_threshold : "—";
    const spread = precFeat.similarity_spread != null ? Number(precFeat.similarity_spread).toFixed(2) : "—";

    document.getElementById("c-feat-top1").textContent = top1;
    document.getElementById("c-feat-mean5").textContent = mean5;
    document.getElementById("c-feat-count").textContent = countAbove;
    document.getElementById("c-feat-spread").textContent = spread;

    // Top 5 Matching Precedents
    if (!precedents.length) {
      precList.innerHTML = `<div class="td-status">No matching precedents registered for this matter.</div>`;
    } else {
      precList.innerHTML = precedents.slice(0, 5).map((p, idx) => {
        const citation = p.citation || `[${p.year || 2022}] INSC ${idx + 1}`;
        const pTitle = p.title || "Judicial Precedent";
        const meta = `${esc(p.court || "High Court")} &middot; ${esc(String(p.year || "2022"))} &middot; ${esc(p.case_type || "")}`;
        const summary = p.summary || p.text_content?.slice(0, 300) || "Summary pending.";
        const sim = p.similarity ?? p.score ?? 0;
        const fullText = p.text_content || "";

        return `
          <article class="law-entry">
            <div class="law-entry-header">
              <div class="law-title-wrap">
                <span class="law-rank">${idx + 1}.</span>
                <h3 class="law-title" style="font-size:1rem;">${esc(pTitle)}</h3>
              </div>
              <span class="law-citation">${esc(citation)}</span>
            </div>
            <div class="law-meta">${meta}</div>
            <div class="law-summary">${esc(summary)}</div>
            <div class="law-footer">
              <div class="law-sim-row">
                <span class="law-sim-label">Similarity</span>
                ${renderSimBar(sim)}
              </div>
              ${fullText ? `<button type="button" class="law-toggle-btn" data-toggle="cp-ft-${idx}">Show judgment text &darr;</button>` : ""}
            </div>
            ${fullText ? `<div id="cp-ft-${idx}" class="law-full-text" hidden>${esc(fullText)}</div>` : ""}
          </article>
        `;
      }).join("");

      // Bind toggles
      precList.querySelectorAll(".law-toggle-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          const target = document.getElementById(btn.dataset.toggle);
          if (target) {
            const isHidden = target.hidden;
            target.hidden = !isHidden;
            btn.innerHTML = isHidden ? "Hide judgment text &uarr;" : "Show judgment text &darr;";
          }
        });
      });
    }

  } catch (err) {
    contentEl.innerHTML = "";
    contentEl.appendChild(renderErrorBox(err.message, () => renderCaseDetailView(caseId)));
  }
}

// ============================================================
// View: Add Case (#/add)
// ============================================================

function setupAddCaseForm() {
  const form = document.getElementById("add-case-form");
  const statusEl = document.getElementById("add-form-status");
  const submitBtn = document.getElementById("btn-submit-case");

  if (!form) return;

  // Set default filing date to today
  const filingInput = document.getElementById("form-filing");
  if (filingInput && !filingInput.value) {
    filingInput.value = new Date().toISOString().split("T")[0];
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    statusEl.textContent = "";
    statusEl.className = "form-status-msg";

    if (!form.checkValidity()) {
      statusEl.textContent = "Please fill in all required fields.";
      statusEl.className = "form-status-msg error";
      form.reportValidity();
      return;
    }

    const fd = new FormData(form);
    const payload = {
      title: (fd.get("title") || "").trim(),
      description: (fd.get("description") || "").trim(),
      case_type: fd.get("case_type"),
      court: (fd.get("court") || "High Court of Delhi").trim(),
      filing_date: fd.get("filing_date"),
      hearings_so_far: parseInt(fd.get("hearings_so_far"), 10) || 0,
      num_parties: parseInt(fd.get("num_parties"), 10) || 2,
      is_appeal: fd.get("is_appeal") === "on" ? 1 : 0,
      status: fd.get("status") || "Pending",
    };

    submitBtn.disabled = true;
    statusEl.textContent = "Analyzing pleadings and scoring matter…";

    try {
      const res = await addCase(payload);
      statusEl.textContent = "Case successfully registered. Redirecting…";

      const newId = res?.case?.id ?? res?.id ?? res?.case_no;
      form.reset();

      setTimeout(() => {
        if (newId != null) {
          window.location.hash = `#/case/${newId}`;
        } else {
          window.location.hash = `#/docket`;
        }
      }, 600);

    } catch (err) {
      statusEl.textContent = `Error: ${err.message}`;
      statusEl.className = "form-status-msg error";
    } finally {
      submitBtn.disabled = false;
    }
  });
}

// ============================================================
// Router & Lifecycle
// ============================================================

function updateActiveNav(route) {
  document.querySelectorAll(".side-nav .nav-item").forEach(item => {
    const itemRoute = item.dataset.route;
    if (itemRoute === route) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });
}

function handleRoute() {
  const rawHash = window.location.hash || "#/";
  const [pathPart, queryPart] = rawHash.split("?");
  const normalizedPath = pathPart.replace(/\/+$/, "") || "#";

  // Hide all views first
  document.querySelectorAll(".route-view").forEach(v => {
    v.hidden = true;
  });

  if (normalizedPath === "#" || normalizedPath === "#/") {
    // Overview
    state.currentRoute = "overview";
    updateActiveNav("overview");
    const v = document.getElementById("view-overview");
    if (v) v.hidden = false;
    renderOverviewView();

  } else if (normalizedPath === "#/search") {
    // Search
    state.currentRoute = "search";
    updateActiveNav("search");
    const v = document.getElementById("view-search");
    if (v) v.hidden = false;

    // Check query params
    if (queryPart) {
      const params = new URLSearchParams(queryPart);
      const q = params.get("q");
      if (q) {
        executeSearch(q);
        return;
      }
    }
    // If input already has query, run it, otherwise show state box
    const inputVal = (document.getElementById("search-input")?.value || "").trim();
    if (inputVal) {
      executeSearch();
    } else {
      document.getElementById("search-results-header").hidden = true;
      document.getElementById("search-state-area").innerHTML = `
        <div class="state-box">
          <h3 class="state-title">Enter a Search Query or Legal Controversy</h3>
          <p class="state-desc">Type facts, statutes, or pick one of the example queries above to search matching Indian judgments.</p>
        </div>
      `;
    }

  } else if (normalizedPath === "#/docket") {
    // Docket
    state.currentRoute = "docket";
    updateActiveNav("docket");
    const v = document.getElementById("view-docket");
    if (v) v.hidden = false;
    renderDocketTable();

  } else if (normalizedPath.startsWith("#/case/")) {
    // Case detail
    const caseId = normalizedPath.replace("#/case/", "");
    state.currentRoute = "case";
    updateActiveNav("docket");
    const v = document.getElementById("view-case");
    if (v) v.hidden = false;
    renderCaseDetailView(caseId);

  } else if (normalizedPath === "#/add") {
    // Add case
    state.currentRoute = "add";
    updateActiveNav("add");
    const v = document.getElementById("view-add");
    if (v) v.hidden = false;
    const filingInput = document.getElementById("form-filing");
    if (filingInput && !filingInput.value) {
      filingInput.value = new Date().toISOString().split("T")[0];
    }

  } else {
    // Fallback to overview
    window.location.hash = "#/";
  }
}

// ============================================================
// App Bootstrap
// ============================================================

document.addEventListener("DOMContentLoaded", () => {
  setupOverviewSearch();
  setupSearchListeners();
  setupDocketListeners();
  setupAddCaseForm();

  // Listen to hash changes
  window.addEventListener("hashchange", handleRoute);

  // Initial route
  handleRoute();
});
