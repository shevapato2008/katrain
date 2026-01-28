#!/usr/bin/env python
"""Test script to verify Qwen LLM translation works with DASHSCOPE_API_KEY.

Reproduces the exact same calling path used in translator.py:
  OpenAI SDK -> DashScope compatible API -> qwen-mt-turbo

Usage:
    python scripts/test_qwen_translation.py
"""

import os
import sys

def main():
    # 1. Check API key
    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("ERROR: DASHSCOPE_API_KEY not set in environment")
        sys.exit(1)
    print(f"DASHSCOPE_API_KEY: set ({api_key[:8]}...)")

    # 2. Check openai package
    try:
        from openai import OpenAI
        print("openai package: installed")
    except ImportError:
        print("ERROR: openai package not installed. Run: pip install openai>=1.0.0")
        sys.exit(1)

    # 3. Config (same defaults as translator.py)
    base_url = os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.environ.get("LLM_MODEL", "qwen-mt-turbo")
    print(f"base_url: {base_url}")
    print(f"model: {model}")
    print()

    client = OpenAI(api_key=api_key, base_url=base_url)

    # 4. Test cases — same prompts as translator.py
    tests = [
        {
            "desc": "Player name: Chinese -> English",
            "prompt": (
                "Translate this Go player name to English:\n"
                "Name: 柯洁\n\n"
                "Follow these conventions:\n"
                "- Chinese names to English: Use pinyin without tones (e.g., 柯洁 → Ke Jie)\n\n"
                "Return ONLY the translated name, nothing else."
            ),
            "expected": "Ke Jie",
        },
        {
            "desc": "Player name: Chinese -> Japanese",
            "prompt": (
                "Translate this Go player name to Japanese:\n"
                "Name: 柯洁\n\n"
                "Follow these conventions:\n"
                "- Chinese names to Japanese: Use katakana with middle dot (e.g., 柯洁 → カ・ケツ)\n\n"
                "Return ONLY the translated name, nothing else."
            ),
            "expected": "カ・ケツ",
        },
        {
            "desc": "Tournament name: Chinese -> English",
            "prompt": (
                "Translate this Go tournament name to English:\n"
                "Name: 第52期天元战\n\n"
                "Guidelines for English:\n"
                "- Use official English names when known (棋聖戦 → Kisei, 天元战 → Tengen)\n"
                "- For editions: 第52期 → 52nd, 27届 → 27th\n"
                "- Translate 战/杯/赛 as Tournament/Cup/Match\n\n"
                "Return ONLY the translated name, nothing else."
            ),
            "expected": "52nd Tengen",
        },
    ]

    passed = 0
    failed = 0

    for i, t in enumerate(tests, 1):
        print(f"--- Test {i}: {t['desc']} ---")
        print(f"  Prompt: {t['prompt'][:80]}...")
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=100,
                messages=[{"role": "user", "content": t["prompt"]}],
            )
            if response.choices:
                result = response.choices[0].message.content.strip()
                status = "PASS" if t["expected"].lower() in result.lower() else "CHECK"
                print(f"  Result: {result}")
                print(f"  Expected: {t['expected']}")
                print(f"  [{status}]")
                passed += 1
            else:
                print(f"  [FAIL] Empty response")
                failed += 1
        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
            failed += 1
        print()

    print(f"=== Results: {passed} passed, {failed} failed ===")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
