"use strict";

const dataset = JSON.parse(document.getElementById("review-data").textContent);
const rows = dataset.rows;
const byId = new Map(rows.map(row => [row.review_id, row]));
const mode = dataset.mode || "pass";
const isDrive = mode === "drive";
const isTrainingReview = !isDrive && rows.some(row => row.review_reason);
const observationField = isDrive ? "review_observation" : "human_visibility";
const judgmentField = isDrive ? "review_mapping" : "human_judgment";
const commentField = isDrive ? "review_comment" : "human_comment";
const storageKey = `u18-${mode}-review-v1:${dataset.review_sha256}`;
const video = document.getElementById("clip-video");
const slider = document.getElementById("frame-slider");
const observationValues = isDrive
  ? ["carry_after_receive", "control_only", "one_touch_release", "partial", "offscreen", "unclear"]
  : ["VISIBLE", "PARTIAL", "OFFSCREEN", "UNCLEAR"];
const observationLabels = isDrive
  ? ["接球后带球", "仅停球/控球", "直接传出/解围", "部分可见", "画面外", "看不清"]
  : ["清楚可见", "部分可见", "画面外", "看不清"];
const judgmentValues = isDrive ? ["accept", "reject", "unclear"] : ["确有 Pass", "无 Pass", "时间偏移", "类别不符", "无法判断"];
const judgmentLabels = isDrive ? ["可作为 Drive", "不适合作为 Drive", "无法判断"] : judgmentValues;
let activeId = (isDrive ? rows[0] : rows.find(row => row.video_id.startsWith("urawa_")) || rows[0]).review_id;
let saved = {};
let storageWorks = true;
try { saved = JSON.parse(localStorage.getItem(storageKey) || "{}"); }
catch { storageWorks = false; }
const answers = Object.fromEntries(rows.map(row => [row.review_id, {
  [observationField]: saved[row.review_id]?.[observationField] ?? row[observationField] ?? "",
  [judgmentField]: saved[row.review_id]?.[judgmentField] ?? (row[judgmentField] === "unreviewed" ? "" : row[judgmentField] ?? ""),
  [commentField]: saved[row.review_id]?.[commentField] ?? row[commentField] ?? ""
}]));

if (isDrive) {
  document.title = "U18 BAS · Drive 语义复核";
  document.querySelector(".brand strong").textContent = "U18 Drive 语义复核";
  document.querySelector(".brand small").textContent = "50 条 Bepro 接球事件 · 遮挡视频";
  document.querySelector(".sidebar-head p").textContent = "判断接球事件能否作为 Drive 的参考标注。";
  document.querySelectorAll(".field h2")[0].textContent = "1 · 接球后看到了什么？";
  document.querySelectorAll(".field h2")[1].textContent = "2 · 可否用作 Drive GT？";
  document.querySelector(".note-label").textContent = "3 · 说明原因（可选）";
  document.getElementById("human-comment").placeholder = "如：接球后立即传出；球被遮住；约 2 秒后开始带球…";
  document.querySelector(".help").textContent = "这 50 条来自 Bepro 的「パス(受け手)」，并不自动等于 BAS 的 Drive。先描述画面所见，再独立判断是否适合映射；看不清就选「无法判断」。选项保存在当前浏览器，请按「保存到项目」留下正式审查文件，也可下载 CSV 备份。快捷键：空格播放，←/→ 逐帧，Shift+←/→ 跳 1 秒，N/P 切换样本。";
  document.getElementById("status-filter").parentElement.hidden = true;
} else if (isTrainingReview) {
  document.title = "U18 BAS · Pass 训练标签复核";
  document.querySelector(".brand strong").textContent = "U18 Pass 训练标签复核";
  document.querySelector(".brand small").textContent = `${rows.length} 条新样本 · 遮挡视频`;
  document.querySelector(".sidebar-head p").textContent = "两场比赛分别用于相反方向的训练；请只判断画面，不参考程序状态。";
  document.querySelector(".note-label").textContent = "3 · 实际传球时刻与说明";
  document.getElementById("human-comment").placeholder = "如：实际传球约在 00:20:40.120；画面外；遮罩挡住触球…";
  document.querySelector(".help").innerHTML = "<strong>本轮任务：</strong>确认画面里是否有 Pass、动作是否可见；若实际传球时刻与页面事件时间不同，请在备注写出精确到帧的时间码。FP/FN 只是自动时间匹配状态，不是视觉结论。每条结果仅能用于该场比赛担任训练集的那一轮，冻结测试 GT 不改动。<br><span>快捷键：空格播放，←/→ 逐帧，Shift+←/→ 跳 1 秒，N/P 切换。请按「保存到项目」，也可下载 CSV 备份。</span>";
  document.getElementById("drive-link").hidden = true;
  document.getElementById("pass-link").textContent = "Pass 训练标签";
}
document.getElementById(isDrive ? "drive-link" : "pass-link").setAttribute("aria-current", "page");

