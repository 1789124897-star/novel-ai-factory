// ── 内核编译 ─────────────────────────────────────────────

let _currentTheme = "";
let _kernelData = null;

async function doCompile() {
  const theme = document.getElementById("themeInput").value.trim();
  if (!theme) return alert("请输入或选择一个主题");

  const btn = document.getElementById("btnCompile");
  const status = document.getElementById("compileStatus");

  btn.disabled = true;
  btn.textContent = "⏳ 生成中…";
  status.className = "status loading";
  status.textContent = "AI 正在分析主题，编译叙事内核…";

  let taskId = null;
  try {
    const resp = await fetch("/api/novel/kernel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme }),
    });
    const payload = await resp.json();
    if (!payload.data || !payload.data.task_id) throw new Error(payload.message || "任务创建失败");
    taskId = payload.data.task_id;
  } catch (e) {
    status.className = "status error";
    status.textContent = "启动失败: " + e.message;
    btn.disabled = false;
    btn.textContent = "生成内核";
    return;
  }

  const interval = setInterval(async () => {
    try {
      const resp = await fetch("/api/novel/kernel/" + taskId);
      const payload = await resp.json();
      const state = payload.data;

      if (state.status === "done") {
        clearInterval(interval);
        document.getElementById("sectionError").style.display = "none";

        _currentTheme = state.theme;
        _kernelData = state.kernel;

        document.getElementById("resultTheme").textContent = "《" + state.theme + "》叙事内核";
        document.getElementById("kernelContent").innerHTML = marked.parse(state.kernel);
        document.getElementById("sectionKernel").style.display = "block";
        document.getElementById("btnConfirmKernel").disabled = false;

        status.className = "status";
        status.textContent = "";
        btn.disabled = false;
        btn.textContent = "生成内核";
      } else if (state.status === "error") {
        clearInterval(interval);
        status.className = "status error";
        status.textContent = "";
        document.getElementById("errorMsg").textContent = state.error || "未知错误";
        document.getElementById("sectionError").style.display = "block";
        btn.disabled = false;
        btn.textContent = "生成内核";
      }
    } catch (e) {
      clearInterval(interval);
      status.className = "status error";
      status.textContent = "轮询失败: " + e.message;
      btn.disabled = false;
      btn.textContent = "生成内核";
    }
  }, 2000);
}

// ── 确认内核，开始写小说 ─────────────────────────────────

const STAGES = ["起", "承", "转", "合"];
let _novelFullText = "";

function confirmKernel() {
  document.getElementById("btnConfirmKernel").disabled = true;
  switchTab("tabNovelGen");
}

// ── utils ─────────────────────────────────────────────────

function switchTab(tabId) {
  document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
  document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
  document.querySelectorAll(".tab-content").forEach(c => c.style.display = "none");
  document.getElementById(tabId).style.display = "";
  if (tabId === "tabNovelGen") { loadGenPrompt(); checkTab1Kernel(); }
}

function resetUI() {
  document.getElementById("sectionInput").style.display = "block";
  document.getElementById("sectionKernel").style.display = "none";
  document.getElementById("sectionError").style.display = "none";
  document.getElementById("compileStatus").className = "status";
  document.getElementById("compileStatus").textContent = "";
  document.getElementById("ttsResult").style.display = "none";
  _novelFullText = "";
  document.getElementById("ttsText").value = "";
  document.getElementById("ttsCharCount").textContent = "0";
}

// ── TTS ───────────────────────────────────────────────────

let _ttsSource = "novel";
let _ttsAudioUrl = "";
let _ttsSrtUrl = "";
let _ttsTaskId = "";

function switchTTSSource(mode) {
  _ttsSource = mode;
  document.querySelectorAll(".tts-source-tab").forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");

  document.getElementById("ttsHintNovel").style.display = mode === "novel" ? "" : "none";

  if (mode === "novel") {
    document.getElementById("ttsText").value = _novelFullText;
  }
  updateTTSCharCount();
}

function updateTTSCharCount() {
  const len = document.getElementById("ttsText").value.length;
  document.getElementById("ttsCharCount").textContent = len;
}

