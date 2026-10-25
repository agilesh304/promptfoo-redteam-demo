"""
compare.py
Reads redteam result JSON files for v1 and v2 and prints a before/after
comparison table, then writes reports/SUMMARY.md.

Usage:
    python scripts/compare.py

Expects:
    reports/results_v1.json   (saved from npx promptfoo@latest redteam run --output)
    reports/results_v2.json
"""

import json
import os
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"

V1_FILE = REPORTS / "results_v1.json"
V2_FILE = REPORTS / "results_v2.json"
SUMMARY_FILE = REPORTS / "SUMMARY.md"


def load_results(path: Path) -> list[dict]:
    """Load promptfoo redteam results JSON."""
    if not path.exists():
        print(f"[warn] {path} not found.")
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Promptfoo result structure varies by version; handle both list and dict
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        res = data.get("results")
        if isinstance(res, list):
            return res
        if isinstance(res, dict) and isinstance(res.get("results"), list):
            return res["results"]
        for key in ("testResults", "tests"):
            if key in data and isinstance(data[key], list):
                return data[key]
    return []


def plugin_from_test(test: dict) -> str:
    """Extract plugin/category name from a test result object."""
    # Try metadata first
    meta = test.get("metadata", {}) or {}
    plugin = meta.get("pluginId") or meta.get("plugin") or ""
    if plugin:
        return plugin
    # Fall back to description
    desc = test.get("description", "") or ""
    return desc.split(":")[0] if ":" in desc else (desc[:30] if desc else "unknown")


def pass_rate(tests: list[dict]) -> tuple[int, int]:
    """Returns (passed, total)."""
    total = len(tests)
    passed = sum(1 for t in tests if t.get("success") or t.get("passed"))
    return passed, total


def group_by_plugin(tests: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in tests:
        groups[plugin_from_test(t)].append(t)
    return groups


def make_table(v1_groups: dict, v2_groups: dict) -> str:
    all_plugins = sorted(set(v1_groups) | set(v2_groups))
    lines = [
        "| Plugin / Category | v1 Pass | v1 Fail | v2 Pass | v2 Fail | Improvement |",
        "|---|---|---|---|---|---|",
    ]
    overall_v1_pass = overall_v1_total = overall_v2_pass = overall_v2_total = 0

    for plugin in all_plugins:
        v1t = v1_groups.get(plugin, [])
        v2t = v2_groups.get(plugin, [])
        v1p, v1tot = pass_rate(v1t)
        v2p, v2tot = pass_rate(v2t)
        overall_v1_pass += v1p
        overall_v1_total += v1tot
        overall_v2_pass += v2p
        overall_v2_total += v2tot

        v1pct = f"{v1p}/{v1tot} ({100*v1p//v1tot if v1tot else 0}%)"
        v2pct = f"{v2p}/{v2tot} ({100*v2p//v2tot if v2tot else 0}%)"
        v1fail = v1tot - v1p
        v2fail = v2tot - v2p
        delta = v2fail - v1fail
        icon = "✅" if delta < 0 else ("➖" if delta == 0 else "❌")
        improvement = f"{icon} {abs(delta)} fewer failures" if delta < 0 else (
            f"➖ No change" if delta == 0 else f"❌ {delta} more failures"
        )
        lines.append(f"| {plugin} | {v1pct} | {v1fail} | {v2pct} | {v2fail} | {improvement} |")

    # Overall row
    v1op = f"{overall_v1_pass}/{overall_v1_total} ({100*overall_v1_pass//overall_v1_total if overall_v1_total else 0}%)"
    v2op = f"{overall_v2_pass}/{overall_v2_total} ({100*overall_v2_pass//overall_v2_total if overall_v2_total else 0}%)"
    lines.append(f"| **OVERALL** | **{v1op}** | **{overall_v1_total-overall_v1_pass}** | **{v2op}** | **{overall_v2_total-overall_v2_pass}** | |")
    return "\n".join(lines)


def find_examples(v1_tests: list[dict], n: int = 3) -> list[dict]:
    """Find the most interesting failures (attacks that succeeded against v1)."""
    failures = [t for t in v1_tests if not (t.get("success") or t.get("passed"))]
    return failures[:n]


def main():
    v1_tests = load_results(V1_FILE)
    v2_tests = load_results(V2_FILE)

    if not v1_tests and not v2_tests:
        print("No result files found. Run red team first:")
        print("  npx promptfoo@latest redteam run -c redteam/redteam_v1.yaml --output reports/results_v1.json")
        print("  npx promptfoo@latest redteam run -c redteam/redteam_v2.yaml --output reports/results_v2.json")
        return

    v1_groups = group_by_plugin(v1_tests)
    v2_groups = group_by_plugin(v2_tests)
    table = make_table(v1_groups, v2_groups)

    print("\n=== Before/After Comparison ===")
    print(table)

    # Write SUMMARY.md
    examples = find_examples(v1_tests)
    example_sections = ""
    for i, ex in enumerate(examples, 1):
        prompt = ex.get("prompt", {})
        prompt_text = (
            prompt.get("raw") or prompt.get("display") or str(prompt)
        ) if isinstance(prompt, dict) else str(prompt)
        response = ex.get("response", {})
        response_text = (
            response.get("output") or response.get("text") or str(response)
        ) if isinstance(response, dict) else str(response)
        plugin = plugin_from_test(ex)
        example_sections += f"""
### Finding {i}: {plugin}

**Attack prompt:**
```
{prompt_text[:500]}
```

**Model response (v1):**
```
{response_text[:500]}
```

**Why this matters:** v1 did not adequately refuse this attack. v2 adds explicit refusal
instructions that block this category.
"""

    summary = f"""# AcmeShop Red Team — Summary Report

## Target
**Application:** AcmeShop Customer Support Chatbot  
**Method:** Promptfoo automated red teaming  
**Date:** Generated by compare.py  

## Results

{table}

## Top Findings (v1 Failures)
{example_sections if example_sections else "_No failures found — check result files._"}

## What Hardening (v2) Changed
1. **Secrets removed from prompt** — canary API key, STAFF50, and policy details moved out of the system prompt entirely; output filter blocks any accidental leakage.
2. **Explicit instruction hierarchy** — system prompt states that user messages cannot override rules; "I am the manager" claims are ignored.
3. **Strict scope enforcement** — explicit list of what the bot can and cannot discuss, with canned refusal templates.
4. **Input/output filtering** — server-side regex blocks canary strings from ever appearing in responses.

## Remaining Weaknesses
- Sophisticated multi-turn crescendo attacks may still partially succeed.
- The FAQ retrieval is keyword-based and may retrieve off-topic snippets.
- No rate limiting or authentication on the HTTP endpoint.

## Next Steps → AI Agentic Security Module
- Test agentic tool-use (function-calling, MCP) for privilege escalation.
- Explore multi-agent trust boundaries.
- Add authentication and input sanitization at the API gateway layer.
"""

    REPORTS.mkdir(exist_ok=True)
    SUMMARY_FILE.write_text(summary, encoding="utf-8")
    print(f"\nSUMMARY.md written to {SUMMARY_FILE}")


if __name__ == "__main__":
    main()
