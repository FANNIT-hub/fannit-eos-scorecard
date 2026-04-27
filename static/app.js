// EOS L10 Scorecard - frontend
// Reads goals + YTD + last-N weekly actuals from /api/scorecard.

const ALL_AGENCIES = ["FANNIT", "TMSA", "HMC", "IPA"];

let state = {
  agencies: [],
  unmapped: [],
  current: null,
};

async function init() {
  try {
    const res = await fetch("/api/agencies");
    const data = await res.json();
    state.agencies = data.agencies || [];
    state.unmapped = ALL_AGENCIES.filter(a => !state.agencies.includes(a));
    state.current = state.agencies[0] || null;
  } catch (err) {
    console.error("agency list failed", err);
  }
  renderSidebar();
  if (state.current) await loadAgency(state.current);
  else showError("No agencies mapped yet.");
}

function renderSidebar() {
  const ul = document.getElementById("agency-nav");
  ul.innerHTML = "";
  for (const a of state.agencies) {
    const li = document.createElement("li");
    li.className = "agency-item" + (a === state.current ? " active" : "");
    li.innerHTML = `<span class="icon">📁</span>${a}`;
    li.addEventListener("click", () => loadAgency(a));
    ul.appendChild(li);
  }
  for (const a of state.unmapped) {
    const li = document.createElement("li");
    li.className = "agency-item unmapped disabled";
    li.innerHTML = `<span class="icon">📁</span>${a}`;
    li.title = "Block offsets not yet wired";
    ul.appendChild(li);
  }
}

async function loadAgency(agency) {
  state.current = agency;
  document.getElementById("page-title").textContent = `${agency} — EOS Scorecard`;
  renderSidebar();
  document.getElementById("kpi-grid").innerHTML = '<div class="placeholder">Reading sheet…</div>';
  document.getElementById("detail-table-wrap").innerHTML = "";

  try {
    const res = await fetch(`/api/scorecard?agency=${encodeURIComponent(agency)}`);
    const data = await res.json();
    if (!res.ok) {
      showError(`API error: ${data.error || res.status}`);
      return;
    }
    renderGrid(data.kpis || []);
    renderDetailTable(data.kpis || []);
  } catch (err) {
    showError(`Network error: ${err.message}`);
  }
}

function renderGrid(kpis) {
  const grid = document.getElementById("kpi-grid");
  grid.innerHTML = "";
  if (!kpis.length) {
    grid.innerHTML = '<div class="placeholder">No KPI rows.</div>';
    return;
  }
  for (const k of kpis) grid.appendChild(buildCard(k));
}

function buildCard(k) {
  const card = document.createElement("div");
  card.className = "kpi-card";

  const title = document.createElement("div");
  title.className = "kpi-title";
  title.textContent = k.label;

  const source = document.createElement("div");
  source.className = "kpi-source";
  source.textContent = k.source || "—";

  const value = document.createElement("div");
  value.className = "kpi-value";
  value.textContent = formatValue(k.current_week_value, k.fmt);

  const weekTag = document.createElement("div");
  weekTag.className = "kpi-week-tag";
  weekTag.textContent = k.current_week_date ? `Week of ${k.current_week_date}` : "no weekly data";

  const meta = document.createElement("div");
  meta.className = "kpi-meta";
  const goalEl = document.createElement("span");
  goalEl.textContent = `Goal: ${formatValue(k.weekly_goal, k.fmt)}`;
  const hitEl = document.createElement("span");
  hitEl.className = "kpi-hit " + hitColor(k.weekly_hit_pct, k.metric_type, k.label);
  hitEl.textContent = formatHit(k.weekly_hit_pct);
  meta.appendChild(goalEl);
  meta.appendChild(hitEl);

  const dot = document.createElement("div");
  dot.className = "kpi-status-dot " + hitColor(k.weekly_hit_pct, k.metric_type, k.label);

  card.appendChild(dot);
  card.appendChild(title);
  card.appendChild(source);
  card.appendChild(value);
  card.appendChild(weekTag);
  card.appendChild(meta);
  return card;
}

function renderDetailTable(kpis) {
  const wrap = document.getElementById("detail-table-wrap");
  if (!kpis.length) { wrap.innerHTML = ""; return; }

  // Use the first KPI's week dates as the column headers (all KPIs share the
  // same week columns since they live in the same row band).
  const allDates = new Set();
  for (const k of kpis) for (const w of (k.weeks || [])) allDates.add(w.date);
  const dateCols = [...allDates].slice(-8);  // up to 8 trailing

  let html = `
    <h3 class="section-title">Weekly Scorecard Detail</h3>
    <div class="detail-table">
      <table>
        <thead>
          <tr>
            <th>KPI</th>
            <th>Data Source</th>
            <th>Annual Goal</th>
            <th>YTD Actual</th>
            <th>Hit %</th>
            ${dateCols.map(d => `<th>${d}</th>`).join("")}
          </tr>
        </thead>
        <tbody>
  `;

  for (const k of kpis) {
    const wMap = {};
    for (const w of (k.weeks || [])) wMap[w.date] = w.value;
    const ytdHitClass = hitColor(k.hit_pct, k.metric_type, k.label);
    html += `
      <tr>
        <td class="row-label">${k.label}</td>
        <td class="row-source">${k.source}</td>
        <td>${formatValue(k.annual_goal, k.fmt)}</td>
        <td>${formatValue(k.ytd_actual, k.fmt)}</td>
        <td class="${ytdHitClass}">${formatHit(k.hit_pct)}</td>
        ${dateCols.map(d => `<td>${d in wMap ? formatValue(wMap[d], k.fmt) : "—"}</td>`).join("")}
      </tr>
    `;
  }

  html += `</tbody></table></div>`;
  wrap.innerHTML = html;
}

function formatValue(v, fmt) {
  if (v === null || v === undefined) return "—";
  if (fmt === "currency") {
    if (Math.abs(v) >= 1_000_000) return "$" + (v / 1_000_000).toFixed(1) + "M";
    if (Math.abs(v) >= 1_000) return "$" + (v / 1_000).toFixed(1) + "K";
    return "$" + v.toFixed(0);
  }
  if (fmt === "percent") {
    const n = Math.abs(v) <= 1 ? v * 100 : v;
    return n.toFixed(2) + "%";
  }
  if (Math.abs(v) >= 10_000) return Math.round(v).toLocaleString();
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(1);
}

function formatHit(p) {
  if (p === null || p === undefined) return "—";
  const n = Math.abs(p) <= 1 ? p * 100 : p;
  return n.toFixed(1) + "%";
}

function hitColor(p, metric_type, label) {
  if (p === null || p === undefined) return "gray";
  let n = Math.abs(p) <= 1 ? p * 100 : p;
  // Inverted (lower is better): Churn, AR Past 30
  const inverted = (label && (label.includes("Churn") || label.includes("AR Past 30")));
  if (inverted) {
    if (n <= 50) return "green";
    if (n <= 100) return "yellow";
    return "red";
  }
  if (n >= 100) return "green";
  if (n >= 50) return "yellow";
  return "red";
}

function showError(msg) {
  document.getElementById("kpi-grid").innerHTML = `<div class="placeholder error">${msg}</div>`;
  document.getElementById("detail-table-wrap").innerHTML = "";
}

init();