function tc(value) {
  const ms = Math.max(0, Math.round(value * 1000));
  const h = Math.floor(ms / 3600000);
  const m = Math.floor(ms / 60000) % 60;
  const s = Math.floor(ms / 1000) % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}.${String(ms % 1000).padStart(3, "0")}`;
}
function isDone(row) {
  const answer = answers[row.review_id];
  return Boolean(answer[observationField] && answer[judgmentField]);
}
function persist() {
  try {
    localStorage.setItem(storageKey, JSON.stringify(answers));
    document.getElementById("save-status").textContent = "已自动保存在此浏览器";
  } catch {
    storageWorks = false;
    document.getElementById("save-status").textContent = "浏览器未允许自动保存，请立即导出 CSV";
  }
  updateProgress();
  renderList();
}
function updateProgress() {
  const done = rows.filter(isDone).length;
  document.getElementById("progress").textContent = `已审 ${done} / ${rows.length}`;
  document.getElementById("status-pill").textContent = isDone(byId.get(activeId)) ? "人工判断已填写" : "待填写人工判断";
}
function addChoiceButtons(targetId, values, labels, field) {
  const target = document.getElementById(targetId);
  target.replaceChildren();
  values.forEach((value, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "choice";
    button.textContent = labels[index];
    button.dataset.value = value;
    button.setAttribute("aria-pressed", String(answers[activeId][field] === value));
    if (answers[activeId][field] === value) button.classList.add("selected");
    button.addEventListener("click", () => {
      answers[activeId][field] = answers[activeId][field] === value ? "" : value;
      addChoiceButtons(targetId, values, labels, field);
      persist();
    });
    target.appendChild(button);
  });
}
function filteredRows() {
  const videoFilter = document.getElementById("video-filter").value;
  const statusFilter = document.getElementById("status-filter").value;
  const reviewFilter = document.getElementById("review-filter").value;
  return rows.filter(row =>
    (!videoFilter || row.video_id === videoFilter) &&
    (isDrive || !statusFilter || row.algorithmic_status === statusFilter) &&
    (!reviewFilter || (reviewFilter === "done" ? isDone(row) : !isDone(row)))
  );
}
function renderList() {
  const target = document.getElementById("case-list");
  target.replaceChildren();
  filteredRows().forEach(row => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `case${row.review_id === activeId ? " active" : ""}`;
    button.setAttribute("role", "listitem");
    button.setAttribute("aria-current", row.review_id === activeId ? "true" : "false");
    const top = document.createElement("div");
    top.className = "case-top";
    const id = document.createElement("span"); id.className = "case-id"; id.textContent = row.review_id;
    const badge = document.createElement("span"); badge.className = `badge ${row.algorithmic_status}`; badge.textContent = row.algorithmic_status;
    const dot = document.createElement("span"); dot.className = `dot${isDone(row) ? " done" : ""}`; dot.title = isDone(row) ? "人工判断已填写" : "待填写";
    top.append(id, badge, dot);
    const time = document.createElement("div"); time.className = "case-time"; time.textContent = row.source_timecode;
    const meta = document.createElement("div"); meta.className = "case-meta"; meta.textContent = row.video_id.replaceAll("_", " · ");
    button.append(top, time, meta);
    button.addEventListener("click", () => selectCase(row.review_id));
    target.appendChild(button);
  });
  if (!target.children.length) {
    const empty = document.createElement("p"); empty.className = "empty"; empty.textContent = "当前筛选没有样本"; target.appendChild(empty);
  }
}
function selectCase(id) {
  if (!byId.has(id)) return;
  activeId = id;
  const row = byId.get(id);
  const clip = row.clip;
  video.pause();
  video.src = clip.path;
  document.getElementById("clip-link").href = clip.path;
  document.getElementById("video-error").hidden = true;
  video.load();
  slider.max = String(clip.frame_count - 1);
  slider.value = String(clip.center_relative_frame);
  document.getElementById("start-label").textContent = tc(clip.start_sec);
  document.getElementById("end-label").textContent = tc(clip.start_sec + clip.frame_count / clip.fps);
  document.getElementById("case-kicker").textContent = row.review_id;
  document.getElementById("case-title").textContent = `${row.source_timecode} · ${isDrive ? "接球→Drive?" : "Pass"}`;
  document.getElementById("case-subtitle").textContent = isDrive
    ? `${row.video_id.replaceAll("_", " · ")} · ${row.team} · ${row.player || "球员未知"}`
    : `${row.video_id.replaceAll("_", " · ")} · ${row.review_reason || (row.algorithmic_status === "FN" ? "Bepro 事件未匹配高分预测" : row.algorithmic_status === "FP" ? "模型预测未匹配 Bepro 事件" : "匹配成功的参照")}`;
  addChoiceButtons("visibility-options", observationValues, observationLabels, observationField);
  addChoiceButtons("judgment-options", judgmentValues, judgmentLabels, judgmentField);
  document.getElementById("human-comment").value = answers[id][commentField];
  updateClock(clip.center_offset_sec);
  updateProgress();
  renderList();
}
function updateClock(relativeSeconds) {
  const row = byId.get(activeId);
  const sourceTime = row.clip.start_sec + relativeSeconds;
  const delta = sourceTime - Number(row.source_time_sec);
  document.getElementById("clock").textContent = `视频 ${tc(sourceTime)} · 事件 ${delta >= 0 ? "+" : ""}${delta.toFixed(2)} 秒`;
  slider.value = String(Math.min(row.clip.frame_count - 1, Math.max(0, Math.round(relativeSeconds * row.clip.fps))));
}
function seekFrame(frame) {
  const clip = byId.get(activeId).clip;
  const clamped = Math.max(0, Math.min(clip.frame_count - 1, frame));
  video.pause();
  video.currentTime = Math.min((clamped + 0.02) / clip.fps, Math.max(0, clip.frame_count / clip.fps - 0.001));
  updateClock(clamped / clip.fps);
}
function moveCase(direction) {
  const filtered = filteredRows();
  const index = filtered.findIndex(row => row.review_id === activeId);
  const next = filtered[index + direction];
  if (next) selectCase(next.review_id);
}
function csvQuote(value) { return `"${String(value ?? "").replaceAll('"', '""')}"`; }
function buildCsv() {
  const lines = [dataset.fields.join(",")];
  for (const row of rows) {
    const merged = {...row, ...answers[row.review_id]};
    if (isDrive && !merged.review_mapping) merged.review_mapping = "unreviewed";
    lines.push(dataset.fields.map(field => csvQuote(merged[field])).join(","));
  }
  return "\ufeff" + lines.join("\r\n") + "\r\n";
}
function exportCsv() {
  const url = URL.createObjectURL(new Blob([buildCsv()], {type: "text/csv;charset=utf-8"}));
  const link = document.createElement("a");
  link.href = url;
  link.download = isDrive ? "drive_mapping_audit_reviewed.csv" : isTrainingReview ? "u18_pass_training_reviewed.csv" : "pass_review_cases_reviewed.csv";
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  document.getElementById("save-status").textContent = "审查 CSV 已导出到下载文件夹";
}
async function saveToProject() {
  const button = document.getElementById("save-project");
  button.disabled = true;
  document.getElementById("save-status").textContent = "正在保存到本机项目…";
  try {
    const response = await fetch("/api/save-review", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({mode, review_sha256: dataset.review_sha256, csv: buildCsv()})
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    document.getElementById("save-status").textContent = `已保存到项目：${result.file}`;
  } catch (error) {
    document.getElementById("save-status").textContent = `保存失败：${error.message}。请使用「下载 CSV」备份。`;
  } finally {
    button.disabled = false;
  }
}
function parseCsv(text) {
  const table = []; let row = []; let cell = ""; let quoted = false;
  text = text.replace(/^\ufeff/, "");
  for (let index = 0; index < text.length; index++) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') { cell += '"'; index++; }
      else if (char === '"') quoted = false;
      else cell += char;
    } else if (char === '"') quoted = true;
    else if (char === ",") { row.push(cell); cell = ""; }
    else if (char === "\n") { row.push(cell.replace(/\r$/, "")); table.push(row); row = []; cell = ""; }
    else cell += char;
  }
  if (quoted) throw new Error("CSV 引号未闭合");
  if (row.length || cell) { row.push(cell.replace(/\r$/, "")); table.push(row); }
  return table;
}
async function importCsv(file) {
  const table = parseCsv(await file.text());
  const header = table.shift();
  const ids = header.indexOf(isDrive ? "event_id" : "review_id");
  const vis = header.indexOf(observationField);
  const judgment = header.indexOf(judgmentField);
  const comment = header.indexOf(commentField);
  if ([ids, vis, judgment, comment].some(index => index < 0)) throw new Error("审查 CSV 缺少必要列");
  let count = 0;
  for (const values of table) {
    if (!byId.has(values[ids])) continue;
    answers[values[ids]] = {
      [observationField]: values[vis] || "",
      [judgmentField]: values[judgment] === "unreviewed" ? "" : values[judgment] || "",
      [commentField]: values[comment] || ""
    };
    count++;
  }
  if (!count) throw new Error("没有找到与本审查表匹配的 review_id");
  persist(); selectCase(activeId);
  document.getElementById("save-status").textContent = `已从 CSV 载入 ${count} 行人工判断`;
}