async function doGenTTS() {
  const text = document.getElementById("ttsText").value.trim();
  if (!text) return alert("请先输入配音文本");

  const voice = document.getElementById("ttsVoice").value;
  const rate = document.getElementById("ttsRate").value;
  const btn = document.getElementById("btnGenTTS");
  const status = document.getElementById("ttsStatus");
  const result = document.getElementById("ttsResult");

  btn.disabled = true;
  btn.textContent = "⏳ 合成中…";
  status.className = "status loading";
  status.textContent = "Edge TTS 正在合成语音…";
  result.style.display = "none";

  let taskId = null;
  try {
    const resp = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice, rate }),
    });
    const data = await resp.json();
    if (!data.data || !data.data.task_id) throw new Error(data.message || "任务创建失败");
    taskId = data.data.task_id;
  } catch (e) {
    status.className = "status error";
    status.textContent = "启动失败: " + e.message;
    btn.disabled = false;
    btn.textContent = "🎙️ 生成配音";
    return;
  }

  const interval = setInterval(async () => {
    try {
      const resp = await fetch("/api/tts/" + taskId);
      const data = await resp.json();
      const state = data.data;

      if (state.status === "done") {
        clearInterval(interval);
        status.className = "status";
        status.textContent = "配音完成 ✓（" + state.duration_sec + " 秒）";

        _ttsAudioUrl = state.audio_url;
        _ttsSrtUrl = state.srt_url;
        _ttsTaskId = taskId;

        // 显示音频和下载链接
        const audio = document.getElementById("ttsAudio");
        audio.src = state.audio_url;
        audio.load();

        document.getElementById("ttsDownloadAudio").href = state.audio_url;
        document.getElementById("ttsDownloadSrt").href = state.srt_url;
        result.style.display = "";

        btn.disabled = false;
        btn.textContent = "🎙️ 重新生成";
      } else if (state.status === "error") {
        clearInterval(interval);
        status.className = "status error";
        status.textContent = "合成失败: " + (state.error || "未知错误");
        btn.disabled = false;
        btn.textContent = "🎙️ 生成配音";
      } else {
        status.textContent = "Edge TTS 正在合成语音…";
      }
    } catch (e) {
      clearInterval(interval);
      status.className = "status error";
      status.textContent = "轮询失败: " + e.message;
      btn.disabled = false;
      btn.textContent = "🎙️ 生成配音";
    }
  }, 1500);
}

// 监听文本变化更新字数
document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("ttsText").addEventListener("input", updateTTSCharCount);
  // 输入变更后重置续跑状态，避免新配置复用旧产物
  ["ocThemeInput", "ocWatermarkTheme", "ocWatermarkAuthor"].forEach(id =>
    document.getElementById(id).addEventListener("input", ocResetResumeBtn));
  fetchVideoClipCount();
});

// ── 视频制作 ───────────────────────────────────────────────

let _videoClipsAvailable = 0;
let _videoAudioSrc = "tts";
let _videoSrtSrc = "tts";
let _videoBgSrc = "default";
let _videoBgmSrc = "default";
let _videoBgFiles = [];  // 用户上传的背景视频文件列表

function fetchVideoClipCount() {
  fetch("/api/video/clips")
    .then(r => r.json())
    .then(data => {
      _videoClipsAvailable = data.data?.count || 0;
      document.getElementById("videoClipCount").textContent =
        _videoClipsAvailable > 0 ? `${_videoClipsAvailable} 个片段可用` : "无可用片段";
    })
    .catch(() => {
      document.getElementById("videoClipCount").textContent = "无法检测";
    });
}

// ── 音频源 ────────────────────────────────────────────

function switchVideoAudioSource(mode) {
  _videoAudioSrc = mode;
  const tabs = document.querySelectorAll("#tabVideo .video-source-tabs")[0].querySelectorAll(".tts-source-tab");
  tabs.forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
  document.getElementById("videoAudioUpload").style.display = mode === "upload" ? "" : "none";
  document.getElementById("videoAudioTtsHint").style.display = mode === "tts" ? "" : "none";
  updateTtsHint("videoAudioTtsHint", _videoAudioSrc);
}

