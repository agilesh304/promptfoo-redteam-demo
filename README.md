# AcmeShop Red Team Demo — Promptfoo

A working demonstration of **LLM evaluation** and **automated red teaming** using [Promptfoo](https://www.promptfoo.dev/), built for the AI Security module kickoff.

## What This Does

| Step | What Happens |
|---|---|
| Target app | A Flask-style customer support chatbot (AcmeShop) with two prompt versions |
| v1 (weak) | System prompt contains embedded secrets and minimal guardrails |
| v2 (hardened) | Secrets removed, explicit refusal templates, instruction hierarchy |
| Baseline eval | 25 test cases checking normal behaviour, tone, and off-topic refusals |
| Red team | Automated attack generation across 15+ plugin categories + 5 hand-crafted attacks |
| Reports | HTML report via `promptfoo view`, before/after table in `reports/SUMMARY.md` |

---

## Prerequisites

- **Node.js 18+** (tested on 22.14.0)
- **Python 3.10+** (tested on 3.13)
- A **Groq API key** (or OpenAI / Anthropic / Gemini)

```bash
# Verify
node --version   # >= 18
python --version # >= 3.10
```

---

## Setup

```bash
# 1. Clone / enter the project
cd promptfoo-redteam-demo

# 2. Copy and fill in your API key
copy .env.example .env
# Edit .env and set GROQ_API_KEY (or another key)

# 3. Install Python dependency (Groq SDK)
python -m pip install groq

# 4. Generate data
python scripts/prepare_data.py
python scripts/make_synthetic_customers.py
```

---

## Running the Target App

```bash
# Terminal 1 — start v1 (weak/vulnerable)
set PROMPT_VERSION=v1
python app/server.py

# Terminal 1 — OR start v2 (hardened)
set PROMPT_VERSION=v2
python app/server.py
```

Test it manually:
```bash
# PowerShell
Invoke-RestMethod -Uri "http://localhost:5001/chat" -Method POST `
  -ContentType "application/json" `
  -Body '{"message": "How do I return an item?"}' | ConvertTo-Json
```

---

## Running the Baseline Evaluation

```bash
# Server must be running first (see above)
set GROQ_API_KEY=your-key-here
npx promptfoo@0.103.0 eval -c evals/promptfooconfig.yaml
```

View results in browser:
```bash
npx promptfoo@0.103.0 view
```

---

## Running the Red Team

```bash
# Step 1: Generate attack test cases for v1
npx promptfoo@0.103.0 redteam run -c redteam/redteam_v1.yaml

# Step 2: Switch server to v2 (hardened)
#   Stop server, set PROMPT_VERSION=v2, restart server

# Step 3: Run same attacks against v2
npx promptfoo@0.103.0 redteam run -c redteam/redteam_v2.yaml

# View the red team report
npx promptfoo@0.103.0 redteam report
```

---

## Generating the Comparison Report

```bash
# Save results first (if not already saved)
# npx promptfoo@0.103.0 redteam run -c redteam/redteam_v1.yaml --output reports/results_v1.json
# npx promptfoo@0.103.0 redteam run -c redteam/redteam_v2.yaml --output reports/results_v2.json

python scripts/compare.py
# Output: reports/SUMMARY.md
```

---

## Project Structure

```
promptfoo-redteam-demo/
├── app/
│   ├── server.py           # Target HTTP app (POST /chat)
│   └── prompts/
│       ├── system_v1.txt   # Weak prompt (has canary secrets)
│       └── system_v2.txt   # Hardened prompt (no secrets, guardrails)
├── data/
│   ├── faq.jsonl           # 25 support Q&A pairs
│   └── customers.json      # 20 synthetic customer records
├── evals/
│   ├── promptfooconfig.yaml
│   └── tests.yaml          # 25 baseline test cases
├── redteam/
│   ├── redteam_v1.yaml
│   └── redteam_v2.yaml
├── reports/
│   └── SUMMARY.md          # Before/after comparison
├── scripts/
│   ├── prepare_data.py
│   ├── make_synthetic_customers.py
│   └── compare.py
├── .env                    # Your API keys (never commit!)
├── .env.example            # Template
└── README.md
```

---

## Approximate Cost & Runtime

| Task | Time | Groq Cost |
|---|---|---|
| Data prep | ~5s | Free |
| Baseline eval (25 tests) | ~2 min | ~$0.01 |
| Red team v1 (4 tests × 15 plugins + 5 manual = ~65 cases) | ~5–10 min | ~$0.05 |
| Red team v2 | ~5–10 min | ~$0.05 |
| **Total** | **~20 min** | **~$0.11** |

---

## Canary Secrets (v1 only)

These are **fake** strings planted to detect leakage:
- `CANARY-API-KEY-7f3a9` — fake internal API key
- `STAFF50` — fake staff discount code
- `MGRAPPROVAL-2024` — fake manager approval code

They appear only in `system_v1.txt`. `system_v2.txt` has none of them.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `model_not_found` | Check `TARGET_MODEL` in `.env` matches an available Groq model |
| Server crashes with Unicode error | Run `python -u app/server.py` or upgrade Python |
| promptfoo engine warning | Use `npx promptfoo@0.103.0` (compatible with Node 22.14) |
| Red team hangs | Lower `numTests` to 2 in the yaml, or run with `--no-cache` |

See `NOTES.md` for version pinning decisions and known issues.
