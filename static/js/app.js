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
  fetchVideoClipCount();
});

// ── 视频制作 ───────────────────────────────────────────────

let _videoClipsAvailable = 0;

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

function switchVideoAudioSource() {
  const mode = document.getElementById("videoAudioSource").value;
  document.getElementById("videoAudioUploadField").style.display = mode === "upload" ? "" : "none";
}

function switchVideoSrtSource() {
  const mode = document.getElementById("videoSrtSource").value;
  document.getElementById("videoSrtUploadField").style.display = mode === "upload" ? "" : "none";
}

function toggleVideoBgm() {
  const on = document.getElementById("videoBgmToggle").checked;
  document.getElementById("videoBgmUploadField").style.display = on ? "" : "none";
}

function toggleVideoWatermark() {
  const on = document.getElementById("videoWatermarkToggle").checked;
  document.getElementById("videoWatermarkField").style.display = on ? "" : "none";
}

async function doGenVideo() {
  const status = document.getElementById("videoStatus");
  const result = document.getElementById("videoResult");
  const btn = document.getElementById("btnGenVideo");

  result.style.display = "none";

  if (_videoClipsAvailable === 0) {
    status.className = "status error";
    status.textContent = "assets/videos/ 中没有背景视频片段，请先放入 .mp4 文件";
    return;
  }

  // 校验音频源
  const audioSource = document.getElementById("videoAudioSource").value;
  if (audioSource === "tts" && !_ttsTaskId) {
    status.className = "status error";
    status.textContent = "请先在「Edge TTS 配音」生成配音，或切换为上传 MP3";
    return;
  }

  btn.disabled = true;
  btn.textContent = "⏳ 生成中…";
  status.className = "status loading";
  status.textContent = "正在提交视频制作任务…";

  const form = new FormData();
  form.append("audio_source", audioSource);
  form.append("audio_tts_task_id", _ttsTaskId);
  form.append("srt_source", document.getElementById("videoSrtSource").value);
  form.append("srt_tts_task_id", _ttsTaskId);
  form.append("watermark_text", document.getElementById("videoWatermarkText").value.trim());

  const audioFile = document.getElementById("videoAudioFile").files[0];
  if (audioSource === "upload" && audioFile) form.append("audio_file", audioFile);
  const srtFile = document.getElementById("videoSrtFile").files[0];
  if (document.getElementById("videoSrtSource").value === "upload" && srtFile) form.append("srt_file", srtFile);
  const bgmFile = document.getElementById("videoBgmFile").files[0];
  if (document.getElementById("videoBgmToggle").checked && bgmFile) form.append("bgm_file", bgmFile);

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
        <span class="icon">▶</span><span>${name} · 第${STAGES.indexOf(name) + 1}阶段</span>
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

  const novelStatus = document.getElementById("genNovelStatus");
  novelStatus.className = "status loading";
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
        novelStatus.className = "status"; novelStatus.textContent = "";
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
        novelStatus.textContent = "正在生成「" + cur + "」…";
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

// 切到视频 Tab 时自动填入 TTS 数据提示
const _origSwitchTab = switchTab;
switchTab = function(tabId) {
  _origSwitchTab(tabId);
  if (tabId === "tabVideo") {
    const hint = document.getElementById("videoStatus");
    if (_ttsAudioUrl) {
      hint.className = "status";
      hint.textContent = "已检测到 TTS 配音产物，可直接生成视频";
    } else {
      hint.className = "status";
      hint.textContent = "请先在「Edge TTS 配音」生成配音";
    }
  }
};