// ── 字幕源 ────────────────────────────────────────────

function switchVideoSrtSource(mode) {
  _videoSrtSrc = mode;
  const tabs = document.querySelectorAll("#tabVideo .video-source-tabs")[1].querySelectorAll(".tts-source-tab");
  tabs.forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
  document.getElementById("videoSrtUpload").style.display = mode === "upload" ? "" : "none";
  document.getElementById("videoSrtTtsHint").style.display = mode === "tts" ? "" : "none";
  updateTtsHint("videoSrtTtsHint", _videoSrtSrc);
}

function updateTtsHint(elId, srcMode) {
  if (srcMode !== "tts") return;
  const hint = document.getElementById(elId);
  if (_ttsAudioUrl) {
    hint.className = "tts-hint";
    hint.style.background = "#eaf7ea";
    hint.style.borderLeftColor = "var(--green)";
    hint.textContent = "✅ 已检测到配音产物，可直接生成";
  } else {
    hint.className = "tts-hint";
    hint.style.background = "";
    hint.style.borderLeftColor = "";
    hint.textContent = "未检测到配音产物，请先在「Edge TTS 配音」中生成";
  }
}

// ── 背景视频 ──────────────────────────────────────────

function switchVideoBgSource(mode) {
  _videoBgSrc = mode;
  const tabs = document.querySelectorAll("#tabVideo .video-source-tabs")[2].querySelectorAll(".tts-source-tab");
  tabs.forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
  document.getElementById("videoBgDefault").style.display = mode === "default" ? "" : "none";
  document.getElementById("videoBgUpload").style.display = mode === "upload" ? "" : "none";
}

function addVideoBgFile() {
  const input = document.getElementById("videoBgFileInput");
  if (!input.files.length) return;
  for (const f of input.files) {
    _videoBgFiles.push(f);
  }
  renderVideoBgList();
  input.value = "";
}

function removeVideoBgFile(index) {
  _videoBgFiles.splice(index, 1);
  renderVideoBgList();
}

function renderVideoBgList() {
  const list = document.getElementById("videoBgFileList");
  if (!_videoBgFiles.length) {
    list.innerHTML = "";
    return;
  }
  list.innerHTML = _videoBgFiles.map((f, i) =>
    `<li><span>${f.name} (${(f.size / 1024 / 1024).toFixed(1)} MB)</span>` +
    `<button onclick="removeVideoBgFile(${i})" class="video-file-del">✕</button></li>`
  ).join("");
}

// ── BGM ───────────────────────────────────────────────

function switchVideoBgmSource(mode) {
  _videoBgmSrc = mode;
  const tabs = document.querySelectorAll("#tabVideo .video-source-tabs")[3].querySelectorAll(".tts-source-tab");
  tabs.forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
  document.getElementById("videoBgmUpload").style.display = mode === "upload" ? "" : "none";
}

