// ── 内核编译 ─────────────────────────────────────────────

let _currentTheme = "";
let _kernelData = null;

function doCompile() {
  const theme = document.getElementById("themeInput").value.trim();
  if (!theme) return alert("请输入或选择一个主题");

  const btn = document.getElementById("btnCompile");
  const status = document.getElementById("compileStatus");

  btn.disabled = true;
  btn.textContent = "⏳ 生成中…";
  status.className = "status loading";
  status.textContent = "AI 正在分析主题，编译叙事内核…";

  // 清除上次生成的小说
  document.getElementById("sectionNovel").style.display = "none";
  document.getElementById("novelStages").innerHTML = "";

  fetch("/api/kernel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme }),
  })
    .then(r => r.json())
    .then(payload => {
      if (!payload.data) throw new Error(payload.message || "未知错误");

      document.getElementById("sectionError").style.display = "none";

      const d = payload.data;
      _currentTheme = d.theme;
      _kernelData = d.kernel;

      document.getElementById("resultTheme").textContent = "《" + d.theme + "》叙事内核";
      document.getElementById("kernelContent").innerHTML = marked.parse(d.kernel);
      document.getElementById("sectionKernel").style.display = "block";
      document.getElementById("btnConfirmKernel").disabled = false;

      status.className = "status";
      status.textContent = "";
    })
    .catch(e => {
      status.className = "status error";
      status.textContent = "";
      document.getElementById("errorMsg").textContent = e.message;
      document.getElementById("sectionError").style.display = "block";
    })
    .finally(() => {
      btn.disabled = false;
      btn.textContent = "生成内核";
    });
}

// ── 确认内核，开始写小说 ─────────────────────────────────

const STAGES = ["起", "承", "转", "合"];
let _novelFullText = "";

function confirmKernel() {
  document.getElementById("btnConfirmKernel").disabled = true;
  document.getElementById("sectionNovel").style.display = "block";
  document.getElementById("sectionNovel").scrollIntoView({ behavior: "smooth" });

  // 初始化四个阶段面板
  const container = document.getElementById("novelStages");
  container.innerHTML = STAGES.map(name => `
    <div class="stage-panel" id="stage-${name}">
      <div class="stage-panel-header" onclick="toggleStage('${name}')">
        <span class="icon">▶</span>
        <span>${name} · 第${STAGES.indexOf(name) + 1}阶段</span>
      </div>
      <div class="stage-panel-body loading">等待生成…</div>
    </div>
  `).join("");

  // 重置进度点
  document.querySelectorAll(".stage-dot").forEach(d => d.className = "stage-dot");

  generateNovel();
}

function toggleStage(name) {
  document.getElementById("stage-" + name).classList.toggle("open");
}

// ── 小说生成（轮询） ─────────────────────────────────────

async function generateNovel() {
  const status = document.getElementById("novelStatus");
  status.className = "status loading";

  let taskId = null;
  try {
    const resp = await fetch("/api/novel/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ theme: _currentTheme, kernel: _kernelData }),
    });
    const data = await resp.json();
    if (!data.data || !data.data.task_id) throw new Error(data.message || "任务创建失败");
    taskId = data.data.task_id;
  } catch (e) {
    status.className = "status error";
    status.textContent = "启动失败: " + e.message;
    return;
  }

  const doneStages = new Set();

  status.textContent = "正在生成「起」…";
  const interval = setInterval(async () => {
    try {
      const resp = await fetch("/api/novel/generate/" + taskId);
      const data = await resp.json();
      const state = data.data;

      // 更新进度点
      STAGES.forEach(name => {
        const dot = document.querySelector(`.stage-dot[data-stage="${name}"]`);
        if (state.stages && state.stages[name]) {
          dot.className = "stage-dot done";
        } else if (name === state.current_stage) {
          dot.className = "stage-dot active";
        }
      });

      // 更新已完成阶段的面板内容
      if (state.stages) {
        for (const [name, content] of Object.entries(state.stages)) {
          if (!doneStages.has(name) && content) {
            doneStages.add(name);
            const panel = document.getElementById("stage-" + name);
            const body = panel.querySelector(".stage-panel-body");
            body.className = "stage-panel-body";
            body.innerHTML = marked.parse(content);
            panel.classList.add("open");
          }
        }
      }

      // 更新状态文字
      if (state.status === "done") {
        clearInterval(interval);
        status.className = "status";
        status.textContent = "小说生成完成 ✓";
        document.querySelectorAll(".stage-dot").forEach(d => d.className = "stage-dot done");

        // 保存全文，供 TTS 导入使用
        _novelFullText = STAGES.map(name => state.stages?.[name] || "").filter(Boolean).join("\n\n");
      } else if (state.status === "error") {
        clearInterval(interval);
        status.className = "status error";
        status.textContent = "生成失败: " + (state.error || "未知错误");
      } else {
        const cur = state.current_stage || STAGES[0];
        status.textContent = "正在生成「" + cur + "」…";
      }
    } catch (e) {
      clearInterval(interval);
      status.className = "status error";
      status.textContent = "轮询失败: " + e.message;
    }
  }, 2000);
}

// ── utils ─────────────────────────────────────────────────

function switchTab(tabId) {
  document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
  document.querySelector(`[data-tab="${tabId}"]`).classList.add("active");
  document.querySelectorAll(".tab-content").forEach(c => c.style.display = "none");
  document.getElementById(tabId).style.display = "";
}

function resetUI() {
  document.getElementById("sectionInput").style.display = "block";
  document.getElementById("sectionKernel").style.display = "none";
  document.getElementById("sectionNovel").style.display = "none";
  document.getElementById("sectionError").style.display = "none";
  document.getElementById("compileStatus").className = "status";
  document.getElementById("compileStatus").textContent = "";
  document.getElementById("novelStages").innerHTML = "";
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

  // 切换提示 / 上传区显示
  document.getElementById("ttsHintNovel").style.display = mode === "novel" ? "" : "none";
  document.getElementById("ttsUploadZone").style.display = mode === "file" ? "" : "none";

  if (mode === "novel") {
    document.getElementById("ttsText").value = _novelFullText;
  }
  updateTTSCharCount();
}

function handleTTSFile(input) {
  const file = input.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("ttsText").value = e.target.result;
    updateTTSCharCount();
  };
  reader.readAsText(file, "UTF-8");
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
