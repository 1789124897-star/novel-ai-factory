# novel-ai-factory · 小说 AI 工厂

**从一句话主题,到带字幕的完整视频,全自动生成。**

> Python 3.9+ · FastAPI · DeepSeek · edge-tts · MoviePy

---

## 项目概述

`novel-ai-factory` 是一个 AI 驱动的内容生产管线,覆盖从创意到成片的完整链路:

```
主题 → 叙事内核 → 四阶段小说生成 → TTS 语音合成 → 词级时间戳字幕
    → 背景视频拼接 → 字幕叠加 → 水印 → BGM 混音 → 成品视频
```

Web 界面一键操作,后台异步执行,进度实时推送。

## 核心特性

- **叙事内核编译** — LLM 将一句话主题拆解为结构化叙事内核
- **四阶段小说生成** — 起·承·转·合分阶段创作,字数预算动态控制
- **可编排管线** — Stage 枚举定义管线阶段,CLI 可按需组合与跳过阶段
- **智能 TTS + 字幕** — edge-tts 流式合成,基于词级时间戳逐句生成 SRT
- **全自动视频** — 背景片段拼接 + 字幕叠加 + 半透明水印 + BGM 混音
- **轻量异步任务** — 自研任务管理器(threading + Lock),SSE 实时推送进度
- **双入口** — Web 界面 + CLI 命令行

---

## 快速开始

### 1. 环境要求

- Python 3.9+
- FFmpeg(MoviePy / pydub 依赖,需在系统 PATH 中)

### 2. 安装

```bash
git clone https://github.com/1789124897-star/novel-ai-factory.git
cd novel-ai-factory
pip install -r requirements.txt
```

### 3. 配置

```bash
cp .env.example .env
# 编辑 .env,填入 DeepSeek API 密钥
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥(必填) | — |
| `DEEPSEEK_BASE_URL` | API 地址 | `https://api.deepseek.com/v1/chat/completions` |
| `DEEPSEEK_MODEL` | 模型名 | `deepseek-v4-pro` |
| `DEEPSEEK_TEMPERATURE` | 采样温度 | `0.85` |
| `DEEPSEEK_MAX_TOKENS` | 单次生成最大 token | `12000` |
| `OUTPUT_DIR` | 输出根目录 | `output` |
| `BGM_VOLUME_RATIO` | BGM 混音音量比 | `0.3` |
| `WATERMARK_FONT` | 水印/字幕字体 | `assets/fonts/LXGWWenKai-Regular.ttf` |

### 4. 准备素材

```bash
assets/
├── videos/          # 背景视频片段 (.mp4)
├── bgm/bgm.mp3      # 背景音乐
└── fonts/           # 字体文件 (.ttf)
```

### 5. 启动

**Web 模式(推荐):**

```bash
uvicorn app.server:app --reload
# 打开 http://localhost:8000
```

**CLI 模式:**

```bash
# 仅生成小说（编译内核 + 四阶段生成）
novel-ai-factory novel -t "仵作之死"

# 运行完整管线（当前含内核编译 + 小说生成阶段）
novel-ai-factory run -t "铁甲怪人"

# 指定阶段运行
novel-ai-factory run -t "铁甲怪人" --stages compile,generate

# 跳过指定阶段
novel-ai-factory run -t "铁甲怪人" --skip generate
```

---

## 项目结构

```
novel-ai-factory/
├── app/
│   ├── main.py                    # CLI 入口
│   ├── server.py                  # Web 入口 (FastAPI)
│   ├── api/routes/                # 路由层 (novel / tts / video / pipeline)
│   ├── core/
│   │   ├── config.py              # Pydantic Settings 统一配置
│   │   ├── paths.py               # PathConfig 集中路径管理
│   │   └── logging.py             # 日志配置
│   ├── pipeline/
│   │   └── stage.py               # 管线阶段枚举 (Stage)
│   ├── services/                  # 服务层 (业务逻辑)
│   │   ├── novel_service.py       # 叙事内核编译
│   │   ├── novel_gen_service.py   # 四阶段小说生成
│   │   ├── tts_service.py         # TTS 合成 + SRT 生成
│   │   ├── video_service.py       # 视频任务编排与路径解析
│   │   └── task_manager.py        # 轻量异步任务管理器
│   ├── tasks/                     # 任务层 (后台执行入口)
│   ├── schemas/                   # Pydantic 请求/响应模型
│   └── video/
│       ├── pipeline.py            # 背景视频拼接
│       ├── subtitle_renderer.py   # 字幕渲染 (Pillow + MoviePy)
│       └── watermark.py           # 水印叠加
├── prompts/                       # 提示词模板
├── static/                        # 前端页面 (HTML/CSS/JS)
├── assets/                        # 素材 (背景视频 / BGM / 字体)
├── .env.example                   # 配置模板
└── requirements.txt
```

---

## 技术栈

| 层 | 技术 |
|----|------|
| Web 框架 | FastAPI + Uvicorn |
| LLM | DeepSeek API(OpenAI 兼容协议,JSON 结构化输出) |
| TTS | edge-tts(流式合成 + 词级时间戳) |
| 视频处理 | MoviePy + Pillow + FFmpeg |
| 音频处理 | pydub |
| 异步任务 | threading + Lock 自研任务管理器,SSE 进度推送 |
| 配置管理 | Pydantic Settings |

---

## 设计要点

- **四层架构** — 路由 / 服务 / 任务 / 核心各司其职,API 层保持薄路由,业务逻辑统一下沉服务层
- **轻量级优先** — 单机内容生成场景不引入 Celery 等重依赖,以 threading + Lock 实现任务注册、状态读写与异常兜底
- **单一数据源** — 配置(Settings)、路径(PathConfig)、任务号(TaskManager)各自唯一出处
- **资源显式释放** — MoviePy 音视频资源用后即 close,避免文件句柄泄漏

---

## License

MIT