async function doGenVideo() {
  const status = document.getElementById("videoStatus");
  const result = document.getElementById("videoResult");
  const btn = document.getElementById("btnGenVideo");

  result.style.display = "none";

  // 校验背景视频
  if (_videoBgSrc === "default" && _videoClipsAvailable === 0) {
    status.className = "status error";
    status.textContent = "assets/videos/ 中没有背景视频片段，请先放入 .mp4 文件或切换为上传";
    return;
  }

  // 校验音频源
  if (_videoAudioSrc === "tts" && !_ttsTaskId) {
    status.className = "status error";
    status.textContent = "请先在「Edge TTS 配音」生成配音，或切换为上传 MP3";
    return;
  }

  btn.disabled = true;
  btn.textContent = "⏳ 生成中…";
  status.className = "status loading";
  status.textContent = "正在提交视频制作任务…";

  const form = new FormData();
  form.append("audio_source", _videoAudioSrc);
  form.append("audio_tts_task_id", _ttsTaskId);
  form.append("srt_source", _videoSrtSrc);
  form.append("srt_tts_task_id", _ttsTaskId);
  form.append("theme", document.getElementById("videoThemeInput").value.trim());
  form.append("watermark_text", document.getElementById("videoWatermarkText").value.trim());
  form.append("video_source", _videoBgSrc);
  form.append("bgm_source", _videoBgmSrc);

  const audioFile = document.getElementById("videoAudioFile").files[0];
  if (_videoAudioSrc === "upload" && audioFile) form.append("audio_file", audioFile);
  const srtFile = document.getElementById("videoSrtFile").files[0];
  if (_videoSrtSrc === "upload" && srtFile) form.append("srt_file", srtFile);
  const bgmFile = document.getElementById("videoBgmFile").files[0];
  if (_videoBgmSrc === "upload" && bgmFile) form.append("bgm_file", bgmFile);
  if (_videoBgSrc === "upload" && _videoBgFiles.length) {
    _videoBgFiles.forEach(f => form.append("video_files", f));
  }

  let taskId = null;
  try {
    const resp = await fetch("/api/video", { method: "POST", body: form });
    const data = await resp.json();
    if (!data.data || !data.data.task_id) throw new Error(data.message || "任务创建失败");
    taskId = data.data.task_id;
  } catch (e) {
    status.className = "status error";
    status.textContent = "启动失败: " + e.message;
    btn.disabled = false;
    btn.textContent = "🎬 生成视频";
    return;
  }

  const interval = setInterval(async () => {
    try {
      const resp = await fetch("/api/video/" + taskId);
      const data = await resp.json();
      if (!resp.ok || !data.data) throw new Error(data.message || data.detail || "请求失败");
      const state = data.data;

      if (state.status === "done") {
        clearInterval(interval);
        status.className = "status";
        status.textContent = "视频制作完成 ✓";

        const player = document.getElementById("videoPlayer");
        player.querySelector("source")?.remove();
        const src = document.createElement("source");
        src.src = state.video_url;
        src.type = "video/mp4";
        player.appendChild(src);
        player.load();

        document.getElementById("videoDownload").href = state.video_url;
        result.style.display = "";

        btn.disabled = false;
        btn.textContent = "🎬 重新生成";
      } else if (state.status === "error") {
        clearInterval(interval);
        status.className = "status error";
        status.textContent = "制作失败: " + (state.error || "未知错误");
        btn.disabled = false;
        btn.textContent = "🎬 生成视频";
      } else {
        status.textContent = state.step || "视频制作中…";
      }
    } catch (e) {
      clearInterval(interval);
      status.className = "status error";
      status.textContent = "轮询失败: " + e.message;
      btn.disabled = false;
      btn.textContent = "🎬 生成视频";
    }
  }, 2000);
}

// ── 📝 小说生成 Tab ─────────────────────────────────────

let _genDefaultPrompt = "";
let _genKernelSource = "import_tab1";
let _genCurrentKernel = "";

function switchGenKernelSource(mode) {
  _genKernelSource = mode;
  const isManual = mode === "manual";
  document.getElementById("genKernelManual").style.display = isManual ? "" : "none";
  document.getElementById("genBtnImportTab1").closest("div").style.display = isManual ? "none" : "";
  if (!isManual) checkTab1Kernel();
}

function toggleGenPrompt() {
  const body = document.getElementById("genPromptBody");
  const btn = document.getElementById("genBtnTogglePrompt");
  const open = body.style.display === "none";
  body.style.display = open ? "" : "none";
  btn.textContent = open ? "📝 收起提示词模板" : "📝 编辑提示词模板";
}

async function loadGenPrompt() {
  if (_genDefaultPrompt) {
    document.getElementById("genPromptTemplate").value = _genDefaultPrompt;
    return;
  }
  try {
    const resp = await fetch("/api/novel/prompt-template");
    const data = await resp.json();
    _genDefaultPrompt = data.data.content;
    document.getElementById("genPromptTemplate").value = _genDefaultPrompt;
  } catch (e) { console.error("加载提示词失败:", e); }
}

