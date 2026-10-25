// Rubik's Cube Race - frontend. Talks only to the local backend; the API key stays server-side.
const $ = (id) => document.getElementById(id);
const FACES = "URFDLB";
// Position of each face (3x3 block) in a 12x9 net: [row, col] of its top-left sticker.
const NET_POS = { U: [0, 3], L: [3, 0], F: [3, 3], R: [3, 6], B: [3, 9], D: [6, 3] };
const MODEL_COLOR = { jev: "var(--m-jev)", luna: "var(--m-luna)", clef: "var(--m-clef)", opus: "var(--m-opus)" };
const STATUS_TEXT = { playing: "PLAYING", solved: "SOLVED", limit: "MOVE LIMIT", budget: "BUDGET STOP", error: "ERROR", stopped: "STOPPED" };

let cfg = null;
let pollTimer = null;
let replayTimer = null;
let lastData = null;

const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fmt = (x, d = 2, suf = "") => (x === null || x === undefined ? "-" : `${Number(x).toFixed(d)}${suf}`);

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error((await r.text()) || r.statusText);
  return r.json();
}

function netHTML(state, large) {
  const cells = new Array(108).fill("");
  FACES.split("").forEach((f, fi) => {
    const [r0, c0] = NET_POS[f];
    for (let i = 0; i < 9; i++) {
      const r = r0 + Math.floor(i / 3), c = c0 + (i % 3);
      cells[r * 12 + c] = state[fi * 9 + i];
    }
  });
  return `<div class="net${large ? " lg" : ""}">${cells.map((c) => (c ? `<i class="${c}"></i>` : "<span></span>")).join("")}</div>`;
}

function cardHTML(t, model, live) {
  const last = t.steps[t.steps.length - 1];
  const bad = last && !last.valid;
  const shown = !last ? "-" : bad ? "INVALID" : last.move;
  const chips = t.steps.map((s) => (s.valid ? `<span class="chip">${esc(s.move)}</span>` : `<span class="chip bad" title="${esc(s.error)}">&#x2716;</span>`)).join("");
  const conf = last && last.confidence != null ? ` &middot; conf ${fmt(last.confidence, 2)}` : "";
  return `<div class="card" style="--mc:${MODEL_COLOR[model.key] || "var(--accent)"}">
    <div class="card-head">
      <div><div class="name">${esc(model.name)}</div><div class="cat">${esc(model.category)}${live ? "" : " &middot; simulated"}</div></div>
      <span class="pill ${t.status}">${STATUS_TEXT[t.status] || t.status}</span>
    </div>
    <div class="card-body">
      ${netHTML(t.state)}
      <div class="now">
        <div class="mv${bad ? " bad" : ""}">${esc(shown)}</div>
        <div class="meta">move ${t.moves.length} &middot; turn ${t.turns}/${lastData?.policy?.move_limit ?? ""}</div>
        <div class="meta">${last ? fmt(last.latency_s, 3, " s") : "-"}${conf}</div>
      </div>
    </div>
    <div class="history">${chips || '<span class="muted">no moves yet</span>'}</div>
    <div class="result">time ${fmt(t.total_time_s, 2, " s")} &middot; invalid ${t.invalid}</div>
  </div>`;
}

function render(data, mode) {
  lastData = data;
  const badge = $("modeBadge");
  badge.className = "badge " + mode;
  badge.textContent = mode === "replay" ? "REPLAY" : data.live ? "LIVE" : "MOCK";
  const cap = data.policy.max_calls ? ` / ${data.policy.max_calls}` : "";
  $("callsMeter").textContent = `${data.live ? "API calls" : "Simulated calls"}: ${data.calls_used}${cap}`;
  $("statusBar").innerHTML = `Run <code>${esc(data.id)}</code> &middot; ${esc(data.profile_label)} &middot; status <b>${esc(data.status)}</b> &middot; round ${data.round}` +
    (data.error ? ` &middot; <span style="color:var(--bad)">${esc(data.error)}</span>` : "");

  const models = Object.fromEntries(data.models.map((m) => [m.key, m]));
  $("puzzles").innerHTML = data.puzzles.map((p) => {
    const trials = data.trials.filter((t) => t.puzzle_id === p.id);
    return `<div class="puzzle">
      <div class="puzzle-head">
        <h3>${p.id}</h3><span class="tag">${esc(p.set)}</span>
        <span>scramble <code>${esc(p.scramble.join(" "))}</code></span>
        <span class="muted">shortest solution: <b>${p.optimal ?? "unknown (&gt;8)"}</b> moves</span>
      </div>
      <div class="cards">${trials.map((t) => cardHTML(t, models[t.model_key], data.live)).join("")}</div>
    </div>`;
  }).join("");
  $("log").textContent = (data.log || []).join("\n");
  $("dashboard").innerHTML = data.summary ? dashboardHTML(data) : '<p class="muted">Results appear when the replay finishes.</p>';
}

