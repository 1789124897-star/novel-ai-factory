# novel-ai-factory · 小说AI工厂

**从一句话主题 → 到带字幕的完整视频，全自动。**

> 哥特心理悬疑小说 · DeepSeek V3 · 腾讯云 TTS · MoviePy · FFmpeg

---

## 项目概述

`novel-ai-factory` 是一个 AI 驱动的小说内容生产管线，覆盖从创意到成片的完整链路：

```
主题 → 叙事内核 → 四阶段小说生成 → TTS 语音合成 → BGM 混音
    → 字幕转录 → 视频拼接 → 字幕叠加 → 水印 → 成品视频
```

### 核心特性

- **🧠 叙事内核编译** — LLM 将一句话主题拆解为人物、事件、预言三大锚点
- **📖 四阶段生成** — 起·承·转·合分阶段创作，阶段内自动续写保底字数
- **🔊 智能 TTS** — 引号感知分句 + 短段合并 + 腾讯云语音合成
- **🎬 全自动视频** — 背景片段拼接 + SRT 字幕叠加 + FFmpeg 水印
- **⚙️ 灵活 CLI** — 支持全流程 / 单步 / 自定义阶段组合
- **🏗️ 清晰架构** — 依赖注入、无全局单例、延迟路径创建、类型标注

---

## 快速开始

### 1. 安装

```bash
# 系统依赖 (必须先安装)
# - ffmpeg (pydub + MoviePy 需要)
# - 基于 Chromium 的浏览器 (DrissionPage 需要, 如 Edge/Chrome)

git clone <repo-url> novel-ai-factory
cd novel-ai-factory
pip install -e .
```

### 2. 配置

```bash
cp .env.example .env
# 编辑 .env，填入你的 API 密钥和路径
```

最少需要配置：

| 变量 | 说明 |
|------|------|
| `NOVEL_API_KEY` | 火山引擎 ARK API 密钥 |
| `NOVEL_API_URL` | API 地址 |
| `TENCENT_SECRET_ID` | 腾讯云 SecretId |
| `TENCENT_SECRET_KEY` | 腾讯云 SecretKey |
| `BROWSER_PATH` | 浏览器可执行文件路径 (Edge/Chrome) |

### 3. 准备素材

```bash
assets/
├── videos/          # 背景视频片段 (.mp4)
├── bgm/bgm.mp3      # 背景音乐
├── fonts/           # 字体文件 (.ttf)
└── covers/          # 封面图片 (可选)
```

### 4. 运行

```bash
# 查看主题预设
novel-ai-factory presets

# 仅生成小说
novel-ai-factory novel -t "仵作之死"

# 全流程一键运行
novel-ai-factory run -t "铁甲怪人"

# 自定义阶段组合
novel-ai-factory run -t "钟表与遗忘" --stages compile,generate,tts

# 跳过某些阶段
novel-ai-factory run -t "仵作之死" --skip tts srt
```

---

## 项目结构

```
novel-ai-factory/
├── app/
│   ├── main.py                    # CLI 入口
│   ├── core/
│   │   ├── config.py              # Pydantic Settings (所有配置)
│   │   ├── paths.py               # PathConfig (惰性路径计算)
│   │   └── logging.py             # 日志配置
│   ├── novel/
│   │   ├── compiler.py            # 叙事内核编译
│   │   ├── prompt.py              # 阶段 Prompt 构建
│   │   ├── generator.py           # 四阶段生成器 (起承转合)
│   │   └── presets.py             # 主题预设
│   ├── tts/
│   │   ├── splitter.py            # 智能分句 (引号感知)
│   │   └── engine.py              # TTS 引擎 + BGM 混音
│   ├── subtitle/
│   │   ├── converter.py           # 时间戳文本→SRT
│   │   └── transcriber.py         # TurboScribe 自动化
│   ├── video/
│   │   ├── pipeline.py            # 视频片段拼接
│   │   ├── subtitle_renderer.py   # 字幕叠加 (Pillow+MoviePy)
│   │   └── watermark.py           # 水印 (FFmpeg drawtext)
│   └── pipeline/
│       └── stage.py               # Stage 枚举 (PipelineStage)
├── prompts/
│   ├── theme_compiler.txt         # 内核编译 Prompt
│   └── novel_prompt.txt           # 小说创作 Prompt
├── assets/                        # 素材 (用户提供)
├── .env.example                   # 配置模板
├── pyproject.toml                 # 项目元数据
└── README.md
```

---

## 设计原则

### 依赖注入
所有服务类通过构造函数接收 `Settings` 和 `PathConfig`，无全局单例，便于测试和替换。

### 惰性路径
`PathConfig` 只在管线阶段实际执行时创建所需目录，而非启动时一次性创建全部。

### 关注点分离
每个包职责单一：`novel/` 不导入 `tts/`，`video/` 不导入 `novel/`。只有 `pipeline/` 和 CLI 跨包编排。

### 可测试性
核心逻辑不依赖外部服务，可注入 mock `Settings` 进行单元测试。

---

## 管线阶段

| 阶段 | CLI 子命令 | 说明 |
|------|-----------|------|
| `compile` | `novel` (内建) | 编译叙事内核 |
| `generate` | `novel` (内建) | 四阶段小说生成 |
| `tts` | `tts generate` | 文本→语音片段→合并 |
| `mix-bgm` | `tts mix` | 语音+BGM 混合 |
| `transcribe` | `srt` | TurboScribe 转录→SRT |
| `make-video` | `video assemble` | 视频片段拼接 |
| `subtitle` | `video subtitle` | 字幕叠加 |
| `watermark` | `video watermark` | FFmpeg 水印 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| LLM | DeepSeek V3 (火山引擎 ARK API) |
| TTS | 腾讯云语音合成 |
| 字幕转录 | TurboScribe.ai (DrissionPage 自动化) |
| 视频处理 | MoviePy + Pillow + FFmpeg |
| 音频处理 | pydub |
| 配置管理 | pydantic-settings |
| CLI | argparse (stdlib) |

---

## License

MIT