async function resetGenPrompt() { _genDefaultPrompt = ""; await loadGenPrompt(); }

// ── 从 Tab1 导入内核 ───────────────────────────────────

function checkTab1Kernel() {
  const btn = document.getElementById("genBtnImportTab1");
  const hint = document.getElementById("genKernelTab1Hint");
  const preview = document.getElementById("genKernelTab1Preview");

  // 已导入过，保持导入状态
  if (_genCurrentKernel) {
    btn.disabled = true;
    btn.textContent = "✅ 已导入";
    hint.textContent = "内核已导入，可以开始生成小说。";
    return;
  }

  if (_kernelData && _currentTheme) {
    btn.disabled = false;
    btn.textContent = `📥 导入内核：「${_currentTheme}」`;
    hint.textContent = "";
    preview.style.display = "none";
  } else {
    btn.disabled = true;
    btn.textContent = "📥 请先在「编译叙事内核」中生成内核";
    hint.textContent = "";
  }
}

function importKernelFromTab1() {
  if (!_kernelData || !_currentTheme) return alert("请先在编译模块中生成内核");
  _genCurrentKernel = _kernelData;
  document.getElementById("genThemeInput").value = _currentTheme;
  document.getElementById("genKernelText").value = _kernelData;
  const preview = document.getElementById("genKernelTab1Preview");
  preview.innerHTML = marked.parse(_kernelData);
  preview.style.display = "";
  const btn = document.getElementById("genBtnImportTab1");
  btn.disabled = true;
  btn.textContent = "✅ 已导入";
  document.getElementById("genKernelTab1Hint").textContent = "内核已导入，可以开始生成小说。";
}

// ── AI 生成内核（已移除，内核统一从 Tab1 编译模块获取） ──

function getGenKernel() {
  if (_genKernelSource === "manual") return document.getElementById("genKernelText").value.trim();
  return _genCurrentKernel;
}

// ── 生成小说 ────────────────────────────────────────────

async function doGenGenerateNovel() {
  const theme = document.getElementById("genThemeInput").value.trim();
  const kernel = getGenKernel();
  const targetWords = parseInt(document.getElementById("genTargetWords").value) || 8000;
  const promptText = document.getElementById("genPromptTemplate").value.trim();

  if (!theme) return alert("请输入故事主题");
  if (!kernel) return alert("请先生成内核、手动编写或导入历史内核");
  if (!promptText) return alert("提示词模板不能为空");

  _genCurrentKernel = kernel;

  const section = document.getElementById("genSectionNovel");
  section.style.display = "block"; section.scrollIntoView({ behavior: "smooth" });

  const container = document.getElementById("genNovelStages");
  container.innerHTML = STAGES.map(name => `
    <div class="stage-panel" id="genStage-${name}">
      <div class="stage-panel-header" onclick="toggleGenStage('${name}')">
        <span class="icon">▶</span>
        <span>${name} · 第${STAGES.indexOf(name) + 1}阶段</span>
        <span class="stage-word-count"></span>
      </div>
      <div class="stage-panel-body loading">等待生成…</div>
    </div>
  `).join("");

  const progressBar = document.getElementById("genNovelProgress");
  progressBar.querySelectorAll(".stage-dot").forEach(d => d.className = "stage-dot");

  const btn = document.getElementById("genBtnGenerate");
  const status = document.getElementById("genGenStatus");
  btn.disabled = true; btn.textContent = "⏳ 启动中…";
  status.className = "status loading"; status.textContent = "正在提交生成任务…";

  const customPrompt = promptText !== _genDefaultPrompt ? promptText : null;

  let taskId = null;
  try {
    const resp = await fetch("/api/novel/generate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme, kernel, target_words: targetWords, custom_prompt: customPrompt || undefined }),
    });
    const data = await resp.json();
    if (!data.data?.task_id) throw new Error(data.message || "任务创建失败");
    taskId = data.data.task_id;
  } catch (e) {
    status.className = "status error"; status.textContent = "启动失败: " + e.message;
    btn.disabled = false; btn.textContent = "🚀 生成小说"; return;
  }

  const doneStages = new Set();

  status.textContent = "正在生成「起」…";
  const interval = setInterval(async () => {
    try {
      const resp = await fetch("/api/novel/generate/" + taskId);
      const state = (await resp.json()).data;

      STAGES.forEach(name => {
        const dot = progressBar.querySelector(`.stage-dot[data-stage="${name}"]`);
        if (state.stages?.[name]) dot.className = "stage-dot done";
        else if (name === state.current_stage) dot.className = "stage-dot active";
      });

      if (state.stages) {
        for (const [name, content] of Object.entries(state.stages)) {
          if (!doneStages.has(name) && content) {
            doneStages.add(name);
            const panel = document.getElementById("genStage-" + name);
            // 更新字数
            const wordCount = panel.querySelector(".stage-word-count");
            if (wordCount) wordCount.textContent = content.length + " 字";
            const body = panel.querySelector(".stage-panel-body");
            body.className = "stage-panel-body";
            body.innerHTML = marked.parse(content);
            panel.classList.add("open");
          }
        }
      }

      if (state.status === "done") {
        clearInterval(interval);
        status.className = "status"; status.textContent = "小说生成完成 ✓";
        progressBar.querySelectorAll(".stage-dot").forEach(d => d.className = "stage-dot done");
        btn.disabled = false; btn.textContent = "🚀 重新生成";
        // 同步到 TTS
        _novelFullText = STAGES.map(n => state.stages?.[n] || "").filter(Boolean).join("\n\n");
      } else if (state.status === "error") {
        clearInterval(interval);
        status.className = "status error"; status.textContent = "生成失败: " + (state.error || "未知");
        btn.disabled = false; btn.textContent = "🚀 生成小说";
      } else {
        const cur = state.current_stage || STAGES[0];
        status.textContent = "正在生成「" + cur + "」…";
      }
    } catch (e) {
      clearInterval(interval);
      status.className = "status error"; status.textContent = "轮询失败: " + e.message;
      btn.disabled = false; btn.textContent = "🚀 生成小说";
    }
  }, 2000);
}

