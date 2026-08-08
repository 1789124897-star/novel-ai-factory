"""叙事内核编译器 — 将一句话主题转化为结构化 JSON 锚点。"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import requests

if TYPE_CHECKING:
    from ..core.config import Settings
    from ..core.paths import PathConfig

logger = logging.getLogger(__name__)


class ThemeCompiler:
    """通过 LLM 将故事主题编译为*叙事内核*。

    内核是不可变锚点，所有后续生成阶段必须遵循——定义象征、核心事件、人物动机和预言。

    ``compile()`` 返回解析后的 ``dict``。用 ``kernel_to_prompt_text()`` 转回可读中文文本用于 prompt 注入。
    """

    def __init__(self, settings: "Settings", paths: "PathConfig"):
        self.settings = settings
        self.paths = paths
        self._session = requests.Session()

    # ── 上下文管理器 ─────────────────────────────────

    def __enter__(self) -> "ThemeCompiler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self) -> None:
        self._session.close()

    # ── 公开 API ──────────────────────────────────────

    def compile(self, theme: str, *, timeout: int = 120) -> dict:
        """将 *theme* 编译为结构化叙事内核 dict。

        Returns:
            解析后的内核 dict，key: theme, physical_attributes,
            cultural_metaphors, operability, core_event, heroine_entry_reason,
            male1_motive, male2_motive, prophecy。

        Raises:
            FileNotFoundError: Prompt 模板不存在。
            ValueError: Prompt 模板为空、花括号不匹配，或 LLM 返回非 JSON。
            requests.RequestException: LLM API 调用失败。
        """
        prompt_path: Path = self.paths.theme_compiler_prompt
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt 模板未找到: {prompt_path}")

        base_prompt = prompt_path.read_text(encoding="utf-8").strip()
        if not base_prompt:
            raise ValueError(f"Prompt 模板为空: {prompt_path}")

        try:
            final_prompt = base_prompt.format(theme=theme)
        except KeyError as e:
            raise ValueError(f"模板变量不匹配 — 缺失: {e}") from e

        payload = {
            "model": self.settings.DEEPSEEK_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是小说主题与叙事内核设计专家。严格按照用户提供的三步流程分析，"
                        "最终输出一个 JSON 对象，包含以下字段：\n"
                        "- theme: 主题名称\n"
                        "- physical_attributes: 物理属性列表\n"
                        "- cultural_metaphors: {{\"positive\": [...], \"negative\": [...]}}\n"
                        "- operability: 可操作性行为列表\n"
                        "- core_event: {{\"type\": 事件类型(A/B/C/D), \"description\": 描述, "
                        "\"victim\": 死者, \"perpetrator\": 发起者, \"location\": 空间, \"evidence\": 物证}}\n"
                        "- heroine_entry_reason: 女主进入原因\n"
                        "- male1_motive: 男1动机\n"
                        "- male2_motive: 男2动机\n"
                        "- prophecy: 闭环预言"
                    ),
                },
                {"role": "user", "content": final_prompt},
            ],
            "temperature": self.settings.DEEPSEEK_TEMPERATURE,
            "top_p": self.settings.DEEPSEEK_TOP_P,
            "max_tokens": self.settings.DEEPSEEK_MAX_TOKENS,
            "response_format": {"type": "json_object"},
        }

        logger.info("正在编译叙事内核，主题：%s", theme)
        raw = self._call_api(payload, timeout=timeout)
        return self._parse_json(raw)

    def save_kernel(self, kernel: dict, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(kernel, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("内核已保存 → %s", output_path)
        return output_path

    @staticmethod
    def kernel_to_prompt_text(kernel: dict) -> str:
        """将结构化内核 dict 转为可读文本，供 LLM prompt 注入。

        ``NovelPrompt`` 使用此方法锚定每个生成阶段。
        """
        ce = kernel.get("core_event", {})
        cm = kernel.get("cultural_metaphors", {})

        parts = [
            f"主题：{kernel.get('theme', '')}",
            "",
            "【物理想象】",
            " · ".join(kernel.get("physical_attributes", [])),
            "",
            "【文化象征】",
            f"  正面：{' · '.join(cm.get('positive', []))}",
            f"  负面：{' · '.join(cm.get('negative', []))}",
            "",
            "【可操作性】",
            " · ".join(kernel.get("operability", [])),
            "",
            "【核心事件】",
            f"  类型：{ce.get('type', '')}",
            f"  描述：{ce.get('description', '')}",
            f"  死者/受害者：{ce.get('victim', '')}",
            f"  主动发起者：{ce.get('perpetrator', '')}",
            f"  物理空间：{ce.get('location', '')}",
            f"  核心物证：{ce.get('evidence', '')}",
            "",
            "【人物动机】",
            f"  女主进入原因：{kernel.get('heroine_entry_reason', '')}",
            f"  男1动机（美化/修复）：{kernel.get('male1_motive', '')}",
            f"  男2动机（揭露/破坏）：{kernel.get('male2_motive', '')}",
            "",
            "【闭环预言】",
            kernel.get("prophecy", ""),
        ]
        return "\n".join(parts)

    # ── 内部方法 ────────────────────────────────────────

    def _call_api(self, payload: dict, *, timeout: int) -> str:
        try:
            resp = self._session.post(
                url=self.settings.DEEPSEEK_BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            return self._extract_content(resp.json())
        except requests.RequestException:
            logger.exception("叙事内核编译失败")
            raise

    @staticmethod
    def _extract_content(data: dict) -> str:
        """解析 OpenAI 兼容的 chat completion 响应。"""
        try:
            choices = data.get("choices")
            if choices and isinstance(choices, list):
                choice = choices[0]
                msg = choice.get("message")
                if msg and "content" in msg:
                    return msg["content"].strip()
                if "text" in choice:
                    return choice["text"].strip()
            if "content" in data:
                return data["content"].strip()
        except Exception:
            logger.error("API 响应内容解析失败")

        logger.error("无法识别的 API 响应结构: %s", data)
        raise ValueError(f"无法识别的 API 响应格式: {data}")

    @staticmethod
    def _parse_json(raw: str) -> dict:
        """从 LLM 输出中提取 JSON 对象。

        尝试顺序：直接解析 → markdown 代码块提取 → 清洗兜底。
        """
        raw = raw.strip()
        # 直接解析
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 尝试从 ```json ... ``` 或 ``` ... ``` 中提取
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 兜底方案: 尝试查找 { ... } 块
        m = re.search(r"\{[\s\S]*\}", raw)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(
            f"LLM 未返回有效 JSON。原始响应（前 500 字符）:\n{raw[:500]}"
        )
