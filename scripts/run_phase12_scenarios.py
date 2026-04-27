from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import yaml

from zeroclaw_reachy_companion.config import AppConfig
from zeroclaw_reachy_companion.runtime.text_chat_loop import ReachyCompanionRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Run Reachy Phase 1/2 scenario suite")
    parser.add_argument("--manifest", default="scenarios/reachy_phase12.yaml")
    parser.add_argument("--reachy-mode", choices=["dry_run", "sim", "real"], default="dry_run")
    parser.add_argument("--llm", choices=["mock", "auto", "ollama"], default="mock")
    parser.add_argument("--local-llm-url", default="http://127.0.0.1:1234/v1")
    parser.add_argument("--local-llm-model", default="qwen/qwen3-vl-8b")
    parser.add_argument("--tool-mode", choices=["json", "native"], default="native")
    return parser


async def main() -> None:
    args = build_parser().parse_args()
    manifest = yaml.safe_load(Path(args.manifest).read_text(encoding="utf-8"))
    config = AppConfig(
        reachy_mode=args.reachy_mode,
        llm_backend=args.llm,
        local_llm_url=args.local_llm_url,
        local_llm_model=args.local_llm_model,
        tool_mode=args.tool_mode,
    )
    runtime = await ReachyCompanionRuntime.create(config)
    try:
        for section in ("simple_cases", "complex_cases"):
            print(f"\n== {section} ==")
            for case in manifest.get(section, []):
                print(f"\n[{case['id']}]")
                turns = case.get("turns") or [case]
                for turn in turns:
                    print(f"User> {turn['prompt']}")
                    result = await runtime.handle_text(turn["prompt"], announce=True)
                    actual = [item.call.name for item in result.tools]
                    expected = turn.get("companion_expected_tools")
                    if expected:
                        status = "ok" if actual == expected else f"expected {expected}, got {actual}"
                        print(f"Check> {status}")
    finally:
        await runtime.close()


if __name__ == "__main__":
    asyncio.run(main())