function toggleGenStage(name) {
  document.getElementById("genStage-" + name).classList.toggle("open");
}

// 切到视频 Tab 时刷新提示
const _origSwitchTab = switchTab;
switchTab = function(tabId) {
  _origSwitchTab(tabId);
  if (tabId === "tabVideo") {
    updateTtsHint("videoAudioTtsHint", _videoAudioSrc);
    updateTtsHint("videoSrtTtsHint", _videoSrtSrc);
  }
};

// ── ⚡ 一键生成（全链路编排）─────────────────────────────

const OC_STEPS = [
  { key: "compile", label: "编译叙事内核" },
  { key: "generate", label: "四阶段小说生成" },
  { key: "tts", label: "TTS 配音" },
  { key: "video", label: "视频合成" },
];

let _ocStepIdx = -1; // 当前步骤下标，用于失败定位

// ── 高级选项状态 ────────────────────────────────────

let _ocBgSrc = "default";
let _ocBgmSrc = "default";
let _ocBgFiles = [];

function toggleOcAdvanced() {
  const body = document.getElementById("ocAdvancedBody");
  const btn = document.getElementById("ocBtnToggleAdvanced");
  const open = body.style.display === "none";
  body.style.display = open ? "" : "none";
  btn.textContent = open ? "⚙️ 收起高级选项" : "⚙️ 高级选项（可选）";
}

function switchOcBgSource(mode) {
  _ocBgSrc = mode;
  ocResetResumeBtn();
  const tabs = document.querySelectorAll("#ocAdvancedBody .video-source-tabs")[0].querySelectorAll(".tts-source-tab");
  tabs.forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
  document.getElementById("ocBgUpload").style.display = mode === "upload" ? "" : "none";
}

function switchOcBgmSource(mode) {
  _ocBgmSrc = mode;
  ocResetResumeBtn();
  const tabs = document.querySelectorAll("#ocAdvancedBody .video-source-tabs")[1].querySelectorAll(".tts-source-tab");
  tabs.forEach(t => t.classList.remove("active"));
  event.target.classList.add("active");
}