function barChart(title, models, field, suffix, digits, higherBetter) {
  const vals = models.map((m) => m[field]).filter((v) => v !== null && v !== undefined);
  const max = Math.max(...vals, 1e-9);
  const rows = models.map((m) => {
    const v = m[field];
    const w = v === null || v === undefined ? 0 : Math.max(2, (100 * v) / max);
    return `<div class="bar-row"><span>${esc(m.name.replace("OpenAI ", "").replace("Cloudflare ", ""))}</span>
      <div class="bar-track"><div class="bar" style="width:${w}%;background:${MODEL_COLOR[m.key]}"></div></div>
      <span class="bar-val">${fmt(v, digits, suffix)}</span></div>`;
  }).join("");
  return `<div class="chart"><h4>${title} <span class="muted">(${higherBetter ? "higher" : "lower"} is better)</span></h4>${rows}</div>`;
}

function dashboardHTML(data) {
  const ms = data.summary.models;
  const rows = ms.map((m) => `<tr>
      <td><span class="swatch" style="background:${MODEL_COLOR[m.key]}"></span>${esc(m.name)}<div class="muted">${esc(m.category)}</div></td>
      <td>${fmt(m.avg_latency_s, 3, " s")}<div class="muted">median ${fmt(m.median_latency_s, 3, " s")}</div></td>
      <td>${fmt(m.avg_total_time_s, 2, " s")}<div class="muted">sum ${fmt(m.sum_total_time_s, 1, " s")}</div></td>
      <td>${m.total_moves}<div class="muted">avg ${fmt(m.avg_moves, 1)} / puzzle</div></td>
      <td>${fmt(m.success_rate, 1, "%")}<div class="muted">${m.solved}/${m.trials} solved</div></td>
      <td>${fmt(m.avg_gap, 2)}<div class="muted">${m.zero_gap_solves} optimal solves</div></td>
      <td>${m.avg_progress == null ? "-" : (m.avg_progress > 0 ? "+" : "") + Number(m.avg_progress).toFixed(2)}<div class="muted">moves closer to solved</div></td>
      <td>${m.invalid}</td><td>${m.calls}</td><td>${m.cost_usd ? "$" + m.cost_usd.toFixed(4) : "-"}</td>
    </tr>`).join("");
  const a = data.summary.answers;
  return `<table>
      <thead><tr><th>Model</th><th>Avg latency / move</th><th>Total solve time / puzzle</th><th>Total moves</th>
      <th>Success rate</th><th>Optimality gap</th><th>Progress</th><th>Invalid</th><th>Calls</th><th>Cost</th></tr></thead>
      <tbody>${rows}</tbody></table>
    <p class="muted">Optimality gap = model moves &minus; exact shortest moves (bidirectional BFS, half-turn metric), solved puzzles only.
      Progress = exact distance to solved at start minus at end (positive = closer).
      Move limit ${data.policy.move_limit}; reaching it counts as unsolved. ${esc(data.policy.invalid_policy)}.</p>
    <div class="charts">
      ${barChart("Avg latency per move", ms, "avg_latency_s", " s", 3, false)}
      ${barChart("Avg total solve time", ms, "avg_total_time_s", " s", 1, false)}
      ${barChart("Success rate", ms, "success_rate", "%", 0, true)}
      ${barChart("Avg optimality gap", ms, "avg_gap", "", 2, false)}
      ${barChart("Total moves", ms, "total_moves", "", 0, false)}
    </div>
    <div class="answers"><h3 style="margin-top:18px">What the experiment shows</h3><ol>
      <li><b>Fastest decisions:</b> ${esc(a.q1)}</li>
      <li><b>Highest solve rate:</b> ${esc(a.q2)}</li>
      <li><b>Shortest solutions:</b> ${esc(a.q3)}</li>
      <li><b>Fastest = best quality?</b> ${esc(a.q4)}</li>
      <li><b>Which to use:</b> ${esc(a.q5)}</li>
    </ol></div>`;
}

function showSlide() {
  if (!lastData || !lastData.summary) { $("hint").textContent = "Run, replay or load a benchmark first."; return; }
  const d = lastData;
  $("slideStudent").innerHTML = `<span class="label">Student</span> ${esc(d.student.name)} <span class="sep">|</span> <span class="label">Roll No</span> ${esc(d.student.roll)}`;
  $("slideMeta").textContent = `${d.live ? "Live OpenRouter run" : "Mock run (simulated models)"} - ${d.puzzles.length} puzzles x ${d.models.length} models - ${d.calls_used} calls - run ${d.id}`;
  $("slideBody").innerHTML = dashboardHTML(d);
  $("slide").hidden = false;
}

