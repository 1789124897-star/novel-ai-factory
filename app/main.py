#!/usr/bin/env python3
"""novel-ai-factory CLI — AI 小说生成管线。

用法：
    novel-ai-factory run --theme "仵作之死"        # 全流程
    novel-ai-factory novel --theme "铁甲怪人"       # 仅生成小说
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  bootstrap
# ═══════════════════════════════════════════════════════════════

def _bootstrap(theme: str = ""):
    """创建 Settings + PathConfig + 日志配置。每次 CLI 调用执行一次。"""
    from app.core.config import settings
    from app.core.logging import setup_logging
    from app.core.paths import PathConfig

    setup_logging(settings)
    paths = PathConfig.from_settings(settings, theme=theme)
    return settings, paths


# ═══════════════════════════════════════════════════════════════
#  子命令处理器
# ═══════════════════════════════════════════════════════════════

def _cmd_novel(args: argparse.Namespace) -> int:
    """``novel`` 子命令 — 编译内核 + 生成小说。"""
    from app.services import novel_service
    from app.services.novel_gen_service import NovelGenerator
    from app.services.novel_gen_service import NovelPrompt

    theme = args.theme or ""
    settings, paths = _bootstrap(theme)

    # 1. 编译内核
    print(f"\n{'='*60}")
    print(f"  🔮 编译叙事内核：{theme}")
    print(f"{'='*60}")
    data = novel_service.compile_kernel(theme)
    kernel = data["kernel"]
    print(f"  ✓ 内核已保存 → {data['kernel_path']}")

    # 2. 生成小说
    print(f"\n{'='*60}")
    print(f"  📖 四阶段小说生成 (起·承·转·合)")
    print(f"{'='*60}")
    prompt = NovelPrompt(theme, paths, kernel)
    generator = NovelGenerator(prompt, paths, settings)
    novel_text = generator.generate_novel(target_words=args.target_words)
    paths.novel_output.write_text(novel_text, encoding="utf-8")
    print(f"\n  ✅ 小说完成 — {len(novel_text)} 字 → {paths.novel_output}")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """``run`` 子命令 — 全流程端到端，一次 bootstrap。"""
    from app.core.config import settings
    from app.core.logging import setup_logging
    from app.core.paths import PathConfig
    from app.services import novel_service
    from app.services.novel_gen_service import NovelGenerator
    from app.services.novel_gen_service import NovelPrompt
    from app.pipeline.stage import Stage

    theme = args.theme or ""

    setup_logging(settings)
    paths = PathConfig.from_settings(settings, theme=theme)

    if args.stages:
        try:
            requested = [Stage(s.strip()) for s in args.stages.split(",")]
        except ValueError as e:
            print(f"❌ 无效阶段名: {e}", file=sys.stderr)
            print(f"   可用阶段: {', '.join(s.value for s in Stage)}", file=sys.stderr)
            return 1
        stages = requested
    else:
        stages = Stage.full_pipeline()

    skip = set(args.skip or [])
    stages = [s for s in stages if s.value not in skip]
    stage_set = set(stages)

    if not stages:
        print("⚠️  没有要执行的阶段", file=sys.stderr)
        return 0

    print(f"\n{'='*60}")
    print(f"  🚀 小说AI工厂 · 全流程管道")
    print(f"  主题: {theme}")
    print(f"  {' → '.join(s.value for s in stages)}")
    print(f"{'='*60}")

    kernel = None

    if Stage.COMPILE in stage_set:
        print(f"\n  🔮 编译叙事内核 …")
        data = novel_service.compile_kernel(theme)
        kernel = data["kernel"]
        print(f"  ✓ 内核已保存 → {data['kernel_path']}")

    if Stage.GENERATE in stage_set:
        if kernel is None:
            if paths.kernel_file.exists():
                kernel = paths.kernel_file.read_text(encoding="utf-8")
            else:
                print("❌ 需要先编译叙事内核 (--stages compile)", file=sys.stderr)
                return 1

        print(f"\n  📖 四阶段小说生成 (起·承·转·合)")
        prompt = NovelPrompt(theme, paths, kernel)
        generator = NovelGenerator(prompt, paths, settings)
        novel_text = generator.generate_novel(target_words=getattr(args, "target_words", 8000))
        paths.novel_output.write_text(novel_text, encoding="utf-8")
        print(f"  ✅ 小说完成 — {len(novel_text)} 字 → {paths.novel_output}")

    print(f"\n{'='*60}")
    print(f"  🎉 管道执行完毕！")
    print(f"{'='*60}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="novel-ai-factory",
        description="AI 小说工厂 — 从主题到小说的生成管线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  novel-ai-factory novel -t "仵作之死"        仅生成小说
  novel-ai-factory run -t "铁甲怪人"          运行全流程
""",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ── novel ────────────────────────────────────────────────
    novel_parser = subparsers.add_parser("novel", help="生成小说（编译内核 + 四阶段生成）")
    novel_parser.add_argument("--theme", "-t", help="故事主题")
    novel_parser.add_argument("--target-words", type=int, default=8000, help="目标字数 (默认 8000)")

    # ── run ──────────────────────────────────────────────────
    run_parser = subparsers.add_parser("run", help="运行完整管道")
    run_parser.add_argument("--theme", "-t", help="故事主题")
    run_parser.add_argument("--stages", help="指定阶段，逗号分隔 (默认全部)")
    run_parser.add_argument("--target-words", type=int, default=8000, help="目标字数 (默认 8000)")
    run_parser.add_argument("--skip", nargs="*", help="跳过的阶段名")

    return parser


# ═══════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════

_HANDLERS = {
    "novel": _cmd_novel,
    "run": _cmd_run,
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler = _HANDLERS.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print("\n👋 已取消")
        return 130
    except Exception:
        logger.exception("'%s' 命令发生未处理异常", args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())