function addOcBgFile() {
  const input = document.getElementById("ocBgFileInput");
  if (!input.files.length) return;
  for (const f of input.files) {
    _ocBgFiles.push(f);
  }
  renderOcBgList();
  input.value = "";
  ocResetResumeBtn();
}

function removeOcBgFile(index) {
  _ocBgFiles.splice(index, 1);
  renderOcBgList();
  ocResetResumeBtn();
}

function renderOcBgList() {
  const list = document.getElementById("ocBgFileList");
  if (!_ocBgFiles.length) {
    list.innerHTML = "";
    return;
  }
  list.innerHTML = _ocBgFiles.map((f, i) =>
    `<li><span>${f.name} (${(f.size / 1024 / 1024).toFixed(1)} MB)</span>` +
    `<button onclick="removeOcBgFile(${i})" class="video-file-del">✕</button></li>`
  ).join("");
}

/** 渲染步骤列表：i < activeIdx 完成，i === activeIdx 进行中，i === failedIdx 失败。 */
function renderOcSteps(activeIdx, failedIdx = -1) {
  const box = document.getElementById("ocSteps");
  box.innerHTML = OC_STEPS.map((s, i) => {
    let cls = "oc-step", icon = "○";
    if (failedIdx >= 0 && i === failedIdx) { cls += " failed"; icon = "✕"; }
    else if (i < activeIdx) { cls += " done"; icon = "✓"; }
    else if (i === activeIdx) { cls += " active"; icon = "⏳"; }
    return `<div class="${cls}"><span class="oc-icon">${icon}</span><span>${s.label}</span></div>`;
  }).join("");
}

// ── 一键生成：提交后端编排任务，轮询进度 ───────────────

let _ocTaskId = "";   // 当前编排任务 id（失败后用于续跑）

/** 用户修改生成配置后重置续跑状态：续跑沿用旧配置，改配置需重新开始。 */
function ocResetResumeBtn() {
  const btn = document.getElementById("btnOneClick");
  if (btn.textContent.includes("重试")) {
    _ocTaskId = "";
    btn.onclick = function() { doOneClick(); };
    btn.textContent = "🚀 一键生成";
  }
}

function ocGetConfig() {
  return {
    theme: document.getElementById("ocThemeInput").value.trim(),
    targetWords: parseInt(document.getElementById("ocTargetWords").value) || 8000,
    voice: document.getElementById("ocVoice").value,
    rate: document.getElementById("ocRate").value,
  };
}

/** 组装编排请求表单（音频/字幕固定走 TTS 产物，背景视频/BGM/水印来自高级选项）。 */
function ocBuildForm() {
  const cfg = ocGetConfig();
  const form = new FormData();
  form.append("theme", cfg.theme);
  form.append("target_words", cfg.targetWords);
  form.append("voice", cfg.voice);
  form.append("rate", cfg.rate);
  form.append("video_source", _ocBgSrc);
  form.append("bgm_source", _ocBgmSrc);
  form.append("watermark_theme", document.getElementById("ocWatermarkTheme").value.trim());
  form.append("watermark_author", document.getElementById("ocWatermarkAuthor").value.trim());
  if (_ocBgSrc === "upload" && _ocBgFiles.length) {
    _ocBgFiles.forEach(f => form.append("video_files", f));
  }
  return form;
}

const OC_STAGE_IDX = { compile: 0, generate: 1, tts: 2, video: 3 };

