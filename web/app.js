"use strict";

const state = { offset: 0, limit: 50, lastCount: 0 };

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function truncate(text, max = 80) {
  const s = String(text ?? "");
  return s.length > max ? s.slice(0, max) + "…" : s;
}

function fmtTime(ms) {
  if (!ms) return "";
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

function fmtDur(ms) {
  if (!ms) return "";
  return ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;
}

function paramsFromForm() {
  const p = new URLSearchParams();
  for (const key of ["device_id", "user_id", "session_id", "q", "turn_type", "tts_status", "stt_status"]) {
    const v = $("filters_" + key) || $("filter_" + key) || $("" + key) || document.getElementById(key);
    if (v && v.value.trim()) p.set(key, v.value.trim());
  }
  const start = $("start_dt").value;
  const end = $("end_dt").value;
  if (start) p.set("start_ms", new Date(start).getTime());
  if (end) p.set("end_ms", new Date(end).getTime());
  p.set("limit", state.limit);
  p.set("offset", state.offset);
  return p;
}

async function search() {
  const tbody = $("rows");
  tbody.innerHTML = '<tr><td colspan="11" class="empty">查询中…</td></tr>';
  try {
    const res = await fetch("/api/turns?" + paramsFromForm().toString());
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderRows(data.rows);
    state.lastCount = data.rows.length;
    updatePager();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="11" class="empty">查询失败：${esc(err.message)}</td></tr>`;
    $("total").textContent = "";
  }
}

function renderRows(rows) {
  const tbody = $("rows");
  tbody.innerHTML = "";
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="11" class="empty">没有匹配的日志</td></tr>';
    $("total").textContent = "0 条";
    return;
  }
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.className = "turn-row";
    tr.innerHTML = `
      <td class="nowrap">${esc(fmtTime(r.utc_start_ms))}</td>
      <td class="mono">${esc(r.device_id)}</td>
      <td class="mono">${esc(r.user_id)}</td>
      <td class="mono">${esc(truncate(r.session_id, 16))}</td>
      <td>${esc(r.turn_type)}</td>
      <td class="text">${esc(truncate(r.stt_text))}</td>
      <td class="text">${esc(truncate(r.tts_text))}</td>
      <td class="nowrap">${esc(r.stt_status)}</td>
      <td class="nowrap">${esc(r.tts_status)}</td>
      <td class="nowrap">${esc(fmtDur(r.e2e_ms))}</td>
      <td class="nowrap audio-btns">
        <button data-play="${esc(r.turn_id)}" data-kind="input" title="播放用户输入">🎤</button>
        <button data-play="${esc(r.turn_id)}" data-kind="tts" title="播放助理回复">🔊</button>
        <button data-play="${esc(r.turn_id)}" data-kind="listen" title="播放回复期间录制">🎧</button>
      </td>`;
    tr.addEventListener("click", (ev) => {
      if (ev.target.closest("[data-play]")) return;
      toggleDetail(r.turn_id, tr);
    });
    tbody.appendChild(tr);
  }
  $("total").textContent = `本页 ${rows.length} 条`;
}

async function toggleDetail(turnId, rowEl) {
  const existing = rowEl.nextElementSibling;
  if (existing && existing.classList.contains("detail-row")) {
    existing.remove();
    rowEl.classList.remove("active");
    return;
  }
  rowEl.classList.add("active");
  const tr = document.createElement("tr");
  tr.className = "detail-row";
  tr.innerHTML = `<td colspan="11" class="detail-cell">加载详情…</td>`;
  rowEl.after(tr);
  try {
    const res = await fetch(`/api/turns/${encodeURIComponent(turnId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    tr.innerHTML = `<td colspan="11" class="detail-cell">${detailHtml(await res.json())}</td>`;
  } catch (err) {
    tr.innerHTML = `<td colspan="11" class="detail-cell">加载详情失败：${esc(err.message)}</td>`;
  }
}

function segmentsHtml(segments) {
  if (!segments || !segments.length) return "—";
  return segments
    .map((s) => `[${(s.start_ms / 1000).toFixed(2)}s → ${(s.end_ms / 1000).toFixed(2)}s]`)
    .join(" ");
}

function detailHtml(r) {
  const kv = [
    ["turn_id", r.turn_id],
    ["session_id", r.session_id],
    ["turn_idx", r.turn_idx],
    ["device_id", r.device_id],
    ["user_id", r.user_id],
    ["persona_id", r.persona_id],
    ["turn_type", r.turn_type],
    ["turn_phase", r.turn_phase],
    ["utc_start_ms", r.utc_start_ms],
    ["utc_end_ms", r.utc_end_ms],
    ["duration_ms", fmtDur(r.duration_ms)],
    ["stt_model", r.stt_model],
    ["stt_status", r.stt_status],
    ["tts_model", r.tts_model],
    ["tts_status", r.tts_status],
    ["tts_truncated_reason", r.tts_truncated_reason],
    ["llm_model", r.llm_model],
    ["e2e_ms", r.e2e_ms],
    ["stt_ms", r.stt_ms],
    ["llm_ttft_ms", r.llm_ttft_ms],
    ["tts_ttfb_ms", r.tts_ttfb_ms],
    ["device_playback_ms", r.device_playback_ms],
    ["input_pcm_ms", r.input_pcm_ms],
    ["tts_pcm_ms", r.tts_pcm_ms],
    ["voice_segments", segmentsHtml(r.voice_segments)],
    ["stt_interims", (r.stt_interims || []).length + " 条"],
    ["abandoned_stts", (r.abandoned_stts || []).length + " 条"],
    ["s3_input_wav", r.s3_input_wav],
    ["s3_tts_wav", r.s3_tts_wav],
    ["s3_listen_wav", r.s3_listen_wav],
  ];
  const meta = kv.map(([k, v]) => `<div class="kv"><span>${esc(k)}</span><code>${esc(v)}</code></div>`).join("");
  const texts = `
    <div class="block"><h4>用户说（STT）</h4><p>${esc(r.stt_text) || "—"}</p></div>
    <div class="block"><h4>助理说（TTS）</h4><p>${esc(r.tts_text) || "—"}</p></div>
    <div class="block"><h4>STT interims</h4><ol>${(r.stt_interims || []).map((t) => `<li>${esc(t)}</li>`).join("") || "<p>—</p>"}</ol></div>`;
  const audio = `
    <div class="block audio-row">
      <h4>音频</h4>
      <audio controls data-audio="${esc(r.turn_id)}" data-kind="input"></audio>
      <span class="audio-label">用户输入 input.wav</span>
      <audio controls data-audio="${esc(r.turn_id)}" data-kind="tts"></audio>
      <span class="audio-label">助理回复 tts.wav</span>
      <audio controls data-audio="${esc(r.turn_id)}" data-kind="listen"></audio>
      <span class="audio-label">回复期间录制 listen.wav</span>
    </div>`;
  return `<div class="detail-grid">${meta}</div>${texts}${audio}`;
}

async function loadAudio(turnId, kind) {
  const el = document.querySelector(`audio[data-audio="${CSS.escape(turnId)}"][data-kind="${kind}"]`);
  if (!el) return;
  const res = await fetch(`/api/turns/${encodeURIComponent(turnId)}/audio/${kind}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    el.dataset.error = err.detail || `HTTP ${res.status}`;
    alert(err.detail || `加载音频失败（HTTP ${res.status}）`);
    return;
  }
  const data = await res.json();
  el.src = data.url;
  el.play().catch(() => {});
}

function updatePager() {
  $("btn_prev").disabled = state.offset <= 0;
  $("btn_next").disabled = state.lastCount < state.limit;
  const page = Math.floor(state.offset / state.limit) + 1;
  $("page_info").textContent = `第 ${page} 页 · 每页 ${state.limit}`;
}

$("btn_search").addEventListener("click", () => {
  state.offset = 0;
  search();
});

$("btn_reset").addEventListener("click", () => {
  for (const el of document.querySelectorAll(".filters input, .filters select")) el.value = "";
  state.offset = 0;
  search();
});

$("btn_prev").addEventListener("click", () => {
  state.offset = Math.max(0, state.offset - state.limit);
  search();
});

$("btn_next").addEventListener("click", () => {
  state.offset += state.limit;
  search();
});

document.addEventListener("input", (ev) => {
  if (ev.target.matches('input[type="datetime-local"]')) {
    if (ev.target.value) state.offset = 0;
  }
});

$("rows").addEventListener("click", async (ev) => {
  const btn = ev.target.closest("[data-play]");
  if (btn) {
    ev.stopPropagation();
    // The <audio> elements live in the detail row — expand it first so the
    // play button works even when the row is collapsed.
    const rowEl = btn.closest("tr");
    if (rowEl && !rowEl.nextElementSibling?.classList.contains("detail-row")) {
      await toggleDetail(btn.dataset.play, rowEl);
    }
    await loadAudio(btn.dataset.play, btn.dataset.kind);
  }
});

(async function init() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const el = $("health");
    el.textContent = `ClickHouse: ${data.clickhouse}`;
    el.className = "health " + (data.clickhouse === "ok" ? "ok" : "bad");
  } catch {
    $("health").textContent = "无法连接后端";
    $("health").className = "health bad";
  }
  search();
})();