// ---------------------------------------------------------------- live run
async function startRun() {
  stopReplay();
  const profile = $("profile").value;
  const p = cfg.profiles[profile];
  if (p.live && !cfg.api_key_set) { $("hint").textContent = "OPENROUTER_API_KEY is not set in .env - restart the server after adding it."; return; }
  if (p.live && !confirm(`Start a LIVE run? It will use at most ${p.max_calls} paid OpenRouter calls.`)) return;
  try {
    await api("/api/run", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile }) });
    $("hint").textContent = "";
    poll();
  } catch (e) { $("hint").textContent = e.message; }
}

async function poll() {
  clearTimeout(pollTimer);
  try {
    const d = await api("/api/run/current");
    if (d.status !== "idle") render(d, d.live ? "live" : "mock");
    if (d.status === "running") { pollTimer = setTimeout(poll, 400); return; }
    $("runBtn").disabled = false;
    refreshSaved();
  } catch (e) { pollTimer = setTimeout(poll, 1500); }
}

// ---------------------------------------------------------------- replay (0 calls)
function stopReplay() { clearInterval(replayTimer); replayTimer = null; }

function viewAt(run, tau, done) {
  const v = JSON.parse(JSON.stringify(run));
  const puzzles = Object.fromEntries(run.puzzles.map((p) => [p.id, p]));
  let calls = 0, round = 0;
  v.trials.forEach((t) => {
    const steps = t.steps.filter((s) => s.t_end <= tau);
    const finished = steps.length === t.steps.length;
    calls += steps.reduce((n, s) => n + (s.attempts || 1), 0);
    round = Math.max(round, steps.length);
    t.steps = steps;
    t.moves = steps.filter((s) => s.valid).map((s) => s.move);
    t.turns = steps.length;
    t.invalid = steps.filter((s) => !s.valid).length;
    t.state = steps.length ? steps[steps.length - 1].state_after : puzzles[t.puzzle_id].state;
    t.total_time_s = steps.reduce((n, s) => n + s.latency_s + s.engine_s, 0);
    t.current_move = steps.length ? steps[steps.length - 1].move : null;
    if (!finished) t.status = "playing";
  });
  v.calls_used = calls; v.round = round;
  v.status = done ? run.status : "replaying";
  if (!done) v.summary = null;
  return v;
}

async function replay() {
  const name = $("savedRuns").value;
  if (!name) return;
  stopReplay(); clearTimeout(pollTimer);
  const run = await api(`/api/runs/${name}`);
  const end = Math.max(0, ...run.trials.flatMap((t) => t.steps.map((s) => s.t_end)));
  const speed = Number($("speed").value);
  const t0 = performance.now();
  replayTimer = setInterval(() => {
    const tau = ((performance.now() - t0) / 1000) * speed;
    const done = tau >= end;
    render(viewAt(run, tau, done), "replay");
    if (done) stopReplay();
  }, 150);
}

async function loadSaved() {
  const name = $("savedRuns").value;
  if (!name) return;
  stopReplay(); clearTimeout(pollTimer);
  render(await api(`/api/runs/${name}`), "replay");
}

async function refreshSaved() {
  const runs = await api("/api/runs");
  $("savedRuns").innerHTML = runs.length ? runs.map((r) => `<option>${esc(r)}</option>`).join("") : "<option value=''>(none yet)</option>";
}

async function preflight() {
  $("hint").textContent = "Checking the public OpenRouter model catalog (free)...";
  try {
    const r = await api("/api/preflight");
    const parts = r.models.map((m) => `${m.name} [${m.id}]: ${m.listed ? "listed" : "NOT FOUND - check the id on openrouter.ai"}`);
    $("hint").textContent = `API key ${r.api_key_set ? "set" : "MISSING"}. ` + parts.join(" | ");
  } catch (e) { $("hint").textContent = e.message; }
}

async function init() {
  cfg = await api("/api/config");
  $("studentName").textContent = cfg.student.name;
  $("studentRoll").textContent = cfg.student.roll;
  $("profile").innerHTML = Object.entries(cfg.profiles).map(([k, p]) => `<option value="${k}">${esc(p.label)}</option>`).join("");
  $("runBtn").onclick = startRun;
  $("stopBtn").onclick = () => api("/api/run/stop", { method: "POST" });
  $("preflightBtn").onclick = preflight;
  $("replayBtn").onclick = replay;
  $("loadBtn").onclick = loadSaved;
  $("slideBtn").onclick = showSlide;
  $("closeSlide").onclick = () => ($("slide").hidden = true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") $("slide").hidden = true; });
  await refreshSaved();
  poll();
}
init();