/** 轮询编排任务，按后端 stage 字段推进步骤条；完成时展示视频。 */
async function ocRunPipeline(taskId) {
  const status = document.getElementById("ocStatus");
  let lastIdx = -1;
  for (;;) {
    await new Promise(r => setTimeout(r, 2000));
    const resp = await fetch("/api/pipeline/" + taskId);
    const payload = await resp.json();
    if (!payload.data) throw new Error(payload.message || payload.detail || "请求失败");
    const state = payload.data;

    if (state.status === "done") {
      _ocStepIdx = 4;
      renderOcSteps(4);
      status.className = "status";
      status.textContent = "全部完成 ✓ 视频已生成";
      const player = document.getElementById("ocPlayer");
      player.querySelector("source")?.remove();
      const src = document.createElement("source");
      src.src = state.video_url;
      src.type = "video/mp4";
      player.appendChild(src);
      player.load();
      document.getElementById("ocDownload").href = state.video_url;
      document.getElementById("ocResult").style.display = "";
      return;
    }
    if (state.status === "error") {
      throw new Error(state.error || "任务失败");
    }
    const idx = OC_STAGE_IDX[state.stage] ?? lastIdx;
    if (idx !== lastIdx) {
      lastIdx = idx;
      _ocStepIdx = idx;
      renderOcSteps(idx);
      // TTS 完成进入视频阶段：同步产物到分步模块，失败可切分步续跑
      if (state.stage === "video" && state.tts_task_id) {
        _ttsTaskId = state.tts_task_id;
        _ttsAudioUrl = state.tts_audio_url || "";
        _ttsSrtUrl = state.tts_srt_url || "";
        _novelFullText = state.novel_text || "";
      }
    }
    status.textContent = "⏳ " + (state.stage_label || "处理中…");
  }
}

/** 失败后的重试：后端从失败阶段续跑，已完成的产物服务端复用。 */
async function resumeOneClick() {
  const btn = document.getElementById("btnOneClick");
  const status = document.getElementById("ocStatus");

  btn.disabled = true;
  btn.textContent = "⏳ 续跑中…";
  status.className = "status";

  try {
    const form = new FormData();
    form.append("old_task_id", _ocTaskId);
    const resp = await fetch("/api/pipeline/resume", { method: "POST", body: form });
    const payload = await resp.json();
    if (!payload.data?.task_id) throw new Error(payload.message || "续跑失败");
    _ocTaskId = payload.data.task_id;
    await ocRunPipeline(_ocTaskId);
    btn.onclick = function() { doOneClick(); };
    btn.textContent = "🚀 一键生成";
  } catch (e) {
    renderOcSteps(_ocStepIdx, _ocStepIdx);
    status.className = "status error";
    status.textContent = "生成失败: " + e.message + "（已完成步骤已保留，可直接重试）";
    btn.onclick = function() { resumeOneClick(); };
    btn.textContent = "↻ 从失败步骤重试";
  } finally {
    btn.disabled = false;
  }
}

async function doOneClick() {
  const cfg = ocGetConfig();
  if (!cfg.theme) return alert("请输入故事主题");

  // 校验背景视频：默认素材为空时必须上传
  if (_ocBgSrc === "default" && _videoClipsAvailable === 0) {
    return alert("assets/videos/ 中没有背景视频片段，请先放入 .mp4 文件，或在高级选项中上传视频");
  }

  const btn = document.getElementById("btnOneClick");
  const status = document.getElementById("ocStatus");
  const progress = document.getElementById("ocProgress");
  const result = document.getElementById("ocResult");

  btn.disabled = true;
  btn.textContent = "⏳ 全链路生成中…";
  progress.style.display = "";
  result.style.display = "none";
  status.className = "status";
  _ocStepIdx = 0;
  renderOcSteps(0);

  try {
    const resp = await fetch("/api/pipeline", { method: "POST", body: ocBuildForm() });
    const payload = await resp.json();
    if (!payload.data?.task_id) throw new Error(payload.message || "任务创建失败");
    _ocTaskId = payload.data.task_id;
    await ocRunPipeline(_ocTaskId);
    btn.onclick = function() { doOneClick(); };
    btn.textContent = "🚀 一键生成";
  } catch (e) {
    renderOcSteps(_ocStepIdx, _ocStepIdx);
    status.className = "status error";
    status.textContent = "生成失败: " + e.message + "（已完成步骤已保留，可直接重试）";
    btn.onclick = function() { resumeOneClick(); };
    btn.textContent = "↻ 从失败步骤重试";
  } finally {
    btn.disabled = false;
  }
}
