// EOS L10 Scorecard - frontend
// Reads existing goals + YTD actuals from the 2026 Scorecard tab via /api/scorecard.
// Trends, period roll-ups, and live source pulls come in later passes.

const ALL_AGENCIES = ["FANNIT", "TMSA", "HMC", "IPA"];

let state = {
  agencies: [],          // mapped agencies (have block offsets)
  unmapped: [],          // agencies known but block offsets not yet wired
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
    state.agencies = [];
  }
  renderSidebar();
  if (state.current) {
    await loadAgency(state.current);
  } else {
    showError("No agencies mapped yet.");
  }
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
    li.title = "Block offsets not yet wired in src/sheets/scorecard.py";
    ul.appendChild(li);
  }
}

async function loadAgency(agency) {
  state.current = agency;
  document.getElementById("page-title").textContent = `${agency} — EOS Scorecard`;
  renderSidebar();

  const grid = document.getElementById("kpi-grid");
  grid.innerHTML = '<div class="placeholder">Reading sheet…</div>';

  try {
    const res = await fetch(`/api/scorecard?agency=${encodeURIComponent(agency)}`);
    const data = await res.json();
    if (!res.ok) {
      showError(`API error: ${data.error || res.status}`);
      return;
    }
    renderGrid(data.kpis || []);
  } catch (err) {
    showError(`Network error: ${err.message}`);
  }
}

function renderGrid(kpis) {
  const grid = document.getElementById("kpi-grid");
  grid.innerHTML = "";
  if (!kpis.length) {
    grid.innerHTML = '<div class="placeholder">No KPI rows returned.</div>';
    return;
  }
  for (const k of kpis) {
    grid.appendChild(buildCard(k));
  }
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
  value.textContent = formatValue(k.ytd_actual, k.fmt);

  const meta = document.createElement("div");
  meta.className = "kpi-meta";
  const goalEl = document.createElement("span");
  goalEl.textContent = `Goal: ${formatValue(k.annual_goal, k.fmt)}`;
  const hitEl = document.createElement("span");
  hitEl.className = "kpi-hit " + hitColor(k);
  hitEl.textContent = formatHit(k.hit_pct);
  meta.appendChild(goalEl);
  meta.appendChild(hitEl);

  const dot = document.createElement("div");
  dot.className = "kpi-status-dot " + hitColor(k);

  card.appendChild(dot);
  card.appendChild(title);
  card.appendChild(source);
  card.appendChild(value);
  card.appendChild(meta);
  return card;
}

function formatValue(v, fmt) {
  if (v === null || v === undefined) return "—";
  if (fmt === "currency") {
    if (Math.abs(v) >= 1_000_000) return "$" + (v / 1_000_000).toFixed(1) + "M";
    if (Math.abs(v) >= 1_000) return "$" + (v / 1_000).toFixed(1) + "K";
    return "$" + v.toFixed(2);
  }
  if (fmt === "percent") {
    // sheet stores percents as decimals (0.046) or as numbers (4.65)
    const n = Math.abs(v) <= 1 ? v * 100 : v;
    return n.toFixed(2) + "%";
  }
  // numbers
  if (Math.abs(v) >= 10_000) return Math.round(v).toLocaleString();
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(1);
}

function formatHit(p) {
  if (p === null || p === undefined) return "—";
  const n = Math.abs(p) <= 1 ? p * 100 : p;
  return n.toFixed(1) + "%";
}

function hitColor(k) {
  const p = k.hit_pct;
  if (p === null || p === undefined) return "gray";
  // raw values: hit_pct is the fraction (0.65) or percent number (65)
  let n = Math.abs(p) <= 1 ? p * 100 : p;
  // For inverted-goal metrics, the "hit pct" displayed in the sheet is just
  // the actual rate, not goal-attainment. Treat low values as good there.
  const inverted = k.label.includes("Churn") || k.label.includes("AR Past 30");
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
  const grid = document.getElementById("kpi-grid");
  grid.innerHTML = `<div class="placeholder error">${msg}</div>`;
}

init();
