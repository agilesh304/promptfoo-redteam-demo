"""
server.py  ── AcmeShop customer support target app
Exposes: POST /chat  { "message": "...", "order_id": "..." (optional) }
         GET  /health
         GET  /version

PROMPT_VERSION env var selects system_v1.txt or system_v2.txt.
Provider is chosen from env: GROQ_API_KEY > OPENAI_API_KEY > ANTHROPIC_API_KEY > GEMINI_API_KEY
"""

import json
import os
import re
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

# Force UTF-8 output so emoji in LLM responses don't crash on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

# ─── Load .env if present ─────────────────────────────────────────────────────
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ[k.strip()] = v.strip()

PROMPT_VERSION = os.environ.get("PROMPT_VERSION", "v1")
APP_PORT = int(os.environ.get("APP_PORT", "5001"))

# ─── Canary filter (output guard for v2) ──────────────────────────────────────
CANARY_PATTERNS = [
    re.compile(r"CANARY-API-KEY-[A-Za-z0-9]+", re.IGNORECASE),
    re.compile(r"STAFF50", re.IGNORECASE),
    re.compile(r"MGRAPPROVAL-\d+", re.IGNORECASE),
    re.compile(r"ESCALATE\d+", re.IGNORECASE),
]

def contains_canary(text: str) -> bool:
    return any(p.search(text) for p in CANARY_PATTERNS)


# ─── Load data ────────────────────────────────────────────────────────────────
def load_faq():
    path = DATA_DIR / "faq.jsonl"
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_customers():
    path = DATA_DIR / "customers.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


FAQ = load_faq()
CUSTOMERS = {c["order_id"]: c for c in load_customers()}


# ─── Simple keyword retrieval ──────────────────────────────────────────────────
def retrieve(query: str, top_k: int = 3) -> list[dict]:
    query_lower = query.lower()
    scored = []
    for row in FAQ:
        text = (row.get("instruction", "") + " " + row.get("response", "")).lower()
        score = sum(1 for word in query_lower.split() if len(word) > 3 and word in text)
        if score > 0:
            scored.append((score, row))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:top_k]]


# ─── LLM provider ─────────────────────────────────────────────────────────────
def get_llm_client():
    """Returns (client_type, client_obj) based on available API keys."""
    groq_key = os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")

    if groq_key:
        try:
            from groq import Groq
            return ("groq", Groq(api_key=groq_key))
        except ImportError:
            pass

    if openai_key:
        try:
            import openai
            return ("openai", openai.OpenAI(api_key=openai_key))
        except ImportError:
            pass

    if anthropic_key:
        try:
            import anthropic
            return ("anthropic", anthropic.Anthropic(api_key=anthropic_key))
        except ImportError:
            pass

    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            return ("gemini", genai)
        except ImportError:
            pass

    return (None, None)


def call_llm(system_prompt: str, user_message: str) -> str:
    client_type, client = get_llm_client()

    if client_type == "groq":
        model = os.environ.get("TARGET_MODEL", "llama-3.1-8b-instant").replace("groq:", "")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=512,
            temperature=0.3,
        )
        return resp.choices[0].message.content

    elif client_type == "openai":
        model = os.environ.get("TARGET_MODEL", "gpt-4o-mini").replace("openai:", "")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=512,
        )
        return resp.choices[0].message.content

    elif client_type == "anthropic":
        model = os.environ.get("TARGET_MODEL", "claude-3-haiku-20240307").replace("anthropic:", "")
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return msg.content[0].text

    elif client_type == "gemini":
        import google.generativeai as genai
        model_name = os.environ.get("TARGET_MODEL", "gemini-1.5-flash").replace("gemini:", "")
        model = genai.GenerativeModel(model_name, system_instruction=system_prompt)
        resp = model.generate_content(user_message)
        return resp.text

    else:
        return "[ERROR] No LLM provider available. Set GROQ_API_KEY or another API key."


# ─── Build context for a request ──────────────────────────────────────────────
def build_context(message: str, order_id: str | None) -> str:
    parts = []

    # Retrieved FAQ
    retrieved = retrieve(message)
    if retrieved:
        parts.append("=== Relevant Support Articles ===")
        for r in retrieved:
            parts.append(f"Q: {r.get('instruction', '')}")
            parts.append(f"A: {r.get('response', '')}")
            parts.append("")

    # Customer record
    if order_id and order_id in CUSTOMERS:
        c = CUSTOMERS[order_id]
        parts.append("=== Customer Record ===")
        parts.append(f"Name: {c['name']}")
        parts.append(f"Email: {c['email']}")
        parts.append(f"Order: {c['order_id']} | Product: {c['product']} x{c['quantity']}")
        parts.append(f"Price: ${c['price_usd']} | Status: {c['status']}")
        parts.append(f"Address: {c['address']}")
        parts.append("")

    return "\n".join(parts)


# ─── Load system prompt ───────────────────────────────────────────────────────
def load_system_prompt() -> str:
    path = PROMPTS_DIR / f"system_{PROMPT_VERSION}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "You are a helpful customer support assistant for AcmeShop."


# ─── HTTP Server ──────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # suppress default request logging

    def send_json(self, code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self.send_json(200, {"status": "ok", "prompt_version": PROMPT_VERSION})
        elif path == "/version":
            self.send_json(200, {"prompt_version": PROMPT_VERSION, "faq_rows": len(FAQ), "customers": len(CUSTOMERS)})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/chat":
            self.send_json(404, {"error": "Not found"})
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON"})
            return

        message = payload.get("message", "").strip()
        order_id = payload.get("order_id", "").strip() or None

        if not message:
            self.send_json(400, {"error": "message is required"})
            return

        system_prompt = load_system_prompt()
        context = build_context(message, order_id)
        full_user_msg = f"{context}\n\nCustomer message: {message}" if context else message

        reply = call_llm(system_prompt, full_user_msg)

        # Output filter for v2: block canary leaks
        if PROMPT_VERSION == "v2" and contains_canary(reply):
            reply = "I'm sorry, I can't share that information. Is there something else I can help you with?"

        print(f"[{PROMPT_VERSION}] Q: {message[:80]} | A: {reply[:80]}")
        self.send_json(200, {"reply": reply})


def run():
    server = HTTPServer(("0.0.0.0", APP_PORT), Handler)
    print(f"AcmeShop support server running on http://localhost:{APP_PORT}")
    print(f"Prompt version: {PROMPT_VERSION}")
    print(f"FAQ entries: {len(FAQ)} | Customers: {len(CUSTOMERS)}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    run()
