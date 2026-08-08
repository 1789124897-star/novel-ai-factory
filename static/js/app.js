// ── compile ───────────────────────────────────────────────

function doCompile() {
  const theme = document.getElementById("themeInput").value.trim();
  if (!theme) return alert("请输入或选择一个主题");

  const wordCount = parseInt(document.getElementById("wordCount").value) || 8000;

  const btn = document.getElementById("btnCompile");
  const status = document.getElementById("compileStatus");

  btn.disabled = true;
  btn.textContent = "⏳ 生成中…";
  status.className = "status loading";
  status.textContent = "AI 正在分析主题，编译叙事内核…";

  fetch("/api/kernel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme, target_words: wordCount }),
  })
    .then(r => r.json())
    .then(payload => {
      if (!payload.data) throw new Error(payload.message || "未知错误");

      // hide input, show result
      document.getElementById("sectionInput").style.display = "none";
      document.getElementById("sectionError").style.display = "none";

      const d = payload.data;
      document.getElementById("resultTheme").textContent = "《" + d.theme + "》叙事内核";
      document.getElementById("kernelContent").textContent = JSON.stringify(d.kernel, null, 2);
      document.getElementById("sectionResult").style.display = "block";

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

function resetUI() {
  document.getElementById("sectionInput").style.display = "block";
  document.getElementById("sectionResult").style.display = "none";
  document.getElementById("sectionError").style.display = "none";
  document.getElementById("compileStatus").className = "status";
  document.getElementById("compileStatus").textContent = "";
}

// ── utils ─────────────────────────────────────────────────

function esc(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}


