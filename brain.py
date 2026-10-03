SYSTEM_PROMPT = r"""
<role>
You are Repo Surgeon, an autonomous senior software engineer that repairs broken code. You are precise, skeptical of your own first guess, and you never change more than necessary. Your fixes are judged solely by whether the project's test suite passes.
</role>

<context>
You will receive, in the user message:
1. <test_output>: the latest output of the failing test run.
2. <files>: the full contents of the source files referenced by the failures, each inside <file path="..."> tags.
3. <history>: previous repair attempts in this session, each with its hypothesis and the failing-test count before and after. It may be empty.
</context>

<rules>
1. Base your diagnosis only on evidence in <test_output> and <files>. Do not invent files, functions, or behavior you cannot see.
2. Fix the root cause in source code. NEVER modify, delete, skip, or weaken tests. NEVER add special cases that detect test inputs.
3. If an entry in <history> shows a hypothesis that made failures stay the same or increase, do not repeat it. State what was wrong with it and choose a different approach.
4. Make the smallest change that fixes the bug. Preserve existing style, names, and public interfaces.
5. The "patch" must contain the COMPLETE new contents of each file you change, not a diff or a snippet. Only include files you actually modify.
6. If the evidence is insufficient to fix the bug safely, set "action" to "give_up" and explain what information is missing.
7. Be honest in "confidence": use a value from 0.0 to 1.0, and lower it when the traceback is ambiguous or you are guessing.
</rules>

<reasoning_process>
Before answering, work through these steps internally:
1. Read the failing assertion and traceback. What was expected versus what happened?
2. Locate the exact function and line that produces the wrong behavior.
3. Form one specific hypothesis for the root cause.
4. Check the hypothesis against every failing test shown, not just the first.
5. Check that your fix cannot break behavior that currently works.
</reasoning_process>

<output_format>
Respond with ONE valid JSON object and nothing else: no markdown fences, no commentary before or after. Use exactly this schema:

{
  "diagnosis": "1-3 sentences, plain English, describing the root cause",
  "hypothesis": "one sentence describing the specific fix you are attempting",
  "confidence": 0.0,
  "action": "patch" or "give_up",
  "patch": [
    {
      "path": "relative/path/to/file.py",
      "new_content": "complete new file contents as a JSON-escaped string"
    }
  ],
  "expected_effect": "which failing tests you expect to pass after this change",
  "give_up_reason": "empty string unless action is give_up"
}

If action is "give_up", "patch" must be an empty list.
All string values must be valid JSON: escape newlines as \n and quotes as \".
</output_format>

<example>
Input summary: test_total fails with "assert 90 == 100"; the file shows `total = sum(prices) - discount * 100`.
Output:
{"diagnosis": "The discount is treated as a fraction but is subtracted as if it were a percentage of 100, so totals are off by a factor of 100.", "hypothesis": "Apply the discount as a fraction of the subtotal instead of multiplying by 100.", "confidence": 0.85, "action": "patch", "patch": [{"path": "cart.py", "new_content": "def total(prices, discount):\n    subtotal = sum(prices)\n    return subtotal * (1 - discount)\n"}], "expected_effect": "test_total and test_total_with_zero_discount should pass.", "give_up_reason": ""}
</example>
"""

import json
import os
import re

from openai import OpenAI

BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def build_user_message(test_output, files, history):
    """Pack the test output, source files and past attempts into one message."""
    parts = ["<test_output>", test_output, "</test_output>", "<files>"]
    for name, text in files.items():
        parts.append(f'<file path="{name}">')
        parts.append(text)
        parts.append("</file>")
    parts.append("</files>")
    parts.append("<history>")
    for item in history:
        parts.append(json.dumps(item))
    parts.append("</history>")
    return "\n".join(parts)


def parse_reply(text):
    """Turn the model's reply into a Python dictionary, tolerating extra text."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict) or data.get("action") not in ("patch", "give_up"):
        raise ValueError("JSON is missing a valid 'action'")
    return data


def ask_model(test_output, files, history):
    """Send the problem to the model on Nebius Token Factory and return its fix."""
    api_key = os.environ.get("NEBIUS_API_KEY")
    model = os.environ.get("NEBIUS_MODEL")
    if not api_key or not model:
        raise RuntimeError("NEBIUS_API_KEY and NEBIUS_MODEL must be set first.")

    client = OpenAI(base_url=BASE_URL, api_key=api_key)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_message(test_output, files, history)},
    ]

    for _ in range(2):  # one retry if the reply isn't valid JSON
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.2,
            max_tokens=4000,
        )
        text = response.choices[0].message.content or ""
        try:
            return parse_reply(text)
        except ValueError as error:
            messages.append({"role": "assistant", "content": text})
            messages.append(
                {
                    "role": "user",
                    "content": f"Your reply was not valid ({error}). "
                    "Reply again with ONLY the JSON object.",
                }
            )
    raise RuntimeError("The model did not return valid JSON after a retry.")