const videoFilter = document.getElementById("video-filter");
const names = {
  fc_tokyo_aomori_h1: "FC 东京 / 青森山田 · 前半场",
  fc_tokyo_aomori_h2: "FC 东京 / 青森山田 · 后半场",
  urawa_ryutsu_h1: "浦和 / 流经大柏 · 前半场",
  urawa_ryutsu_h2: "浦和 / 流经大柏 · 后半场"
};
for (const id of [...new Set(rows.map(row => row.video_id))]) {
  const option = document.createElement("option"); option.value = id; option.textContent = names[id] || id; videoFilter.appendChild(option);
}
for (const id of ["video-filter", "status-filter", "review-filter"]) {
  document.getElementById(id).addEventListener("change", () => {
    const filtered = filteredRows();
    if (filtered.length && !filtered.some(row => row.review_id === activeId)) selectCase(filtered[0].review_id);
    else renderList();
  });
}
video.addEventListener("loadedmetadata", () => seekFrame(byId.get(activeId).clip.center_relative_frame));
video.addEventListener("timeupdate", () => updateClock(video.currentTime));
video.addEventListener("error", () => { document.getElementById("video-error").hidden = false; });
slider.addEventListener("input", () => seekFrame(Number(slider.value)));
document.getElementById("back-frame").onclick = () => seekFrame(Number(slider.value) - 1);
document.getElementById("forward-frame").onclick = () => seekFrame(Number(slider.value) + 1);
document.getElementById("back-second").onclick = () => seekFrame(Number(slider.value) - 25);
document.getElementById("forward-second").onclick = () => seekFrame(Number(slider.value) + 25);
document.getElementById("event-jump").onclick = () => seekFrame(byId.get(activeId).clip.center_relative_frame);
document.getElementById("previous").onclick = () => moveCase(-1);
document.getElementById("next").onclick = () => moveCase(1);
document.getElementById("human-comment").addEventListener("input", event => {
  answers[activeId][commentField] = event.target.value;
  persist();
});
document.getElementById("export").onclick = exportCsv;
document.getElementById("save-project").onclick = saveToProject;
document.getElementById("import").addEventListener("change", async event => {
  if (!event.target.files[0]) return;
  try { await importCsv(event.target.files[0]); }
  catch (error) { alert(`导入失败：${error.message}`); }
  event.target.value = "";
});
document.addEventListener("keydown", event => {
  if (["TEXTAREA", "INPUT", "SELECT"].includes(document.activeElement.tagName)) return;
  if (event.code === "Space") { event.preventDefault(); video.paused ? video.play() : video.pause(); }
  else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
    event.preventDefault(); seekFrame(Number(slider.value) + (event.key === "ArrowRight" ? 1 : -1) * (event.shiftKey ? 25 : 1));
  } else if (event.key.toLowerCase() === "n") moveCase(1);
  else if (event.key.toLowerCase() === "p") moveCase(-1);
});

selectCase(activeId);
if (!storageWorks) document.getElementById("save-status").textContent = "浏览器未允许自动保存，请经常导出 CSV";
