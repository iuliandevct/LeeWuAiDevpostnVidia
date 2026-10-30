/**
 * LeeWu AI — AI Operations & Cost Observatory
 * Interactive Client-Side Telemetry, Canvas Visualizations & FinOps Logic
 */

(function () {
  "use strict";

  // Application State
  const state = {
    activeTab: "overview",
    currency: "EUR",
    includeSynthetic: true,
    autoRefresh: true,
    refreshTimer: null,
    adminToken: localStorage.getItem("leewu_admin_token") || "",
    filters: {
      model: "",
      survey_id: "",
      status: "",
      page: 1,
      page_size: 20
    },
    cache: {
      overview: null,
      usage: null,
      models: null,
      costs: null,
      alerts: null,
      requests: null,
      health: null
    }
  };

  // API Client Helper
  async function apiFetch(endpoint, options = {}) {
    const headers = options.headers || {};
    if (state.adminToken) {
      headers["Authorization"] = `Bearer ${state.adminToken}`;
    }
    options.headers = headers;

    try {
      const res = await fetch(endpoint, options);
      if (res.status === 401) {
        showAuthModal();
        throw new Error("Unauthorized: Administrator key required.");
      }
      if (!res.ok) {
        throw new Error(`API Error ${res.status}: ${res.statusText}`);
      }
      return await res.json();
    } catch (err) {
      console.warn("[AIOps Client]", err.message);
      throw err;
    }
  }

  // Formatters
  function formatNumber(num) {
    if (num === null || num === undefined) return "0";
    return new Intl.NumberFormat().format(num);
  }

  function formatCost(amount, currency = state.currency) {
    if (amount === null || amount === undefined || amount < 0) return "Pricing unavailable";
    const symbol = currency === "EUR" ? "€" : "$";
    if (amount < 0.001 && amount > 0) {
      return `${symbol}${amount.toFixed(5)}`;
    }
    return `${symbol}${amount.toFixed(4)}`;
  }

  function formatLatency(ms) {
    if (!ms) return "0 ms";
    if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
    return `${Math.round(ms)} ms`;
  }

  function formatTimestamp(isoStr) {
    if (!isoStr) return "-";
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + 
             " (" + d.toISOString().split("T")[0].substring(5) + ")";
    } catch (e) {
      return isoStr;
    }
  }

  // Auth Handling
  function showAuthModal() {
    const key = prompt("LeeWu AI Observatory is protected. Enter Administrator Access Key (or leave blank for localhost dev):");
    if (key !== null) {
      state.adminToken = key.trim();
      localStorage.setItem("leewu_admin_token", state.adminToken);
      loadAllData();
    }
  }

  // Data Loading Dispatcher
  async function loadAllData() {
    const synthParam = `include_synthetic=${state.includeSynthetic}`;
    const currParam = `currency=${state.currency}`;

    try {
      // 1. Health & Overview
      const [overview, health] = await Promise.all([
        apiFetch(`/api/ai-ops/overview?${currParam}&${synthParam}`),
        apiFetch(`/api/ai-ops/health`)
      ]);
      state.cache.overview = overview;
      state.cache.health = health;
      renderOverviewHUD(overview, health);

      // 2. Tab Specific Loads
      if (state.activeTab === "overview" || state.activeTab === "costs") {
        const [usage, costs] = await Promise.all([
          apiFetch(`/api/ai-ops/usage?period=daily&limit=14&${synthParam}`),
          apiFetch(`/api/ai-ops/costs?${synthParam}`)
        ]);
        state.cache.usage = usage;
        state.cache.costs = costs;
        renderSpendingChart(usage);
        renderCostBreakdowns(costs);
      }

      if (state.activeTab === "models" || state.activeTab === "overview") {
        const models = await apiFetch(`/api/ai-ops/models?${synthParam}`);
        state.cache.models = models;
        renderModelsTable(models);
      }

      if (state.activeTab === "requests") {
        await loadRequestsTable();
      }

      if (state.activeTab === "alerts" || state.activeTab === "overview") {
        const alerts = await apiFetch(`/api/ai-ops/alerts`);
        state.cache.alerts = alerts;
        renderAlertsFeed(alerts);
      }

      document.getElementById("last-updated").textContent = new Date().toLocaleTimeString();
    } catch (err) {
      console.error("[AIOps Load Error]", err);
    }
  }

  // Render Overview HUD
  function renderOverviewHUD(ov, hl) {
    if (!ov) return;
    document.getElementById("kpi-total-requests").textContent = formatNumber(ov.total_requests);
    document.getElementById("kpi-total-tokens").textContent = formatNumber(ov.total_tokens);
    document.getElementById("kpi-tokens-sub").textContent = 
      `In: ${formatNumber(ov.total_prompt_tokens)} | Out: ${formatNumber(ov.total_completion_tokens)}`;
    
    document.getElementById("kpi-total-cost").textContent = formatCost(ov.display_cost, ov.currency);
    document.getElementById("kpi-avg-latency").textContent = formatLatency(ov.avg_latency_ms);
    
    const sr = document.getElementById("kpi-success-rate");
    sr.textContent = `${ov.success_rate_pct}%`;
    sr.className = ov.success_rate_pct >= 95 ? "kpi-value text-success" : (ov.success_rate_pct >= 85 ? "kpi-value text-warning" : "kpi-value text-danger");
    document.getElementById("kpi-failures-sub").textContent = `${ov.failure_count} failures logged`;

    // Active Models & Alerts
    document.getElementById("kpi-active-models").textContent = ov.active_models_count || "0";
    const alertBadge = document.getElementById("kpi-alerts-badge");
    if (ov.unresolved_alerts_count > 0) {
      alertBadge.textContent = `${ov.unresolved_alerts_count} Active`;
      alertBadge.className = "brand-badge text-danger";
    } else {
      alertBadge.textContent = "0 Alerts";
      alertBadge.className = "brand-badge text-success";
    }

    // Budget Progress Bars
    if (ov.budget) {
      const b = ov.budget;
      document.getElementById("budget-daily-label").textContent = 
        `${formatCost(b.daily_spend_eur, "EUR")} / ${formatCost(b.daily_limit_eur, "EUR")} (${b.daily_pct_consumed}%)`;
      const dailyBar = document.getElementById("meter-daily-fill");
      dailyBar.style.width = `${Math.min(100, b.daily_pct_consumed)}%`;
      dailyBar.style.backgroundColor = b.daily_pct_consumed >= 90 ? "var(--accent-red)" : (b.daily_pct_consumed >= 75 ? "var(--accent-yellow)" : "var(--accent-green)");

      document.getElementById("budget-monthly-label").textContent = 
        `${formatCost(b.monthly_spend_eur, "EUR")} / ${formatCost(b.monthly_limit_eur, "EUR")} (${b.monthly_pct_consumed}%)`;
      const monthlyBar = document.getElementById("meter-monthly-fill");
      monthlyBar.style.width = `${Math.min(100, b.monthly_pct_consumed)}%`;
      monthlyBar.style.backgroundColor = b.monthly_pct_consumed >= 90 ? "var(--accent-red)" : (b.monthly_pct_consumed >= 75 ? "var(--accent-yellow)" : "var(--accent-blue)");
    }
  }

  // Render Spending & Request Canvas Chart
  function renderSpendingChart(timelineData) {
    const canvas = document.getElementById("chart-spending");
    if (!canvas || !timelineData || timelineData.length === 0) return;

    const ctx = canvas.getContext("2d");
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    canvas.width = width * window.devicePixelRatio;
    canvas.height = height * window.devicePixelRatio;
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

    ctx.clearRect(0, 0, width, height);

    const padding = { top: 20, right: 30, bottom: 35, left: 50 };
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;

    const maxCost = Math.max(...timelineData.map(d => d.cost_eur || 0), 0.05);
    const maxReqs = Math.max(...timelineData.map(d => d.request_count || 0), 5);

    // Grid Lines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(padding.left + chartW, y);
      ctx.stroke();

      const labelVal = (maxCost * (1 - i / 4)).toFixed(3);
      ctx.fillStyle = "rgba(255, 255, 255, 0.3)";
      ctx.font = "10px monospace";
      ctx.fillText(`€${labelVal}`, 5, y + 3);
    }

    const n = timelineData.length;
    const barWidth = Math.max(6, (chartW / n) * 0.55);

    // Draw Bars (Cost)
    timelineData.forEach((d, idx) => {
      const x = padding.left + (chartW / n) * idx + (chartW / n - barWidth) / 2;
      const barH = ((d.cost_eur || 0) / maxCost) * chartH;
      const y = padding.top + chartH - barH;

      const grad = ctx.createLinearGradient(x, y, x, y + barH);
      grad.addColorStop(0, "#f5a623");
      grad.addColorStop(1, "rgba(245, 166, 35, 0.1)");

      ctx.fillStyle = grad;
      ctx.fillRect(x, y, barWidth, barH);

      // Date Label
      if (idx % Math.ceil(n / 7) === 0 || idx === n - 1) {
        ctx.fillStyle = "rgba(255, 255, 255, 0.5)";
        ctx.font = "10px monospace";
        const dateShort = d.bucket.substring(5);
        ctx.fillText(dateShort, x - 2, padding.top + chartH + 20);
      }
    });

    // Draw Line (Requests)
    ctx.beginPath();
    ctx.strokeStyle = "#00e676";
    ctx.lineWidth = 2;
    timelineData.forEach((d, idx) => {
      const x = padding.left + (chartW / n) * idx + (chartW / n) / 2;
      const y = padding.top + chartH - ((d.request_count || 0) / maxReqs) * chartH;
      if (idx === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Data points on line
    timelineData.forEach((d, idx) => {
      const x = padding.left + (chartW / n) * idx + (chartW / n) / 2;
      const y = padding.top + chartH - ((d.request_count || 0) / maxReqs) * chartH;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#00e676";
      ctx.fill();
    });
  }

  // Render Cost Breakdowns
  function renderCostBreakdowns(costs) {
    if (!costs) return;

    // By Model
    const modelTbody = document.getElementById("table-cost-model-body");
    if (modelTbody) {
      modelTbody.innerHTML = costs.by_model.map(m => `
        <tr>
          <td class="code-cell font-weight-bold">${escapeHtml(m.model_id)}</td>
          <td>${formatNumber(m.request_count)}</td>
          <td>${formatNumber(m.total_tokens)}</td>
          <td class="font-weight-bold text-warning">${formatCost(m.cost_eur, "EUR")}</td>
        </tr>
      `).join("");
    }

    // By Survey
    const srvTbody = document.getElementById("table-cost-survey-body");
    if (srvTbody) {
      srvTbody.innerHTML = costs.by_survey.map(s => `
        <tr>
          <td class="code-cell">${escapeHtml(s.survey_id)}</td>
          <td>${formatNumber(s.request_count)}</td>
          <td>${formatNumber(s.total_tokens)}</td>
          <td class="font-weight-bold text-success">${formatCost(s.cost_eur, "EUR")}</td>
        </tr>
      `).join("");
    }
  }

  // Render Model Inventory Table
  function renderModelsTable(models) {
    const tbody = document.getElementById("table-models-body");
    if (!tbody || !models) return;

    tbody.innerHTML = models.map(m => {
      const isVerified = m.is_verified === 1;
      const badge = isVerified 
        ? `<span class="status-badge badge-success">VERIFIED LIVE</span>` 
        : `<span class="status-badge badge-warning">CONFIGURED</span>`;
      
      const pricingStr = m.pricing_status === "VERIFIED"
        ? `In: €${m.input_price_per_m} / Out: €${m.output_price_per_m}`
        : `<span class="text-danger">Unavailable</span>`;

      return `
        <tr>
          <td>
            <div style="font-weight:700;">${escapeHtml(m.display_name)}</div>
            <div class="code-cell text-muted">${escapeHtml(m.model_id)}</div>
          </td>
          <td><span class="status-badge badge-info">${escapeHtml(m.category)}</span></td>
          <td>${badge}</td>
          <td class="code-cell">${pricingStr}</td>
          <td>${formatNumber(m.request_count)}</td>
          <td>${formatNumber(m.total_tokens)}</td>
          <td>${formatLatency(m.avg_latency_ms)}</td>
          <td>${formatCost(m.total_cost_eur, "EUR")}</td>
          <td><span class="${m.error_rate_pct > 5 ? 'text-danger' : 'text-success'}">${m.error_rate_pct}%</span></td>
        </tr>
      `;
    }).join("");
  }

  // Load Requests Explorer Table
  async function loadRequestsTable() {
    const f = state.filters;
    const synthParam = `include_synthetic=${state.includeSynthetic}`;
    let url = `/api/ai-ops/requests?page=${f.page}&page_size=${f.page_size}&${synthParam}`;
    if (f.model) url += `&model=${encodeURIComponent(f.model)}`;
    if (f.survey_id) url += `&survey_id=${encodeURIComponent(f.survey_id)}`;
    if (f.status) url += `&status=${encodeURIComponent(f.status)}`;

    try {
      const data = await apiFetch(url);
      state.cache.requests = data;

      const tbody = document.getElementById("table-requests-body");
      if (!tbody) return;

      tbody.innerHTML = data.items.map(r => {
        const isSuccess = r.status === "SUCCESS";
        const badge = isSuccess
          ? `<span class="status-badge badge-success">200 OK</span>`
          : `<span class="status-badge badge-danger">${escapeHtml(r.status)}</span>`;

        const synthBadge = r.is_synthetic === 1 
          ? `<span class="status-badge badge-warning" style="font-size:9px;">DEMO</span>` 
          : `<span class="status-badge badge-info" style="font-size:9px;">LIVE</span>`;

        return `
          <tr>
            <td class="code-cell">${formatTimestamp(r.timestamp_utc)}</td>
            <td class="code-cell font-weight-bold">${escapeHtml(r.model_id.split("/").pop())}</td>
            <td class="code-cell">${escapeHtml(r.survey_id || "-")}</td>
            <td>${formatNumber(r.total_tokens)} <span class="text-dim">(${r.prompt_tokens}/${r.completion_tokens})</span></td>
            <td class="code-cell text-warning">${formatCost(r.estimated_cost, r.currency)}</td>
            <td class="code-cell">${formatLatency(r.latency_ms)}</td>
            <td>${badge} ${synthBadge}</td>
            <td class="code-cell text-dim" style="font-size:10px;">${escapeHtml(r.request_id)}</td>
          </tr>
        `;
      }).join("");

      document.getElementById("requests-pagination-info").textContent = 
        `Page ${data.page} of ${data.total_pages} (${formatNumber(data.total)} total requests)`;
      document.getElementById("btn-prev-page").disabled = data.page <= 1;
      document.getElementById("btn-next-page").disabled = data.page >= data.total_pages;
    } catch (err) {
      console.error("[Requests Load Error]", err);
    }
  }

  // Render Anomaly Alerts Feed
  function renderAlertsFeed(alerts) {
    const container = document.getElementById("alerts-container");
    if (!container || !alerts) return;

    if (alerts.length === 0) {
      container.innerHTML = `<div class="text-muted" style="padding:16px;">Zero operational alerts detected. AI pipelines running within normal thresholds.</div>`;
      return;
    }

    container.innerHTML = alerts.map(a => `
      <div class="alert-item severity-${a.severity}">
        <div class="alert-content">
          <div class="alert-title">${escapeHtml(a.message)}</div>
          <div class="alert-meta">
            <span>Type: <b>${escapeHtml(a.alert_type)}</b></span> • 
            <span>Severity: <b>${escapeHtml(a.severity)}</b></span> • 
            <span>Logged: ${formatTimestamp(a.timestamp_utc)}</span>
          </div>
        </div>
        ${!a.resolved ? `
          <button class="btn btn-sm" onclick="window.AIOps.resolveAlert(${a.id})">Resolve</button>
        ` : `<span class="text-success" style="font-size:11px;">✓ Resolved</span>`}
      </div>
    `).join("");
  }

  // Resolve Alert Action
  async function resolveAlert(alertId) {
    try {
      await apiFetch("/api/ai-ops/alerts/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ alert_id: alertId })
      });
      loadAllData();
    } catch (e) {
      alert("Failed resolving alert: " + e.message);
    }
  }

  // Seed / Clear Synthetic Demo
  async function seedDemoData() {
    try {
      const res = await apiFetch("/api/ai-ops/seed-demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ count: 35 })
      });
      alert(`Success! Seeded ${res.seeded_events} synthetic demonstration events.`);
      loadAllData();
    } catch (e) {
      alert("Failed seeding demo: " + e.message);
    }
  }

  async function clearDemoData() {
    if (!confirm("Are you sure you want to clear all synthetic demonstration telemetry? Real events will be preserved.")) return;
    try {
      const res = await apiFetch("/api/ai-ops/clear-demo", { method: "POST" });
      alert(`Cleared ${res.cleared_events} synthetic demo records.`);
      loadAllData();
    } catch (e) {
      alert("Failed clearing demo: " + e.message);
    }
  }

  // Trigger Live AI Inspection Test
  async function triggerLiveInference() {
    const btn = document.getElementById("btn-trigger-ai");
    if (btn) btn.disabled = true;
    try {
      const res = await fetch("/api/surveys/LW-DEMO-001/ai-inspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const data = await res.json();
      alert(`Live NVIDIA Nemotron assessment complete! Model: ${data.model}. Telemetry recorded.`);
      loadAllData();
    } catch (e) {
      alert("Live AI inspection failed: " + e.message);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // Export Data Download
  function downloadExport(format) {
    const synthParam = `include_synthetic=${state.includeSynthetic}`;
    const url = `/api/ai-ops/export?format=${format}&${synthParam}`;
    window.location.href = url;
  }

  // Utility Escaper
  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initialization & Event Binding
  function init() {
    // Tab switching
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        state.activeTab = btn.dataset.tab;

        document.querySelectorAll(".tab-pane").forEach(pane => pane.style.display = "none");
        const activePane = document.getElementById(`pane-${state.activeTab}`);
        if (activePane) activePane.style.display = "block";

        loadAllData();
      });
    });

    // Synthetic Toggle
    const synthToggle = document.getElementById("toggle-synthetic");
    if (synthToggle) {
      synthToggle.addEventListener("change", (e) => {
        state.includeSynthetic = e.target.checked;
        const banner = document.getElementById("mode-banner");
        if (banner) {
          banner.className = state.includeSynthetic ? "banner-mode banner-synthetic" : "banner-mode banner-live";
          banner.innerHTML = state.includeSynthetic
            ? `<span>⚠️ <b>SYNTHETIC DEMO MODE ACTIVE</b> — Telemetry displays real requests combined with isolated synthetic benchmarks for demonstration.</span>`
            : `<span>🟢 <b>STRICT LIVE PRODUCTION MODE</b> — Displaying exclusively verified live inference events.</span>`;
        }
        loadAllData();
      });
    }

    // Currency Switcher
    const currSelect = document.getElementById("select-currency");
    if (currSelect) {
      currSelect.addEventListener("change", (e) => {
        state.currency = e.target.value;
        loadAllData();
      });
    }

    // Request Explorer Filters & Pagination
    const btnApplyFilter = document.getElementById("btn-apply-filters");
    if (btnApplyFilter) {
      btnApplyFilter.addEventListener("click", () => {
        state.filters.model = document.getElementById("filter-model").value;
        state.filters.survey_id = document.getElementById("filter-survey").value.trim();
        state.filters.status = document.getElementById("filter-status").value;
        state.filters.page = 1;
        loadRequestsTable();
      });
    }

    const btnPrev = document.getElementById("btn-prev-page");
    if (btnPrev) {
      btnPrev.addEventListener("click", () => {
        if (state.filters.page > 1) {
          state.filters.page--;
          loadRequestsTable();
        }
      });
    }

    const btnNext = document.getElementById("btn-next-page");
    if (btnNext) {
      btnNext.addEventListener("click", () => {
        state.filters.page++;
        loadRequestsTable();
      });
    }

    // Buttons
    document.getElementById("btn-refresh")?.addEventListener("click", loadAllData);
    document.getElementById("btn-seed-demo")?.addEventListener("click", seedDemoData);
    document.getElementById("btn-clear-demo")?.addEventListener("click", clearDemoData);
    document.getElementById("btn-trigger-ai")?.addEventListener("click", triggerLiveInference);
    document.getElementById("btn-export-csv")?.addEventListener("click", () => downloadExport("csv"));
    document.getElementById("btn-export-json")?.addEventListener("click", () => downloadExport("json"));
    document.getElementById("btn-auth-config")?.addEventListener("click", showAuthModal);

    // Initial Load & Polling
    loadAllData();
    setInterval(() => {
      if (state.autoRefresh) {
        loadAllData();
      }
    }, 15000);
  }

  // Global namespace for inline callbacks
  window.AIOps = {
    resolveAlert,
    downloadExport
  };

  document.addEventListener("DOMContentLoaded", init);
})();
