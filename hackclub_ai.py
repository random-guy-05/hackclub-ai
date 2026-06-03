import os, sys, re, json, time, base64, hashlib, mimetypes, zipfile, subprocess, threading, queue, urllib.request, urllib.error, shutil, argparse, uuid
from pathlib import Path
from dataclasses import dataclass
import xml.etree.ElementTree as ET
from rich.console import Console
from rich.markdown import Markdown
from openrouter import OpenRouter
from openrouter.types import UNSET
API_URL = os.getenv("HACKCLUB_AI_BASE_URL", "https://ai.hackclub.com/proxy/v1")
API_KEY = "HACKCLUB_API_KEY"
COMPOSIO_KEY = "COMPOSIO_API_KEY"
HOME = Path.home() / ".hackclub-ai"
_LEGACY_HOME = Path.home() / ".hackclub-ai-shell"
if not HOME.exists() and _LEGACY_HOME.exists():
    try:
        _LEGACY_HOME.rename(HOME)
    except OSError:
        pass
HOME.mkdir(parents=True, exist_ok=True)
CACHE_DIR = HOME / "cache"
MCP_FILE = Path(os.getenv("HC_MCP_CONFIG", str(HOME / "mcp.json")))
MAX_FILE = int(os.getenv("HC_MAX_FILE", "5000000"))
MAX_DOCX_FILE = int(os.getenv("HC_MAX_DOCX_FILE", "30000000"))
INDEX_VERSION = "v3"
MAX_CTX = int(os.getenv("HC_MAX_CONTEXT", "180000"))
MAX_FILES = int(os.getenv("HC_MAX_FILES", "400"))
MAX_TURNS = int(os.getenv("HC_MAX_TURNS", "20"))
# Long-context efficiency: cap the raw history sent per request to a char budget
# (~chars/4 tokens), and fold older turns into a rolling summary once the live
# context grows past a threshold so per-request input stays bounded.
HISTORY_BUDGET = int(os.getenv("HC_HISTORY_BUDGET", str(MAX_CTX // 2)))
AUTO_COMPACT_PCT = float(os.getenv("HC_AUTO_COMPACT_PCT", "75"))
AUTO_COMPACT_KEEP = int(os.getenv("HC_AUTO_COMPACT_KEEP", "6"))
CACHE_TTL = int(os.getenv("HC_CACHE_TTL", "86400"))
MCP_TTL = int(os.getenv("HC_MCP_CACHE_TTL", "300"))
CTX_WINDOW = int(os.getenv("HC_CONTEXT_WINDOW", "200000"))

MODELS = [
    ("GPT Latest", "~openai/gpt-latest"),
    ("GPT Mini", "~openai/gpt-mini-latest"),
    ("GPT-5.5 Pro", "openai/gpt-5.5-pro"),
    ("Claude Sonnet", "~anthropic/claude-sonnet-latest"),
    ("Claude Opus", "~anthropic/claude-opus-latest"),
    ("Gemini Pro", "~google/gemini-pro-latest"),
    ("Gemini Flash", "~google/gemini-flash-latest"),
    ("GLM 5.1", "z-ai/glm-5.1"),
    ("Qwen 3.6 Max", "qwen/qwen3.6-max-preview"),
    ("MiMo v2.5 Pro", "xiaomi/mimo-v2.5-pro"),
    ("KAT Coder v2 Pro", "kwaipilot/kat-coder-pro-v2"),
    ("Kimi", "~moonshotai/kimi-latest"),
    ("DeepSeek V4 Pro", "deepseek/deepseek-v4-pro"),
    ("Auto", "openrouter/auto"),
    ("Custom", "custom"),
]
REASONING_VARIANTS = {
    "openai": [("low", "low"), ("medium", "medium"), ("high", "high"), ("xhigh", "xhigh")],
    "deepseek": [("low", "low"), ("high", "high"), ("max", "xhigh")],
    "anthropic": [("low", "low"), ("medium", "medium"), ("high", "high"), ("max", "xhigh")],
    "google": [("minimal", "minimal"), ("low", "low"), ("medium", "medium"), ("high", "high")],
    "generic": [("low", "low"), ("medium", "medium"), ("high", "high")],
}
SKILLS = {
    "build": "Implement the requested change end-to-end. Start with the smallest working version, preserve existing behavior unless asked otherwise, and state any assumptions that matter.\n\n",
    "debug": "Debug this systematically. Start with the most likely root cause in 1-2 sentences, then show the smallest reliable fix and how to verify it. Avoid unrelated refactors.\n\n",
    "explain": "Explain the code or behavior concretely. Cover purpose, key files/functions, data flow, and the main gotchas. Cite paths or symbols when useful.\n\n",
    "refactor": "Refactor for clarity and maintainability without changing behavior. Prefer small mechanical changes, keep names honest, and avoid broad rewrites unless necessary.\n\n",
    "test": "Add or propose focused tests that cover the happy path, one meaningful edge case, and one failure mode. Use the project's existing test style and avoid noisy low-value tests.\n\n",
    "search": "Find where this lives in the codebase. Return the most relevant files, symbols, and search terms first, with a short note on why each result matters.\n\n",
    "shell": "Give safe shell commands for macOS/Linux. Prefer copy-pasteable commands, note destructive steps, and include a quick explanation for each command.\n\n",
    "api": "Design or implement the API carefully: method, path, auth, request/response schema, validation, status codes, and one concrete example.\n\n",
    "docs": "Write clean developer-facing docs or README text. Be explicit, structured, and optimized for someone using the project for the first time.\n\n",
    "sql": "Write SQL that works. State schema assumptions, explain the query plainly, and suggest an index or simplification if performance could matter.\n\n",
    "pr": "Write a concise PR package: title, summary bullets, testing notes, risks, and rollout or rollback guidance if relevant.\n\n",
    "quick": "Answer as briefly as possible while still being correct. No preamble, no recap, no alternatives unless needed.\n\n",
}
SKILL_ALIASES = {
    "fix": "debug",
    "ship": "build",
    "read": "explain",
    "grep": "search",
    "bash": "shell",
    "regex": "quick",
    "json": "quick",
}
MODE_PROMPTS = {
    "side": (
        "\n\nSIDE MODE: This is a quick side question. Answer briefly and directly. "
        "Do not assume it changes the main project task unless the user says so."
    ),
    "plan": (
        "\n\nPLAN MODE: Do NOT write code or propose disk changes yet. "
        "First produce a numbered execution plan with risks, unknowns, and verification steps. "
        "Wait for explicit approval before implementation."
    ),
    "grill": (
        "\n\nGRILL MODE: Stress-test the user's plan or design with relentless Socratic questioning. "
        "Find weak assumptions, missing edge cases, failure modes, and alternatives. "
        "Ask sharp follow-up questions before offering solutions."
    ),
}
GOAL_KICKOFF = (
    "Execute this goal now. Stay locked to this objective — do not drift. "
    "Do not stop at partial progress, vague next steps, or suggestions. "
    "Keep going until the goal is fully implemented and verified. "
    "If blocked, state the blocker briefly and immediately take the smallest action to unblock it. "
    "Write files with the fs JSON tool — put file content ONLY inside the JSON, never in chat prose. "
    "Keep reasoning minimal; do not draft full files in thinking then repeat them in the reply. "
    "Never tell the user to copy-paste code or save files manually."
)
EXECUTION_RULES = (
    "\n\nEXECUTION RULES:\n"
    "- Reasoning is internal planning only: short bullets, no code, no full file drafts.\n"
    "- Never duplicate content — if you thought it, do not paste it again in the visible reply.\n"
    "- To create/edit local files: reply with ONLY fs JSON (see LOCAL FILESYSTEM ACCESS). "
    "Put the entire file body in the JSON content field — not in markdown fences or prose.\n"
    "- After a successful fs write: confirm briefly (1-2 sentences). Do not re-print the file.\n"
    "- When building something: act first (fs tool), explain second.\n"
)
REVIEW_PROMPT = (
    "Perform a full review using the attached context. "
    "Analyze the project tree for bugs, safety anti-patterns, missing tests, architectural risks, and technical debt. "
    "Order findings by severity. Cite concrete file paths. Skip style nitpicks.\n\n"
)
GRILL_KICKOFF = (
    "GRILL ME — inspect this session for any existing plan, design, or proposed approach.\n"
    "If you find a concrete plan in the conversation or attached context, immediately start stress-testing it "
    "with relentless Socratic questioning. Challenge assumptions, expose edge cases, failure modes, and missing steps. "
    "Ask the hardest questions first. Do not soften or validate — grill it.\n"
    "If there is NO clear plan yet, say explicitly that there is no plan to grill, and tell the user what "
    "minimum plan or design decision you would need before grilling can begin.\n"
    "Do not jump into implementation unless it helps expose a flaw in the plan."
)
YEET_COMMIT_FALLBACK = "chore: automated commit via HackClub AI"
AGENTS_MD_TEMPLATE = """# AGENTS.md

## Project
Describe what this repository does in 2-4 sentences.

## Working rules
- Prefer minimal, focused changes.
- Match existing conventions in this repo.
- Explain risky changes before making them.
- Do not commit secrets, credentials, or local-only files.

## Repository layout
- `src/` — main application code
- `tests/` — automated tests
- `docs/` — documentation

## Commands
- install: `pip install -r requirements.txt`
- test: `pytest`
- run: `python -m app`

## Context notes
Add project-specific constraints, APIs, deployment notes, and gotchas here.
"""
CORE_COMMANDS = [
    "/help", "/model", "/clear", "/exit", "/attach", "/drop", "/context", "/skills",
    "/save", "/copy", "/export", "/system", "/mcp", "/cache", "/theme", "/compact", "/side",
    "/plan", "/goal", "/diff", "/init", "/review", "/grill-me", "/yeet", "/sessions", "/rename",
]
COMMANDS = CORE_COMMANDS + [f"/{k}" for k in SKILLS]
CMD_SET = set(COMMANDS)
SLASH_MENU_LINES = 8
CMD_DESCRIPTIONS = {
    "/help": "List all commands",
    "/model": "Switch model and reasoning level",
    "/attach": "Attach file or folder via Finder",
    "/drop": "Remove attachment(s)",
    "/context": "List attached files and folders",
    "/skills": "List built-in prompt shortcuts",
    "/save": "Save last reply to a file",
    "/copy": "Copy last reply to clipboard",
    "/export": "Download chat as markdown or json",
    "/system": "View or set the system prompt",
    "/mcp": "List connected MCP tools",
    "/cache": "Cache stats, list cached folders, or clear",
    "/theme": "Switch dark or light theme",
    "/compact": "Summarize transcript and replace chat context",
    "/side": "Ask a side question without polluting main history",
    "/plan": "Toggle planning mode (plan before code changes)",
    "/goal": "Start relentless execution mode for an objective",
    "/diff": "Show live git diff in the terminal",
    "/init": "Scaffold AGENTS.md in an attached folder or home",
    "/review": "Run a full project review from attachments",
    "/grill-me": "Immediately stress-test the current plan",
    "/yeet": "Stage, commit, push, and open a GitHub PR",
    "/sessions": "List saved chat sessions",
    "/rename": "Rename the current chat",
    "/clear": "Clear chat history",
    "/exit": "Quit HackClub AI",
}
for _sk in SKILLS:
    CMD_DESCRIPTIONS.setdefault(f"/{_sk}", SKILLS[_sk].split(".")[0].strip())
PREFS_FILE = HOME / "prefs.json"
CONFIG_FILE = HOME / "config.json"
SESSIONS_DIR = HOME / "sessions"
THEMES = {
    "dark": {
        "prompt": "#6ac6ff bold",
        "status": "#ffffff",
        "label": "bold white",
        "dim": "dim",
        "arrow": "cyan",
    },
    "light": {
        "prompt": "#0066cc bold",
        "status": "#000000",
        "label": "bold black",
        "dim": "dim",
        "arrow": "blue",
    },
}
SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
# Smooth pulsing braille bar for the "working" indicator and a 3-state dot cycle
# used to animate the status label (e.g. "Thinking" → "Thinking ·" → "Thinking ··").
SPINNER_BAR = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "▆", "▅", "▄", "▃", "▂"]
SPINNER_DOTS = ["", " ·", " · ·", " · · ·"]
BANNER = "HackClub AI"
CYAN = "\033[96m"
BLUE = "\033[94m"
DIM = "\033[2m"
BOLD = "\033[1m"
RST = "\033[0m"
LOGO = [
    "  ██╗  ██╗ █████╗  ██████╗██╗  ██╗",
    "  ██║  ██║██╔══██╗██╔════╝██║ ██╔╝",
    "  ███████║███████║██║     █████╔╝ ",
    "  ██╔══██║██╔══██║██║     ██╔═██╗ ",
    "  ██║  ██║██║  ██║╚██████╗██║  ██╗",
    "  ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝",
    "",
    "   ██████╗██╗     ██╗   ██╗██████╗ ",
    "  ██╔════╝██║     ██║   ██║██╔══██╗",
    "  ██║     ██║     ██║   ██║██████╔╝",
    "  ██║     ██║     ██║   ██║██╔══██╗",
    "  ╚██████╗███████╗╚██████╔╝██████╔╝",
    "   ╚═════╝╚══════╝ ╚═════╝ ╚═════╝ ",
    "",
    "   ██████╗██╗     ██╗",
    "  ██╔════╝██║     ██║",
    "  ██║     ██║     ██║",
    "  ██║     ██║     ██║",
    "  ╚██████╗███████╗██║",
    "   ╚═════╝╚══════╝╚═╝",
]
GLITCH = "▓░▒█▄▀"
LOGO_PROTECT = " █╗╝╔═║"
INPUT_PAD_LEFT = 2
INPUT_PAD_AFTER_ARROW = 1
INPUT_PAD_RIGHT = 3
INPUT_PAD_Y = 1
INPUT_MAX_LINES = 8
OUTPUT_TOP_MARGIN = 1          # margin above HackClub AI header
STATUS_BOTTOM_MARGIN = 1       # margin below status bar (mirrors top)
OUTPUT_BOTTOM_MARGIN = 2       # chat area → input
INPUT_SLASH_GAP = 1            # one small neutral line between input and slash menu
SLASH_STATUS_GAP = 1           # slash menu → status bar
LINE = "\n"
BLANK = "\n\n"                 # one empty line — used consistently everywhere
WELCOME_KINDS = frozenset({"text", "welcome_model", "label"})
RULE_GAP = LINE                # small gap after ─── divider, before You
HEADER_GAP = BLANK             # slight gap after You / Assistant / thinking headers
THINK_REPLY_GAP = BLANK        # line gap between thinking and the response
THINK_TOOL_GAP = LINE          # smaller gap between thinking and tool status
NOTIFY_USER_GAP = LINE         # gap between a status notify and the next user divider
CONTENT_INDENT = 2
DEFAULT_MODEL = os.getenv("HC_DEFAULT_MODEL", "~openai/gpt-mini-latest")
FALLBACK_MODEL = os.getenv("HC_FALLBACK_MODEL", "deepseek/deepseek-v4-flash")
THINK_INDENT = 4
FOLLOW_MIN_S = 0.15
STREAM_REDRAW_S = 0.22

def load_prefs():
    try:
        return json.loads(PREFS_FILE.read_text())
    except Exception:
        return {}

def load_api_key():
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            key = (data.get("hackclub_api_key") or data.get("api_key") or "").strip()
            if key:
                os.environ[API_KEY] = key
                return key
    except Exception:
        pass
    key = os.getenv(API_KEY, "").strip()
    if key:
        return key
    try:
        prefs = load_prefs()
        key = (prefs.get("hackclub_api_key") or prefs.get("api_key") or "").strip()
        if key:
            os.environ[API_KEY] = key
            return key
    except Exception:
        pass
    return ""

def load_composio_key():
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            key = (data.get("composio_api_key") or "").strip()
            if key:
                os.environ[COMPOSIO_KEY] = key
                return key
    except Exception:
        pass
    key = os.getenv(COMPOSIO_KEY, "").strip()
    if key:
        return key
    return ""

def save_composio_key(key):
    key = (key or "").strip()
    HOME.mkdir(parents=True, exist_ok=True)
    data = {}
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
    except Exception:
        data = {}
    if key:
        data["composio_api_key"] = key
        os.environ[COMPOSIO_KEY] = key
    elif "composio_api_key" in data:
        del data["composio_api_key"]
        os.environ.pop(COMPOSIO_KEY, None)
    write_json_atomic(CONFIG_FILE, data)

def save_api_key(key):
    key = (key or "").strip()
    if not key:
        return
    os.environ[API_KEY] = key
    HOME.mkdir(parents=True, exist_ok=True)
    data = {}
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
    except Exception:
        data = {}
    data["hackclub_api_key"] = key
    write_json_atomic(CONFIG_FILE, data)

def mask_secret(value, show=4):
    value = (value or "").strip()
    if not value:
        return "(not set)"
    if len(value) <= show + 3:
        return "•" * len(value)
    return value[:show] + "…" + value[-3:]

def save_prefs(data):
    try:
        cur = load_prefs()
        cur.update(data)
        PREFS_FILE.write_text(json.dumps(cur, indent=2))
    except Exception:
        pass

def make_session_id():
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]

def session_title_from_history(history):
    for m in history:
        if m.get("role") == "user":
            text = message_text(m.get("content", "")).strip()
            if text:
                text = re.sub(r"\s+", " ", text)
                return text[:80] + ("..." if len(text) > 80 else "")
    return "Untitled session"

def session_display_title(history=None, custom_title=None, data=None):
    if data is not None:
        custom = (data.get("custom_title") or "").strip()
        if custom:
            return custom
        return session_title_from_history(data.get("history") or [])
    custom = (custom_title or "").strip()
    if custom:
        return custom
    return session_title_from_history(history or [])

def rename_saved_session(session_id, title):
    if not session_id:
        return False
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    title = (title or "").strip()
    data["custom_title"] = title or None
    data["title"] = title or session_title_from_history(data.get("history") or [])
    write_json_atomic(path, data)
    return True

def write_json_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)

def delete_all_sessions():
    count = 0
    if not SESSIONS_DIR.exists():
        return 0
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            path.unlink()
            count += 1
        except Exception:
            continue
    return count


def list_saved_sessions():
    if not SESSIONS_DIR.exists():
        return []
    out = []
    for path in SESSIONS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data.setdefault("id", path.stem)
            data.setdefault("updated_at", path.stat().st_mtime)
            out.append(data)
        except Exception:
            continue
    out.sort(key=session_epoch, reverse=True)
    return out


def session_epoch(data):
    v = data.get("updated_at", 0)
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return time.mktime(time.strptime(str(v)[:19], "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 0.0

def format_session_line(data, index=None):
    sid = data.get("id", "?")
    title = data.get("title") or session_display_title(data=data)
    turns = len(data.get("history", [])) // 2
    updated = data.get("updated_at", "")
    if isinstance(updated, (int, float)):
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(updated))
    else:
        when = str(updated)[:16].replace("T", " ")
    prefix = f"{index:2}. " if index is not None else ""
    return f"{prefix}{when}  {title}  ({turns} turns)  [{sid}]"

def pick_saved_session(session_id=None):
    sessions = list_saved_sessions()
    if not sessions:
        return None
    if not session_id:
        return None
    matches = [s for s in sessions if s["id"] == session_id or s["id"].startswith(session_id)]
    if len(matches) == 1:
        return matches[0]
    return None

def parse_cli_args(argv):
    parser = argparse.ArgumentParser(prog="hackclub-ai", add_help=True)
    parser.add_argument(
        "--resume",
        nargs="?",
        const="",
        default=None,
        metavar="ID",
        help="resume a saved session (optionally by id prefix)",
    )
    parser.add_argument(
        "prompt",
        nargs=argparse.REMAINDER,
        help="optional first message to send after startup",
    )
    args = parser.parse_args(argv)
    prompt_parts = list(args.prompt)
    resume = args.resume
    if resume is not None and str(resume).startswith("/"):
        prompt_parts.insert(0, resume)
        resume = None
    prompt = " ".join(prompt_parts).strip()
    if prompt == "--":
        prompt = ""
    return {"resume": resume, "prompt": prompt}

def default_model():
    return load_prefs().get("model") or DEFAULT_MODEL

def model_family(model):
    m = (model or "").lower()
    if "openai/" in m:
        return "openai"
    if "deepseek/" in m:
        return "deepseek"
    if "anthropic/" in m or "claude" in m:
        return "anthropic"
    if "google/" in m or "gemini" in m:
        return "google"
    return "generic"

def reasoning_variants_for_model(model):
    return REASONING_VARIANTS.get(model_family(model), REASONING_VARIANTS["generic"])

def default_reasoning_for_model(model):
    fam = model_family(model)
    if fam == "deepseek":
        return "medium"
    return "medium"

def normalize_reasoning_for_model(model, value=None):
    if not value:
        return default_reasoning_for_model(model)
    low = str(value).strip().lower()
    choices = reasoning_variants_for_model(model)
    for label, effort in choices:
        if low in {label.lower(), effort.lower()}:
            return effort
    return default_reasoning_for_model(model)

def reasoning_label_for_model(model, value=None):
    effort = normalize_reasoning_for_model(model, value)
    for label, canonical in reasoning_variants_for_model(model):
        if canonical == effort:
            return label
    return effort

def resolve_model_query(text, allow_partial=False):
    q = (text or "").strip()
    if not q:
        return None
    if q.isdigit():
        idx = int(q) - 1
        if 0 <= idx < len(MODELS):
            return MODELS[idx][1]
    ql = q.lower()
    for name, mid in MODELS:
        if ql == mid.lower() or ql == name.lower():
            return mid
    if allow_partial:
        for name, mid in MODELS:
            if ql in name.lower() or ql in mid.lower():
                return mid
    if "/" in q or q.startswith("~"):
        return q
    return None

def parse_model_command(q):
    q = (q or "").strip()
    if not q:
        return {"kind": "list", "filter": ""}
    if q.lower() == "custom" or q.lower().startswith("custom "):
        tail = q[6:].strip() if q.lower().startswith("custom ") else ""
        if not tail:
            return {"kind": "custom_id", "model_id": None, "variant_q": ""}
        tokens = tail.split()
        model_id = tokens[0]
        variant_q = " ".join(tokens[1:]).lower()
        if "/" in model_id or model_id.startswith("~"):
            return {"kind": "variants", "model_id": model_id, "display": model_id, "variant_q": variant_q, "custom": True}
        return {"kind": "custom_id", "model_id": model_id, "variant_q": variant_q}
    mid, name, rest = split_model_query(q)
    if mid and mid != "custom":
        return {"kind": "variants", "model_id": mid, "display": name, "variant_q": rest.lower(), "custom": False}
    first = q.split()[0]
    if "/" in first or first.startswith("~"):
        tokens = q.split()
        return {"kind": "variants", "model_id": tokens[0], "display": tokens[0], "variant_q": " ".join(tokens[1:]).lower(), "custom": False}
    return {"kind": "list", "filter": q.lower()}

def model_command_insert(model_id, display, label, custom=False):
    if custom:
        return f"/model custom {model_id} {label}"
    return f"/model {display} {label}"

def split_model_query(text):
    q = (text or "").strip()
    if not q:
        return None, None, ""
    if q.isdigit():
        idx = int(q) - 1
        if 0 <= idx < len(MODELS):
            name, mid = MODELS[idx]
            return mid, name, ""
    candidates = []
    for name, mid in MODELS:
        candidates.append((name, mid, name))
        candidates.append((mid, mid, name))
    candidates.sort(key=lambda item: len(item[0]), reverse=True)
    ql = q.lower()
    for token, mid, name in candidates:
        tl = token.lower()
        if ql == tl:
            return mid, name, ""
        if ql.startswith(tl + " "):
            return mid, name, q[len(token):].strip()
    return None, None, q

def run_cmd(args, cwd=None, timeout=120):
    try:
        p = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except FileNotFoundError:
        return 127, "", f"command not found: {args[0]}"
    except Exception as e:
        return 1, "", str(e)

def git_root(start=None):
    start = Path(start or Path.cwd()).expanduser()
    try:
        start = start.resolve()
    except Exception:
        pass
    code, out, _ = run_cmd(["git", "-C", str(start), "rev-parse", "--show-toplevel"])
    if code == 0 and out.strip():
        return Path(out.strip())
    cur = start if start.is_dir() else start.parent
    for p in [cur, *cur.parents]:
        if (p / ".git").exists():
            return p
    return cur

def copy_to_clipboard(text):
    text = text or ""
    if not text.strip():
        return False, "nothing to copy"
    try:
        if sys.platform == "darwin":
            p = subprocess.run(["pbcopy"], input=text, text=True, capture_output=True, timeout=5)
            if p.returncode == 0:
                return True, None
        elif sys.platform.startswith("linux"):
            for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
                try:
                    p = subprocess.run(cmd, input=text, text=True, capture_output=True, timeout=5)
                    if p.returncode == 0:
                        return True, None
                except FileNotFoundError:
                    continue
    except Exception as e:
        return False, str(e)
    return False, "clipboard unavailable (install pbcopy, wl-copy, or xclip)"

def export_download_dir():
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    return HOME

def export_default_name(fmt="md"):
    ext = "json" if fmt == "json" else "md"
    return f"hackclub-chat-{time.strftime('%Y-%m-%d-%H%M%S')}.{ext}"

def write_export_file(path, body):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)
    return path.resolve()

def reveal_export(path):
    path = Path(path)

    def run():
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", str(path)], check=False, timeout=5)
            elif sys.platform.startswith("linux"):
                subprocess.run(["xdg-open", str(path.parent)], check=False, timeout=5)
            elif sys.platform == "win32":
                subprocess.run(["explorer", "/select,", str(path)], check=False, timeout=5)
        except Exception:
            pass

    threading.Thread(target=run, daemon=True).start()

def message_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif item.get("type") == "image_url":
                    parts.append("[image]")
        return "\n".join(p for p in parts if p)
    return str(content)

def pick_macos_path(kind):
    script = (
        'POSIX path of (choose folder with prompt "Attach folder")'
        if kind == "folder"
        else 'POSIX path of (choose file with prompt "Attach file")'
    )
    try:
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=180)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().rstrip("/")
    except Exception:
        pass
    return None

def pick_path_for_kind(kind):
    return pick_macos_path(kind)

def rich_style_to_pt(style, tone="normal"):
    if not style:
        return "class:think" if tone == "think" else "class:text"
    s = str(style)
    if "on black" in s or ("cyan" in s and style.bold):
        return "class:think_code" if tone == "think" else "class:code"
    if "underline" in s:
        return "class:think_h" if tone == "think" else "class:md_h"
    if style.italic:
        return "class:think_em" if tone == "think" else "class:md_em"
    if style.bold:
        return "class:think_strong" if tone == "think" else "class:md_strong"
    return "class:think" if tone == "think" else "class:text"

def format_md_segment(text, style, is_last_on_line):
    s = str(style or "").lower()
    m = re.match(r"^\s*(\d+)\s*$", text)
    if m and "cyan" in s:
        return f"{m.group(1)}. "
    return text.rstrip(" \t") if is_last_on_line else text.rstrip("\t")

def md_to_fragments(text, width=100, indent=0, tone="normal"):
    if not text or not text.strip():
        return [("class:text", "")]
    pad = " " * indent
    w = max(40, min(width - indent, 200))
    console = Console(width=w, highlight=False)
    try:
        lines = console.render_lines(Markdown(text), console.options)
    except Exception:
        return [(("class:think" if tone == "think" else "class:text"), pad + text)]
    out = []
    blank = "class:think" if tone == "think" else "class:text"
    for line in lines:
        row = []
        if indent:
            row.append((blank, pad))
        segs = list(line)
        for j, seg in enumerate(segs):
            t = format_md_segment(seg.text, seg.style, j == len(segs) - 1)
            if t:
                row.append((rich_style_to_pt(seg.style, tone), t))
        if row:
            out.extend(row)
            out.append((blank, "\n"))
        elif not out or out[-1][1] != "\n":
            if indent:
                out.append((blank, pad + "\n"))
            else:
                out.append((blank, "\n"))
    return out or [("class:text", "")]

def normalize_input(raw):
    raw = raw.strip()
    if not raw:
        return None
    raw = re.sub(r"^/\s+(\S)", r"/\1", raw)
    if raw.startswith("/"):
        parts = raw.split(None, 1)
        cmd = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ""
        if cmd in CMD_SET or cmd.startswith("/skill:"):
            return f"{cmd} {rest}".strip() if rest else cmd
        return raw
    for m in re.finditer(r"(?:^|\s)(/\S+)", raw):
        token = m.group(1)
        base = token.lower()
        if base in CMD_SET or base.startswith("/skill:") or base.startswith("/mcp"):
            before = raw[:m.start(1)].strip()
            after = raw[m.end(1):].strip()
            rest = " ".join(x for x in [before, after] if x)
            return f"{token} {rest}".strip() if rest else token
    return raw

@dataclass
class UiBlock:
    kind: str
    text: str = ""
    style: str = "class:text"

@dataclass
class Attachment:
    id: int; name: str; kind: str; path: Path; content: object; chars: int = 0; files: int = 1; cached: bool = False

@dataclass
class Usage:
    input: int = 0; output: int = 0; cached: int = 0
    @property
    def total(self): return self.input + self.output

class Cache:
    def __init__(self): CACHE_DIR.mkdir(parents=True, exist_ok=True)
    def _hash(self, key): return hashlib.sha256(key.encode()).hexdigest()
    def path(self, key, hint=None):
        h = self._hash(key)
        if hint:
            safe = re.sub(r"[^a-zA-Z0-9._-]", "_", hint)[:48].strip("_") or "ws"
            return CACHE_DIR / f"{safe}__{h[:12]}.json"
        return CACHE_DIR / f"{h}.json"
    def find(self, key):
        h = self._hash(key)
        legacy = CACHE_DIR / f"{h}.json"
        if legacy.exists():
            return legacy
        for p in CACHE_DIR.glob(f"*__{h[:12]}.json"):
            return p
        return None
    def get(self, key, ttl=CACHE_TTL):
        p = self.find(key)
        if not p: return None
        try:
            if time.time() - p.stat().st_mtime > ttl: return None
            return json.loads(p.read_text())
        except Exception: return None
    def set(self, key, value, hint=None):
        try:
            for old in CACHE_DIR.glob(f"*__{self._hash(key)[:12]}.json"):
                old.unlink(missing_ok=True)
            self.path(key, hint=hint).write_text(json.dumps(value))
        except Exception: pass
    def clear(self):
        for p in CACHE_DIR.glob("*.json"): p.unlink(missing_ok=True)
    def stats(self): return len(list(CACHE_DIR.glob("*.json"))), sum(p.stat().st_size for p in CACHE_DIR.glob("*.json"))
    def cached_folders(self):
        out = []
        for p in sorted(CACHE_DIR.glob("*__*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                data = json.loads(p.read_text())
                if data.get("kind") == "text" and "files" in data:
                    out.append({"file": p.name, "name": data.get("name", "?"), "files": data.get("files", 1), "chars": data.get("chars", 0), "mtime": p.stat().st_mtime})
            except Exception: pass
        return out

class Indexer:
    def __init__(self, cache): self.cache = cache
    def load(self, raw, aid):
        path = Path(raw).expanduser().resolve()
        if not path.exists(): return None
        sig = self.sig_dir(path) if path.is_dir() else self.sig_file(path)
        key = f"idx:{INDEX_VERSION}:{sig}"
        hint = path.name
        hit = self.cache.get(key)
        if hit: return Attachment(aid, hit["name"], hit["kind"], path, hit["content"], hit["chars"], hit["files"], True)
        att = self.dir(path, aid) if path.is_dir() else self.file(path, aid)
        if att: self.cache.set(key, {"name": att.name, "kind": att.kind, "content": att.content, "chars": att.chars, "files": att.files}, hint=hint)
        return att
    def sig_file(self, path):
        s = path.stat(); return f"file:{path}:{s.st_size}:{int(s.st_mtime)}"
    def sig_dir(self, root):
        h = hashlib.sha256(("dir:" + str(root)).encode()); n = 0
        for base, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not d.startswith("."))
            for name in sorted(files):
                if n >= MAX_FILES: break
                if name in IGNORE_FILES or name.startswith("."): continue
                p = Path(base) / name
                try:
                    if self.is_readable(p):
                        s = p.stat(); h.update(f"{p.relative_to(root)}:{s.st_size}:{int(s.st_mtime)}".encode()); n += 1
                except Exception: pass
        return h.hexdigest()
    def is_readable(self, p):
        ext = p.suffix.lower()
        try: size = p.stat().st_size
        except Exception: return False
        if ext == ".docx": return size <= MAX_DOCX_FILE
        if ext in TEXT_EXT: return size <= MAX_FILE
        return False
    def file(self, path, aid):
        mime, _ = mimetypes.guess_type(str(path))
        if mime and mime.startswith("image/"):
            data = base64.b64encode(path.read_bytes()).decode()
            return Attachment(aid, f"Image: {path.name}", "image", path, {"mime": mime, "data": data}, len(data))
        text = self.text(path)
        if not text: return None
        body = f"### Attachment: {path.name}\n```text\n{text[:MAX_CTX]}\n```"
        return Attachment(aid, f"File: {path.name}", "text", path, body, len(body))
    def dir(self, root, aid):
        all_files = []
        all_dirs = []
        for base, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if d not in IGNORE_DIRS and not d.startswith("."))
            rel = Path(base).relative_to(root)
            for d in dirs:
                all_dirs.append((rel / d).as_posix())
            for name in sorted(files):
                if name in IGNORE_FILES or name.startswith("."):
                    continue
                rel_path = (rel / name).as_posix()
                all_files.append((Path(base) / name, rel_path, len(rel.parts)))
        all_files.sort(key=lambda x: (x[2], x[1].lower()))
        loaded = {}
        not_loaded = {}
        total = 0
        count = 0
        for path, rel_path, _ in all_files:
            ext = path.suffix.lower()
            if ext not in TEXT_EXT | {".docx"}:
                not_loaded[rel_path] = "unsupported type"
                continue
            try:
                size = path.stat().st_size
            except Exception:
                not_loaded[rel_path] = "unreadable"
                continue
            if ext == ".docx" and size > MAX_DOCX_FILE:
                not_loaded[rel_path] = f"docx {size/1024/1024:.1f}MB > {MAX_DOCX_FILE/1024/1024:.0f}MB limit"
                continue
            if ext != ".docx" and size > MAX_FILE:
                not_loaded[rel_path] = f"{size/1024/1024:.1f}MB > {MAX_FILE/1024/1024:.0f}MB limit"
                continue
            if count >= MAX_FILES:
                not_loaded[rel_path] = "per-folder file limit reached"
                continue
            if total >= MAX_CTX:
                not_loaded[rel_path] = "context budget filled"
                continue
            text = self.text(path)
            if not text:
                not_loaded[rel_path] = "empty / parse failed"
                continue
            chunk_body = f"--- START FILE: {rel_path} ---\n{text}\n--- END FILE: {rel_path} ---"
            if total + len(chunk_body) > MAX_CTX:
                chunk_body = chunk_body[:MAX_CTX - total]
            loaded[rel_path] = chunk_body
            total += len(chunk_body)
            count += 1
        kids_dirs = {}
        kids_files = {}
        for d in set(all_dirs):
            parent = "/".join(d.split("/")[:-1])
            kids_dirs.setdefault(parent, []).append(d.split("/")[-1])
        for path, rel_path, _ in all_files:
            parent = "/".join(rel_path.split("/")[:-1])
            note = None if rel_path in loaded else not_loaded.get(rel_path, "not loaded")
            kids_files.setdefault(parent, []).append((path.name, note, rel_path))
        tree_lines = [f"{root.name}/"]
        def render(parent_path, depth):
            indent = "  " * (depth + 1)
            for d in sorted(kids_dirs.get(parent_path, []), key=str.lower):
                tree_lines.append(f"{indent}{d}/")
                child_parent = f"{parent_path}/{d}" if parent_path else d
                render(child_parent, depth + 1)
            for name, note, _ in sorted(kids_files.get(parent_path, []), key=lambda x: x[0].lower()):
                line = f"{indent}{name}"
                if note:
                    line += f"  [not loaded: {note}]"
                tree_lines.append(line)
        render("", 0)
        notice = (
            f"Folder dump — {count}/{len(all_files)} files loaded into context, "
            f"{len(not_loaded)} listed in tree only. .docx files ARE parsed (text + tables); "
            f"if a .docx is marked [not loaded] the reason is shown next to it."
        )
        header = ["### Folder: " + root.name, notice, "```text", *tree_lines[:600], "```"]
        body_parts = header + [loaded[k] for k in sorted(loaded.keys(), key=lambda x: x.lower())]
        body = "\n".join(body_parts)
        return Attachment(aid, f"Folder: {root.name}", "text", root, body, len(body), count)
    def text(self, path):
        try:
            ext = path.suffix.lower()
            size = path.stat().st_size
            if ext == ".docx":
                if size > MAX_DOCX_FILE: return None
                return self.docx(path)
            if ext not in TEXT_EXT: return None
            if size > MAX_FILE: return None
            return path.read_text("utf-8", errors="replace")
        except Exception:
            return None
    def docx(self, path):
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        parts = []
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if "word/document.xml" not in names:
                    return f"[unable to extract .docx text: missing word/document.xml in archive — {path.name}]"
                xml_parts = ["word/document.xml"]
                xml_parts += sorted(n for n in names if (n.startswith("word/header") or n.startswith("word/footer")) and n.endswith(".xml"))
                xml_parts += [n for n in ("word/footnotes.xml", "word/endnotes.xml") if n in names]
                for fname in xml_parts:
                    try:
                        xml = z.read(fname)
                    except Exception:
                        continue
                    try:
                        root = ET.fromstring(xml)
                    except ET.ParseError:
                        continue
                    for p in root.findall(".//w:p", ns):
                        line = "".join(t.text for t in p.findall(".//w:t", ns) if t.text)
                        if line.strip():
                            parts.append(line)
                    for tbl in root.findall(".//w:tbl", ns):
                        for tr in tbl.findall(".//w:tr", ns):
                            cells = []
                            for tc in tr.findall(".//w:tc", ns):
                                cell = " ".join("".join(t.text for t in p.findall(".//w:t", ns) if t.text) for p in tc.findall(".//w:p", ns)).strip()
                                cells.append(cell)
                            if any(cells):
                                parts.append(" | ".join(cells))
        except zipfile.BadZipFile:
            return f"[unable to extract .docx text: not a valid .docx archive — {path.name}]"
        except Exception as e:
            return f"[unable to extract .docx text: {type(e).__name__}: {e} — {path.name}]"
        if not parts:
            return f"[.docx opened but no readable text found — {path.name}]"
        seen = set()
        unique = []
        for line in parts:
            if line not in seen:
                seen.add(line)
                unique.append(line)
        return "\n".join(unique)

def envv(x):
    if isinstance(x, str):
        return re.sub(r"\$\{?([A-Z0-9_]+)\}?", lambda m: os.getenv(m.group(1), ""), x)
    if isinstance(x, dict): return {k: envv(v) for k, v in x.items()}
    if isinstance(x, list): return [envv(v) for v in x]
    return x


def extract_json_objects(text):
    out = []
    if not text:
        return out
    i = 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        start = i
        for j in range(i, len(text)):
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    out.append(text[start:j + 1])
                    i = j + 1
                    break
        else:
            i += 1
    return out

def try_parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        fixed = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            return None

def normalize_mcp_call(data):
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("mcp"), dict):
        data = data["mcp"]
    elif not (data.get("tool") or data.get("name")):
        return None
    tool = data.get("tool") or data.get("name")
    if not tool:
        return None
    args = data.get("arguments")
    if args is None:
        args = data.get("args")
    if args is None:
        args = data.get("parameters")
    if not isinstance(args, dict):
        args = {}
    return {"tool": str(tool).strip(), "arguments": args}

def normalize_fs_call(data):
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("fs"), dict):
        data = data["fs"]
    elif isinstance(data.get("write"), dict):
        data = {"action": "write", **data["write"]}
    elif data.get("path") and "content" in data and not data.get("tool"):
        data = {"action": "write", **data}
    action = data.get("action", "write")
    if action == "write":
        path = data.get("path")
        if not path:
            return None
        content = data.get("content")
        if content is None:
            content = ""
        return {"action": "write", "path": str(path), "content": str(content)}
    if action == "run":
        cmd = data.get("command") or data.get("cmd")
        if not cmd:
            return None
        return {"action": "run", "command": str(cmd)}
    return None

def parse_fs_call(text):
    if not text or not text.strip():
        return None
    candidates = []
    for block in re.findall(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I):
        block = block.strip()
        if block:
            candidates.append(block)
    candidates.extend(extract_json_objects(text))
    seen = set()
    for c in reversed(candidates):
        if c in seen:
            continue
        seen.add(c)
        data = try_parse_json(c)
        if data is None:
            continue
        call = normalize_fs_call(data)
        if call:
            return call
    return None

def local_fs_prompt(write_root):
    root = str(write_root)
    return (
        "\n\nLOCAL FILESYSTEM ACCESS:\n"
        "You are running HackClub AI on the user's computer with direct file access. "
        "Never say you cannot write files to their machine.\n"
        f"Default output directory: {root}\n"
        "WHEN CREATING OR EDITING FILES:\n"
        "- Output ONLY this JSON (no markdown fences, no prose before/after):\n"
        f'  {{"fs":{{"action":"write","path":"{root}/index.html","content":"..."}}}}\n'
        "- Put the COMPLETE file contents inside content — nowhere else.\n"
        "- Do NOT show the same code in your chat reply. One sentence confirmation after write is enough.\n"
        f"Paths support ~ expansion. Relative paths resolve under {root}.\n"
        f'To run a shell command: {{"fs":{{"action":"run","command":"open {root}/index.html"}}}}\n'
    )

def fs_nudge_message(attempt):
    return (
        "You pasted code in chat instead of writing to disk.\n"
        "Reply with ONLY valid JSON (no markdown, no explanation):\n"
        '{"fs":{"action":"write","path":"~/path/to/file.ext","content":"..."}}\n'
        "The full file body goes in content only. Do not repeat it outside the JSON."
    )

FS_MAX_NUDGES = 2

def user_wants_fs(prompt, shell=None):
    p = (prompt or "").lower()
    if shell and (shell.session_mode == "goal" or shell.goal):
        return True
    triggers = (
        "build", "create", "write", "save", "file", "html", "website", "web page",
        "implement", "scaffold", "generate", "make me", "index.html", "script",
        "to my computer", "to disk", "locally", "documents folder", "home directory",
        "single file", "open in browser", "deploy locally",
    )
    return any(t in p for t in triggers)

def looks_like_code_without_fs(text):
    if not text or not text.strip():
        return False
    if parse_fs_call(text):
        return False
    if parse_mcp_call(text):
        return False
    if "```" in text:
        return True
    low = text.lower()
    if len(text) > 1200 and any(m in low for m in ("<!doctype", "<html", "function ", "def ", "class ", "import ")):
        return True
    return False

def fs_continue_message():
    return (
        "Filesystem result above.\n"
        "- Task incomplete → reply with ONLY valid JSON: "
        '{"fs":{"action":"write","path":"...","content":"..."}}\n'
        "- Or run a command: {\"fs\":{\"action\":\"run\",\"command\":\"...\"}}\n"
        "- Double quotes, no trailing commas.\n"
        "- When done, summarize in plain language what was created."
    )

FS_MAX_STEPS = 12

def parse_mcp_call(text):
    if not text or not text.strip():
        return None
    candidates = []
    for block in re.findall(r"```(?:json)?\s*(.*?)\s*```", text, re.S | re.I):
        block = block.strip()
        if block:
            candidates.append(block)
    candidates.extend(extract_json_objects(text))
    seen = set()
    for c in reversed(candidates):
        if c in seen:
            continue
        seen.add(c)
        try:
            data = try_parse_json(c)
        except Exception:
            continue
        if data is None:
            continue
        call = normalize_mcp_call(data)
        if call:
            return call
    return None

MCP_MAX_STEPS = 12
MCP_MAX_NUDGES = 2

def mcp_continue_message():
    return (
        "Tool result above.\n"
        "- Task incomplete → reply with ONLY valid JSON: {\"mcp\":{\"tool\":\"...\",\"arguments\":{...}}}\n"
        "- Execute via COMPOSIO_MULTI_EXECUTE_TOOL with tools:[{tool_slug,arguments}], sync_response_to_workbench, memory:{}.\n"
        "- Auth issue → composio.COMPOSIO_MANAGE_CONNECTIONS.\n"
        "- Double quotes, no trailing commas, no {...} placeholders.\n"
        "- Never claim success unless this result confirms it. When done, summarize in plain language."
    )

def mcp_nudge_message(attempt):
    if attempt <= 1:
        return (
            "No tool ran — your reply was not valid executable JSON.\n"
            "Output ONLY this (one line, no markdown):\n"
            '{"mcp":{"tool":"composio.COMPOSIO_SEARCH_TOOLS","arguments":{"queries":[{"use_case":"send email via gmail"}]}}}'
        )
    return (
        "Still no valid tool JSON. Output ONLY one parseable object. "
        'Example execute: {"mcp":{"tool":"composio.COMPOSIO_MULTI_EXECUTE_TOOL","arguments":{"tools":[{"tool_slug":"GMAIL_SEND_EMAIL","arguments":{"to":"x@y.com","subject":"Hi","body":"Hello"}}],"sync_response_to_workbench":false,"memory":{}}}}'
    )

def mcp_integration_prompt(mcp, user_request=""):
    names = []
    try:
        names = sorted({t["name"] for t in mcp.tools() if t.get("name") and t["name"] != "ERROR"})
    except Exception:
        pass
    tools_line = ", ".join(names) if names else "COMPOSIO_SEARCH_TOOLS, COMPOSIO_MULTI_EXECUTE_TOOL"
    task = (user_request or "").strip().replace("\n", " ")[:400]
    return (
        "\n\nThe user requested an external action. Connected integrations are live: "
        + tools_line
        + ".\n\n"
        "HOW TO CALL TOOLS\n"
        "- Output one raw JSON object per message. The shell parses and runs it.\n"
        "- Format: {\"mcp\":{\"tool\":\"composio.TOOL_NAME\",\"arguments\":{...}}}\n"
        "- Use double quotes only. No trailing commas. No {...} placeholders — fill real values.\n"
        "- No markdown fences. No text before or after the JSON in tool-call messages.\n\n"
        "STEP 1 — search (copy exactly, change use_case if needed):\n"
        '{"mcp":{"tool":"composio.COMPOSIO_SEARCH_TOOLS","arguments":{"queries":[{"use_case":"'
        + (task or "complete the user request")
        + '"}]}}}\n\n'
        "STEP 2 — execute (use tool_slug + arguments from search results; memory and sync_response_to_workbench are REQUIRED):\n"
        '{"mcp":{"tool":"composio.COMPOSIO_MULTI_EXECUTE_TOOL","arguments":{"tools":[{"tool_slug":"GMAIL_SEND_EMAIL","arguments":{"to":"user@example.com","subject":"Subject","body":"Body text"}}],"sync_response_to_workbench":false,"memory":{}}}}\n\n'
        "JSON RULES (common syntax errors to avoid)\n"
        "- arguments.tools must be an array of {tool_slug, arguments} objects — not a bare slug string.\n"
        "- COMPOSIO_MULTI_EXECUTE_TOOL requires sync_response_to_workbench (boolean) and memory (object, use {} if empty).\n"
        "- COMPOSIO_SEARCH_TOOLS uses queries: [{use_case: \"...\"}] — not query, not use-case.\n"
        "- Tool names are UPPER_SNAKE like GMAIL_SEND_EMAIL inside tool_slug; composio.COMPOSIO_* for meta tools.\n"
        "- Pass session_id from search results into later execute calls when provided.\n\n"
        "WORKFLOW\n"
        "1. Search → 2. Execute with real slugs/args from results → 3. If auth fails use COMPOSIO_MANAGE_CONNECTIONS "
        "→ 4. Repeat until done → 5. Then answer the user in plain language.\n\n"
        "NEVER claim an action succeeded without a tool result confirming it. NEVER say you lack access."
    )

class StdioMCP:
    def __init__(self, name, cfg, cache):
        self.name, self.cfg, self.cache, self.proc, self.q, self.seq = name, cfg, cache, None, queue.Queue(), 1
    def start(self):
        if self.proc and self.proc.poll() is None: return
        env = os.environ.copy(); env.update(self.cfg.get("env", {}))
        self.proc = subprocess.Popen([self.cfg["command"], *self.cfg.get("args", [])], cwd=self.cfg.get("cwd"), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1)
        threading.Thread(target=self.reader, daemon=True).start()
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "hackclub-ai", "version": "1.0"}}, init=True)
        self.notify("notifications/initialized", {})
    def reader(self):
        for line in self.proc.stdout:
            try: self.q.put(json.loads(line))
            except Exception: pass
    def send(self, msg): self.proc.stdin.write(json.dumps(msg) + "\n"); self.proc.stdin.flush()
    def notify(self, method, params=None): self.send({"jsonrpc": "2.0", "method": method, "params": params or {}})
    def rpc(self, method, params=None, timeout=30, init=False):
        if not init: self.start()
        rid = self.seq; self.seq += 1; self.send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        end = time.time() + timeout
        while time.time() < end:
            try: msg = self.q.get(timeout=.1)
            except queue.Empty: continue
            if msg.get("id") == rid:
                if "error" in msg: raise RuntimeError(msg["error"])
                return msg.get("result", {})
        raise TimeoutError(f"MCP timeout: {self.name}.{method}")
    def tools(self): return mcp_tools_cached(self, self.cache)
    def call(self, tool, args): return self.rpc("tools/call", {"name": tool, "arguments": args}, timeout=60)

class HttpMCP:
    def __init__(self, name, cfg, cache):
        self.name, self.cfg, self.cache, self.seq, self.session = name, cfg, cache, 1, None
        self.url = cfg["url"]; self.headers = cfg.get("headers", {})
        self.inited = False
    def start(self):
        if self.inited: return
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "hackclub-ai", "version": "1.0"}}, init=True)
        self.notify("notifications/initialized", {})
        self.inited = True
    def base_headers(self):
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", **self.headers}
        if self.session: h["Mcp-Session-Id"] = self.session
        return h
    def post(self, body, timeout=60):
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=self.base_headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                self.session = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id") or self.session
                data = r.read().decode()
                ctype = r.headers.get("content-type", "")
        except urllib.error.HTTPError as e:
            raise RuntimeError(e.read().decode() or str(e))
        if not data.strip(): return {}
        if "text/event-stream" in ctype:
            for line in data.splitlines():
                if line.startswith("data:"):
                    raw = line[5:].strip()
                    if raw and raw != "[DONE]": return json.loads(raw)
            return {}
        return json.loads(data)
    def notify(self, method, params=None): self.post({"jsonrpc": "2.0", "method": method, "params": params or {}}, 15)
    def rpc(self, method, params=None, timeout=60, init=False):
        if not init: self.start()
        rid = self.seq; self.seq += 1
        msg = self.post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, timeout)
        if "error" in msg: raise RuntimeError(msg["error"])
        return msg.get("result", {})
    def tools(self): return mcp_tools_cached(self, self.cache)
    def call(self, tool, args): return self.rpc("tools/call", {"name": tool, "arguments": args}, timeout=90)

def mcp_tools_cached(server, cache):
    key = "mcp-tools:" + server.name + ":" + hashlib.sha256(json.dumps(server.cfg, sort_keys=True).encode()).hexdigest()
    hit = cache.get(key, MCP_TTL)
    if hit: return hit
    tools = server.rpc("tools/list").get("tools", [])
    cache.set(key, tools)
    return tools

class MCP:
    def __init__(self, cache):
        self.cache, self.servers = cache, {}
        self.enabled = True
        self.load()
    def default_config(self):
        return {"mcpServers": {"composio": {"url": "https://connect.composio.dev/mcp", "headers": {"x-consumer-api-key": "${COMPOSIO_API_KEY}"}}}}
    def load(self):
        self.servers = {}
        data = self.default_config()
        if MCP_FILE.exists():
            try:
                custom = json.loads(MCP_FILE.read_text())
                data["mcpServers"].update(custom.get("mcpServers", {}))
            except Exception: pass
        for name, cfg in data.get("mcpServers", {}).items():
            cfg = envv(cfg)
            if name == "composio" and not cfg.get("headers", {}).get("x-consumer-api-key"): continue
            if "command" in cfg: self.servers[name] = StdioMCP(name, cfg, self.cache)
            elif "url" in cfg: self.servers[name] = HttpMCP(name, cfg, self.cache)
    def tools(self):
        out = []
        for name, srv in self.servers.items():
            try:
                for t in srv.tools(): out.append({"server": name, "name": t.get("name"), "description": t.get("description", ""), "inputSchema": t.get("inputSchema", {})})
            except Exception as e: out.append({"server": name, "name": "ERROR", "description": str(e), "inputSchema": {}})
        return out
    def prompt(self):
        return ""
    def resolve_tool(self, tool):
        tool = (tool or "").strip()
        if not tool:
            raise RuntimeError("Empty MCP tool name")
        if "." in tool:
            server, name = tool.split(".", 1)
            if server in self.servers:
                return server, name
        known = {t["name"]: t["server"] for t in self.tools() if t["name"] != "ERROR"}
        bare = tool.split(".")[-1]
        if bare in known:
            return known[bare], bare
        if "composio" in self.servers:
            return "composio", bare
        if len(self.servers) == 1:
            return next(iter(self.servers)), bare
        raise RuntimeError(f"Unknown MCP tool: {tool}")
    def call(self, tool, args):
        server, name = self.resolve_tool(tool)
        return self.servers[server].call(name, args or {})

def user_wants_mcp(prompt):
    p = (prompt or "").lower()
    triggers = (
        "github", "gitlab", "slack", "gmail", "google drive", "jira", "notion",
        "linear", "discord", "send email", "send an email", "send a email",
        "send mail", "email to", "e-mail", " create an issue", "post to",
        "composio", "integration", "connect my", "mcp tool", "use mcp",
    )
    return any(t in p for t in triggers)

def safe(fn, default=None):
    try:
        return fn()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return default

class Shell:
    def __init__(self, api_key=None):
        key = (api_key or load_api_key()).strip()
        if not key:
            raise ValueError(f"Missing {API_KEY}")
        os.environ[API_KEY] = key
        HOME.mkdir(parents=True, exist_ok=True)
        self.blocks = []
        self._frag_lock = threading.Lock()
        self.stream_i = None
        self.ui_delegate = None
        self.busy = False
        self.cache = Cache()
        self.client = OpenRouter(api_key=key, server_url=API_URL)
        self.mcp = MCP(self.cache)
        self.model = default_model()
        self.reasoning_level = normalize_reasoning_for_model(self.model, load_prefs().get("reasoning"))
        self.history = []
        self.attachments = []
        self.last = ""
        self.aid = 1
        self.usage = Usage()
        self.session_usage = Usage()
        self.mcp_tool_count = 0
        self._status_ver = 0
        self.follow_output = False
        self._keep_at_top = True
        self._body_ver = 0
        self.output_control = None
        self.indexer = Indexer(self.cache)
        prefs = load_prefs()
        self.theme_name = prefs.get("theme", "dark")
        self.compact = prefs.get("compact", False)
        self.session_mode = "main"
        self.transcript_summary = None
        self.goal = None
        self.goal_paused = False
        self.goal_started_at = None
        self.goal_elapsed_before_pause = 0.0
        self.system = (
            "You are concise, accurate, and practical. Answer the user directly. "
            "Do not bring up Composio, MCP, or third-party integrations unless the user "
            "explicitly asks to use an external app or service."
        )
        self._last_touch = 0.0
        self.session_id = None
        self._session_created_at = None
        self._resumed_session = False
        self._session_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self.custom_title = None

    def display_title(self):
        return session_display_title(self.history, self.custom_title)

    def rename_session(self, title):
        title = (title or "").strip()
        self.custom_title = title or None
        self.persist_session()
        return self.display_title()

    def update_api_key(self, key):
        key = (key or "").strip()
        if not key:
            raise ValueError(f"Missing {API_KEY}")
        save_api_key(key)
        self.client = OpenRouter(api_key=key, server_url=API_URL)

    def update_composio_key(self, key):
        save_composio_key(key)
        self.mcp = MCP(self.cache)
        self.refresh_mcp_tools()
        self.refresh_status(invalidate=True)

    def stop_generation(self):
        if self.busy:
            self._stop_requested.set()

    def _stopped(self):
        return self._stop_requested.is_set()

    def _clear_stop(self):
        self._stop_requested.clear()

    def _finalize_stream_blocks(self, out, think, out_i, think_i, spin_i, end_spin):
        end_spin()
        with self._frag_lock:
            if out_i is not None and out_i < len(self.blocks) and out.strip():
                self.blocks[out_i].text = out.rstrip() + "\n"
                self.blocks[out_i].kind = "md"
            if think.strip() and not self.compact:
                block = UiBlock("think", think.rstrip() + "\n")
                if think_i is not None and think_i < len(self.blocks):
                    self.blocks[think_i] = block
                elif out_i is not None and out_i < len(self.blocks):
                    self.blocks.insert(out_i, block)
                else:
                    self.blocks.append(block)
            elif think_i is not None and think_i < len(self.blocks):
                self.blocks.pop(think_i)

    def session_file(self):
        if not self.session_id:
            return None
        return SESSIONS_DIR / f"{self.session_id}.json"

    def session_payload(self):
        return {
            "id": self.session_id,
            "title": self.display_title(),
            "custom_title": self.custom_title,
            "created_at": self._session_created_at or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "updated_at": getattr(self, "_last_activity", None) or time.strftime("%Y-%m-%dT%H:%M:%S"),
            "history": self.history,
            "transcript_summary": self.transcript_summary,
            "model": self.model,
            "reasoning_level": self.reasoning_level,
            "session_mode": self.session_mode,
            "goal": self.goal,
            "goal_paused": self.goal_paused,
            "goal_elapsed_before_pause": self.goal_elapsed_before_pause,
            "system": self.system,
            "last": self.last,
            "session_usage": {
                "input": self.session_usage.input,
                "output": self.session_usage.output,
                "cached": self.session_usage.cached,
            },
            "attachments": [
                {"id": a.id, "path": str(a.path), "name": a.name}
                for a in self.attachments
            ],
        }

    def persist_session(self):
        if not self.session_id:
            return
        with self._session_lock:
            path = self.session_file()
            if not path:
                return
            write_json_atomic(path, self.session_payload())
            save_prefs({"last_session_id": self.session_id})

    def begin_session(self):
        self.session_id = make_session_id()
        self._session_created_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._last_activity = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._resumed_session = False
        self.custom_title = None
        self.persist_session()

    def _restore_attachment(self, path, att_id=None):
        p = Path(path).expanduser()
        if not p.exists():
            return False
        use_id = att_id if att_id is not None else self.aid
        att = self.indexer.load(str(p), use_id)
        if not att:
            return False
        self.attachments.append(att)
        self.aid = max(self.aid, att.id + 1)
        return True

    def apply_saved_session(self, data):
        self.session_id = data.get("id") or make_session_id()
        self._session_created_at = data.get("created_at") or time.strftime("%Y-%m-%dT%H:%M:%S")
        self._last_activity = data.get("updated_at") or time.strftime("%Y-%m-%dT%H:%M:%S")
        self.history = list(data.get("history") or [])
        self.custom_title = (data.get("custom_title") or "").strip() or None
        self.transcript_summary = data.get("transcript_summary")
        if data.get("model"):
            self.model = data["model"]
        if data.get("reasoning_level"):
            self.reasoning_level = normalize_reasoning_for_model(self.model, data.get("reasoning_level"))
        self.session_mode = data.get("session_mode") or "main"
        self.goal = data.get("goal")
        self.goal_paused = bool(data.get("goal_paused"))
        self.goal_elapsed_before_pause = float(data.get("goal_elapsed_before_pause") or 0)
        self.goal_started_at = time.time() if self.goal and not self.goal_paused else None
        if data.get("system"):
            self.system = data["system"]
        self.last = data.get("last") or ""
        su = data.get("session_usage") or {}
        self.session_usage = Usage(
            input=int(su.get("input") or 0),
            output=int(su.get("output") or 0),
            cached=int(su.get("cached") or 0),
        )
        self.attachments = []
        self.aid = 1
        for att in data.get("attachments") or []:
            self._restore_attachment(att.get("path"), att.get("id"))
        self._resumed_session = True
        self.persist_session()

    def restore_session_ui(self):
        blocks = [
            UiBlock("text", BANNER + "\n", "class:label"),
            UiBlock("text", f"resumed [{self.session_id}]  ·  {len(self.history) // 2} turns\n", "class:dim"),
        ]
        blocks.append(UiBlock("text", "/attach to add files or folders\n", "class:dim"))
        blocks.append(UiBlock("welcome_model", self._welcome_model_text(), "class:dim"))
        for a in self.attachments:
            p = a.path
            if p.is_dir():
                line = f"Attached #{a.id}  {p.name}/  ·  {a.files} files  ·  {a.chars:,} chars"
            else:
                line = f"Attached #{a.id}  {p.name}  ·  {a.chars:,} chars"
            blocks.append(UiBlock("attach", line))
        if self.transcript_summary:
            blocks.append(UiBlock("notify", f"compact summary loaded ({len(self.transcript_summary):,} chars)", "class:dim"))
        for m in self.history:
            role = m.get("role")
            content = message_text(m.get("content", "")).strip()
            if not content:
                continue
            if role == "user":
                blocks.append(UiBlock("user", content))
                blocks.append(UiBlock("asst", ""))
            elif role == "assistant":
                blocks.append(UiBlock("md", content + "\n"))
        with self._frag_lock:
            self.blocks = blocks
        self.follow_output = False
        self._keep_at_top = True
        self.session_info()
        self.ui_invalidate()

    def sessions_cmd(self):
        sessions = list_saved_sessions()
        if not sessions:
            return self.info("no saved sessions — use HackClub AI → File → Resume Session to pick one on launch")
        self.ui("Saved sessions", "class:label")
        for i, s in enumerate(sessions[:20], 1):
            self.ui(f"  {format_session_line(s, i)}")
        self.info("resume on launch: HackClub AI → File → Resume Session  or  HackClub AI → File → Resume Session <id>")

    def rename_cmd(self, rest):
        title = (rest or "").strip()
        if not title and self.ui_delegate and hasattr(self.ui_delegate, "prompt_rename"):
            title = self.ui_delegate.prompt_rename(self.display_title())
        if not title:
            return self.warn("usage: /rename <title>")
        name = self.rename_session(title)
        if self.ui_delegate:
            self.ui_delegate.requestRefresh()
        return self.ok(f"renamed to: {name}")

    def ui_invalidate(self, scroll_bottom=False):
        if scroll_bottom:
            self.follow_output = True
            self._keep_at_top = False
            if self.ui_delegate:
                try:
                    self.ui_delegate.scroll_to_bottom()
                except Exception:
                    pass
        if self.ui_delegate:
            self.ui_delegate.requestRefresh()

    def refresh_status(self, invalidate=True):
        self._status_ver += 1
        if invalidate:
            if self.ui_delegate and hasattr(self.ui_delegate, "refresh_status_bar"):
                self.ui_delegate.refresh_status_bar()
            else:
                self.ui_invalidate()

    def follow_latest(self, force=False):
        now = time.time()
        if force or now - self._last_touch >= FOLLOW_MIN_S:
            self._last_touch = now
            self.follow_output = True
            self._keep_at_top = False
            self.ui_invalidate(scroll_bottom=True)

    def touch_body(self, scroll_bottom=False):
        now = time.time()
        if now - self._last_touch < STREAM_REDRAW_S:
            return
        self._last_touch = now
        self._body_ver += 1
        self.ui_invalidate(scroll_bottom=scroll_bottom)

    def _finish_stream_ui(self):
        self.ui_invalidate(scroll_bottom=True)

    def show_welcome(self):
        welcome = [
            UiBlock("text", BANNER + "\n", "class:label"),
            UiBlock("text", "/attach to add files or folders\n", "class:dim"),
            UiBlock("welcome_model", self._welcome_model_text(), "class:dim"),
        ]
        with self._frag_lock:
            self.blocks = welcome
            self._welcome_blocks = list(welcome)
        self.session_info()
        self.ui_invalidate()

    def submit_line(self, line):
        if self.busy:
            return
        line = normalize_input(line)
        if not line:
            return
        if line.lower() in {"/exit", "/quit", "exit", "quit"}:
            self.exit_cmd()
            return
        self._dispatch(line, sync=False)

    def _ensure_ui(self):
        if not hasattr(self, "_frag_lock"):
            self._frag_lock = threading.Lock()
        if not hasattr(self, "blocks"):
            self.blocks = []

    def ui(self, text, style="class:text", nl=True):
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("text", text + ("\n" if nl else ""), style))
        if self.ui_delegate:
            self.ui_delegate.requestRefresh()
    def notify(self, msg, style):
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("notify", msg + "\n", style))
        if self.ui_delegate:
            self.ui_delegate.requestRefresh()
    def body_width(self):
        if self.ui_delegate:
            try:
                return self.ui_delegate.body_width()
            except Exception:
                pass
        return 80
    def render_body(self):
        self._ensure_ui()
        _ = self._body_ver
        with self._frag_lock:
            blocks = list(self.blocks)
            welcome_blocks = getattr(self, "_welcome_blocks", None)
        if not blocks:
            return [("class:dim", "")]
        if welcome_blocks and any(b.kind == "user" for b in blocks):
            welcome_ids = {id(b) for b in welcome_blocks}
            blocks = [b for b in blocks if id(b) not in welcome_ids]
        width = self.body_width()
        if self.compact and len(blocks) > 48:
            blocks = blocks[-48:]
        out = []
        if OUTPUT_TOP_MARGIN:
            out.append(("class:text", LINE * OUTPUT_TOP_MARGIN))
        last = len(blocks) - 1
        for i, b in enumerate(blocks):
            nxt = blocks[i + 1].kind if i < last else None
            if b.kind == "user":
                prev_kind = blocks[i - 1].kind if i > 0 else None
                if i > 0 and prev_kind not in WELCOME_KINDS:
                    gap = NOTIFY_USER_GAP if prev_kind == "notify" else BLANK
                    out.append(("class:text", gap))
                rule = "─" * min(max(24, width - 4), 72)
                out.append(("class:sep", f"{rule}{LINE}"))
                out.append(("class:text", RULE_GAP))
                if self.compact:
                    t = re.sub(r"\s+", " ", b.text.strip())
                    if len(t) > 120:
                        t = t[:120] + "..."
                    out.append(("class:user_label", "You  "))
                    out.append(("class:user_msg", t + LINE))
                else:
                    out.append(("class:user_label", f"You{HEADER_GAP}"))
                    pad = " " * CONTENT_INDENT
                    for line in b.text.splitlines() or [""]:
                        out.append(("class:user_msg", pad + line + LINE))
                if nxt is not None:
                    out.append(("class:text", BLANK))
            elif b.kind == "asst":
                out.append(("class:asst_label", f"Assistant{HEADER_GAP}"))
            elif b.kind in ("md", "stream"):
                if b.kind == "stream":
                    pad = " " * CONTENT_INDENT
                    for line in b.text.splitlines() or [""]:
                        out.append(("class:text", pad + line + LINE))
                elif self.compact:
                    text = re.sub(r"\s+", " ", b.text.strip())
                    if len(text) > 240:
                        text = text[:240] + "..."
                    out.append(("class:user_msg", f"  {text}{LINE}"))
                else:
                    out.extend(md_to_fragments(b.text, width, indent=CONTENT_INDENT))
                    if not b.text.endswith("\n"):
                        out.append(("class:text", LINE))
            elif b.kind in ("think", "think_live"):
                if self.compact:
                    continue
                if b.text.strip():
                    pad = " " * THINK_INDENT
                    header = "Reasoning" if b.kind == "think_live" else "Reasoned"
                    out.append(("class:think_label", pad + f"{header}{HEADER_GAP}"))
                    out.extend(md_to_fragments(b.text, width, indent=THINK_INDENT, tone="think"))
                    if not b.text.endswith("\n"):
                        out.append(("class:text", LINE))
                    if nxt == "md":
                        nxt_text = blocks[i + 1].text.strip() if i + 1 < len(blocks) else "x"
                        nxt2 = blocks[i + 2].kind if i + 2 < len(blocks) else None
                        if not (not nxt_text and nxt2 == "notify"):
                            out.append(("class:text", THINK_REPLY_GAP))
            elif b.kind == "spin":
                out.append((b.style or "class:spin", "  " + b.text + LINE))
            elif b.kind == "attach":
                out.append(("class:attach", f"{BLANK}{b.text}{LINE}"))
            elif b.kind == "notify":
                prev_kind = blocks[i - 1].kind if i > 0 else None
                prev_text = blocks[i - 1].text.strip() if i > 0 else ""
                prev2_kind = blocks[i - 2].kind if i > 1 else None
                if prev_kind == "think" or (prev_kind == "md" and not prev_text and prev2_kind == "think"):
                    out.append(("class:text", THINK_TOOL_GAP))
                elif prev_kind in ("md", "think"):
                    out.append(("class:text", BLANK))
                out.append((b.style, b.text))
                if nxt is not None and nxt != "user":
                    out.append(("class:text", THINK_TOOL_GAP))
            else:
                out.append((b.style, b.text))
                if nxt is not None and b.kind in WELCOME_KINDS and nxt in WELCOME_KINDS:
                    continue
        return out
    def write_root(self):
        for a in self.attachments:
            if getattr(a, "path", None):
                p = Path(a.path).expanduser().resolve()
                return p if p.is_dir() else p.parent
        return Path.home()

    def resolve_fs_path(self, path):
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = self.write_root() / p
        return p

    def execute_fs_call(self, call):
        if call["action"] == "write":
            path = self.resolve_fs_path(call["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(call["content"], encoding="utf-8")
            return f"Wrote {len(call['content'])} bytes to {path}"
        if call["action"] == "run":
            r = subprocess.run(
                call["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.write_root()),
            )
            out = (r.stdout or "") + (r.stderr or "")
            return f"exit {r.returncode}\n{out[:15000]}".strip()
        raise ValueError(f"unknown fs action: {call.get('action')}")

    def info(self, msg): self.notify(msg, "class:dim")
    def ok(self, msg): self.notify(msg, "class:ok")
    def warn(self, msg): self.notify(msg, "class:warn")
    def err(self, msg): self.notify(msg, "class:error")
    def status_text(self):
        try:
            _ = self._status_ver
            if self.mcp.enabled and self.mcp.servers:
                mcp = "mcp connected"
            elif not self.mcp.servers:
                mcp = "no mcp"
            else:
                mcp = "mcp off"
            ctx = self.ctx_pct()
            tot_in = self.session_usage.input + self.usage.input
            tot_out = self.session_usage.output + self.usage.output
            tot_cached = self.session_usage.cached + self.usage.cached
            tok = f"in {tot_in}  out {tot_out}"
            if tot_cached:
                tok += f"  cached {tot_cached}"
            if self.compact:
                bits = [self.model_display_label(), f"ctx {ctx:.0f}%", mcp, tok]
                return " | ".join(bits)
            bits = [self.model_display_label(), f"ctx {ctx:.0f}%", mcp, f"turns {len(self.history)//2}", tok]
            if self.session_mode != "main":
                bits.insert(1, self.session_mode)
            if self.transcript_summary:
                bits.insert(1, "compact")
            left = "  ".join(bits)
            if self.goal:
                timer = self.format_goal_timer()
                right = f"⏱ {timer}" + (" paused" if self.goal_paused else "")
                width = max(len(left) + len(right) + 2, self.body_width())
                pad = max(2, width - len(left) - len(right))
                return left + (" " * pad) + right
            return left
        except Exception:
            return "in 0  out 0"
    def usage_summary(self):
        def _h(n):
            n = int(n or 0)
            if n >= 1_000_000:
                return f"{n / 1_000_000:.1f}M"
            if n >= 1000:
                return f"{n / 1000:.1f}k"
            return str(n)
        try:
            ctx = self.ctx_pct()
            tot_in = self.session_usage.input + self.usage.input
            tot_out = self.session_usage.output + self.usage.output
            return f"ctx {ctx:.0f}%   ·   in {_h(tot_in)}   ·   out {_h(tot_out)}"
        except Exception:
            return "ctx 0%   ·   in 0   ·   out 0"
    def render_status(self):
        return [("class:status", self.status_text())]
    def apply_theme(self, name):
        if name not in THEMES:
            return self.warn(f"unknown theme: {name} (dark, light)")
        self.theme_name = name
        save_prefs({"theme": name, "compact": self.compact, "model": self.model})
        if self.ui_delegate:
            try:
                self.ui_delegate.apply_theme(name)
            except Exception:
                pass
        self.ui_invalidate()
        self.ok(f"theme: {name}")
    def max_history_msgs(self):
        return 6 if self.compact else MAX_TURNS * 2
    def max_ctx_limit(self):
        return MAX_CTX // 4 if self.compact else MAX_CTX
    def history_budget(self):
        return HISTORY_BUDGET // 4 if self.compact else HISTORY_BUDGET
    def history_window(self):
        # Most-recent-first selection bounded by both a message cap and a char budget,
        # so a few huge turns can't blow up per-request input on long-context chats.
        cap = self.max_history_msgs()
        budget = self.history_budget()
        recent = self.history[-cap:]
        chosen = []
        total = 0
        for m in reversed(recent):
            size = len(message_text(m.get("content", "")))
            if chosen and total + size > budget:
                break
            chosen.append(m)
            total += size
        chosen.reverse()
        # Never split a turn: if we start on an assistant reply with no preceding
        # user turn in-window, drop it so the window begins on a user message.
        if chosen and chosen[0].get("role") == "assistant" and len(chosen) > 1:
            chosen = chosen[1:]
        return chosen
    def live_input_chars(self):
        # Approximate size of the actual per-request input (attachments + summary +
        # in-window history), independent of cumulative session totals.
        hist = sum(len(message_text(m.get("content", ""))) for m in self.history_window())
        summ = len(self.transcript_summary or "")
        return self.ctx_chars() + hist + summ
    def live_ctx_pct(self):
        return min(100.0, (self.live_input_chars() // 4) / CTX_WINDOW * 100)
    def _trim_ui(self):
        with self._frag_lock:
            if len(self.blocks) > 48:
                self.blocks = self.blocks[-48:]
        if self.ui_delegate:
            self.ui_delegate.requestRefresh()
    def goal_elapsed_s(self):
        if not self.goal:
            return 0
        total = self.goal_elapsed_before_pause
        if self.goal_started_at and not self.goal_paused:
            total += time.time() - self.goal_started_at
        return total
    def format_goal_timer(self):
        s = int(self.goal_elapsed_s())
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m}:{sec:02d}"
    def mode_prompt(self):
        parts = []
        if self.session_mode in MODE_PROMPTS:
            parts.append(MODE_PROMPTS[self.session_mode])
        if self.goal and not self.goal_paused:
            parts.append(
                f"\n\nGOAL MODE — ACTIVE OBJECTIVE: {self.goal}\n"
                "You are in relentless execution mode for this objective.\n"
                "Stay tightly focused on the goal. Do NOT stop at partial progress, hand-wavy next steps, or suggestions.\n"
                "Keep working across turns until the goal is fully implemented and verified.\n"
                "If blocked, state the blocker briefly and immediately take the smallest action to unblock it.\n"
                "When the goal is truly complete, say GOAL COMPLETE and summarize what was implemented and how to verify it."
            )
        elif self.goal and self.goal_paused:
            parts.append(f"\n\nGOAL PAUSED: {self.goal}\nDo not advance the goal until the user resumes it.")
        return "".join(parts)
    def repo_root(self):
        for a in self.attachments:
            if a.path:
                root = git_root(a.path)
                if (root / ".git").exists():
                    return root
        return git_root(Path.cwd())
    def call_model(self, msgs, model=None):
        active = model or self.model
        out = ""
        for chunk in self.client.chat.send(
            model=active,
            messages=msgs,
            reasoning=self.reasoning_request(active),
            stream=True,
        ):
            if self._stopped():
                break
            self.read_usage(chunk, invalidate=False)
            for kind, piece in self.delta_parts(chunk):
                if kind != "reasoning":
                    out += piece
        return out.strip()
    def _clear_chat_ui(self):
        with self._frag_lock:
            keep = []
            for b in self.blocks:
                if b.kind in WELCOME_KINDS or b.kind == "attach" or b.kind == "notify":
                    keep.append(b)
                elif b.kind == "text" and (b.text.startswith("/attach")):
                    keep.append(b)
                elif b.kind == "welcome_model":
                    keep.append(b)
            self.blocks = keep
        if self.ui_delegate:
            self.ui_delegate.requestRefresh()
    def compact_transcript(self):
        if not self.history and not self.transcript_summary:
            return self.info("nothing to compact")
        self.info("summarizing transcript...")
        lines = []
        if self.transcript_summary:
            lines.append(f"PRIOR SUMMARY:\n{self.transcript_summary}")
        for m in self.history:
            role = m.get("role", "?").upper()
            lines.append(f"{role}: {message_text(m.get('content', ''))}")
        transcript = "\n\n".join(lines)
        prompt = (
            "Compress this conversation into a dense structured brief for future model context. "
            "Preserve decisions, constraints, open questions, current task state, file paths, and technical details. "
            "Use sections and bullets. Stay under 2000 words.\n\n" + transcript
        )
        try:
            summary = self.call_model([
                {"role": "system", "content": "You summarize chat transcripts without losing actionable detail."},
                {"role": "user", "content": prompt},
            ])
        except Exception as e:
            return self.err(f"compact failed: {e}")
        if self._stopped():
            return self.warn("generation stopped")
        if not summary:
            return self.err("compact failed: empty summary")
        self.transcript_summary = summary
        self.history.clear()
        self._clear_chat_ui()
        self.persist_session()
        self.info(f"transcript compacted ({len(summary):,} chars) — previous turns replaced by summary")
        self.refresh_status()
    def auto_compact_if_needed(self):
        # Fold the oldest turns into a rolling summary once live context crosses the
        # threshold. Unlike /compact this keeps the visible transcript intact and only
        # shrinks what is sent to the model, preserving detail in the summary.
        if self.session_mode == "side" or self.compact or self._stopped():
            return False
        try:
            if self.live_ctx_pct() < AUTO_COMPACT_PCT:
                return False
        except Exception:
            return False
        keep = max(2, AUTO_COMPACT_KEEP)
        if len(self.history) <= keep + 2:
            return False
        old = self.history[:-keep]
        recent = self.history[-keep:]
        lines = []
        if self.transcript_summary:
            lines.append(f"PRIOR SUMMARY:\n{self.transcript_summary}")
        for m in old:
            lines.append(f"{m.get('role', '?').upper()}: {message_text(m.get('content', ''))}")
        prompt = (
            "Update the running brief for this conversation so future turns stay grounded. "
            "Merge any prior summary with the new turns into one dense brief. "
            "Preserve decisions, constraints, open questions, task state, file paths, and key facts. "
            "Use sections and bullets. Stay under 1500 words.\n\n" + "\n\n".join(lines)
        )
        try:
            summary = self.call_model([
                {"role": "system", "content": "You maintain a compact running brief of a chat without losing actionable detail."},
                {"role": "user", "content": prompt},
            ])
        except Exception:
            return False
        if self._stopped() or not summary or not summary.strip():
            return False
        self.transcript_summary = summary.strip()
        self.history = recent
        self.persist_session()
        self.info(f"auto-compacted older turns to keep context lean (summary {len(summary):,} chars)")
        self.refresh_status()
        return True
    def side_cmd(self, rest):
        rest = (rest or "").strip()
        if not rest:
            return self.warn("usage: /side <question>")
        old = self.session_mode
        self.session_mode = "side"
        try:
            self.send(rest)
        finally:
            self.session_mode = old
    def plan_cmd(self, rest):
        self.session_mode = "main" if self.session_mode == "plan" else "plan"
        self.ok(f"plan mode: {'on' if self.session_mode == 'plan' else 'off'}")
    def grill_me_cmd(self, rest):
        rest = (rest or "").strip()
        prompt = GRILL_KICKOFF
        if rest:
            prompt += f"\n\nAdditional focus: {rest}"
        old = self.session_mode
        self.session_mode = "grill"
        try:
            self.send(prompt)
        finally:
            self.session_mode = old
    def _start_goal(self, text):
        self.goal = text.strip()
        self.goal_paused = False
        self.goal_started_at = time.time()
        self.goal_elapsed_before_pause = 0.0
        self.session_mode = "goal"
        self.refresh_status()
        self.ok(f"goal started — ⏱ {self.format_goal_timer()}")
        self.send(f"GOAL: {self.goal}\n\n{GOAL_KICKOFF}")
    def goal_cmd(self, rest):
        rest = (rest or "").strip()
        if not rest:
            return self.warn("usage: /goal <objective>")
        if rest == "clear":
            self.goal = None
            self.goal_started_at = None
            self.goal_elapsed_before_pause = 0.0
            self.goal_paused = False
            if self.session_mode == "goal":
                self.session_mode = "main"
            self.refresh_status()
            return self.info("goal cleared")
        if rest == "pause":
            if not self.goal:
                return self.info("no active goal")
            if not self.goal_paused:
                self.goal_elapsed_before_pause = self.goal_elapsed_s()
                self.goal_started_at = None
                self.goal_paused = True
                if self.session_mode == "goal":
                    self.session_mode = "main"
            self.refresh_status()
            return self.ok(f"goal paused — ⏱ {self.format_goal_timer()}")
        if rest == "resume":
            if not self.goal:
                return self.info("no active goal")
            if self.goal_paused:
                self.goal_started_at = time.time()
                self.goal_paused = False
                self.session_mode = "goal"
            self.refresh_status()
            return self.ok(f"goal resumed — ⏱ {self.format_goal_timer()}")
        if rest == "show":
            if not self.goal:
                return self.info("no active goal")
            state = "paused" if self.goal_paused else "active"
            return self.info(f"goal ({state}, ⏱ {self.format_goal_timer()}): {self.goal}")
        self._start_goal(rest)
    def diff_cmd(self, rest):
        root = self.repo_root()
        if not (root / ".git").exists():
            return self.err("not a git repository")
        sections = []
        for label, args in [
            ("unstaged", ["git", "-C", str(root), "diff"]),
            ("staged", ["git", "-C", str(root), "diff", "--cached"]),
        ]:
            code, out, err = run_cmd(args)
            if code not in (0, 1):
                return self.err(err or f"git diff failed ({label})")
            if out.strip():
                sections.append(f"## {label}\n```diff\n{out[:120000]}\n```")
        code, out, _ = run_cmd(["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"])
        if code == 0 and out.strip():
            untracked = out.strip().splitlines()
            chunks = []
            for rel in untracked[:40]:
                p = root / rel
                if p.is_file():
                    try:
                        body = p.read_text(errors="replace")
                    except Exception:
                        body = "(binary or unreadable)"
                    chunks.append(f"--- a/{rel}\n+++ b/{rel}\n{body[:8000]}")
            if chunks:
                sections.append("## untracked\n```diff\n" + "\n\n".join(chunks)[:120000] + "\n```")
        if not sections:
            return self.info("working tree clean — no diff")
        self.ui(f"Git diff — {root.name}", "class:label")
        for sec in sections:
            self.ui(sec)
    def init_cmd(self, rest):
        root = self.repo_root()
        target = root / "AGENTS.md"
        if target.exists() and rest != "force":
            return self.warn(f"AGENTS.md already exists at {target} — run `/init force` to overwrite")
        body = AGENTS_MD_TEMPLATE
        target.write_text(body, encoding="utf-8")
        self.ok(f"created {target}")
    def review_cmd(self, rest):
        prompt = REVIEW_PROMPT + (rest or "Review the attached files and folders.")
        return self.send(prompt)
    def yeet_cmd(self, rest):
        root = self.repo_root()
        if not (root / ".git").exists():
            return self.err("not a git repository")
        msg = rest.strip() or YEET_COMMIT_FALLBACK
        steps = []
        for label, args in [
            ("stage", ["git", "-C", str(root), "add", "-A"]),
            ("commit", ["git", "-C", str(root), "commit", "-m", msg]),
            ("push", ["git", "-C", str(root), "push"]),
        ]:
            code, out, err = run_cmd(args)
            text = (out or err).strip()
            if label == "commit" and code != 0 and "nothing to commit" in text.lower():
                return self.info("nothing to commit")
            if code != 0:
                return self.err(f"yeet failed at {label}: {text[:300]}")
            steps.append(f"{label}: ok")
        code, out, err = run_cmd(["gh", "pr", "create", "--fill"], cwd=root)
        pr_text = (out or err).strip()
        if code != 0:
            return self.warn("committed and pushed, but PR creation failed: " + pr_text[:300])
        self.ok("yeet complete — " + " · ".join(steps))
        if pr_text:
            self.info(pr_text)
    def exit_cmd(self):
        self.persist_session()
        self._auto_refresh_attachments()
        if self.ui_delegate:
            self.ui_delegate.request_exit()
    def show_user(self, text):
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("user", text.strip()))
        self.follow_latest(force=True)
    def show_assistant_start(self):
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("asst", ""))
        self.follow_latest(force=True)
    def model_label(self):
        for name, mid in MODELS:
            if mid == self.model: return name
        return self.model
    def reasoning_label(self, model=None, value=None):
        return reasoning_label_for_model(model or self.model, self.reasoning_level if value is None else value)
    def model_display_label(self):
        return f"{self.model_label()} [{self.reasoning_label()}]"
    def _welcome_model_text(self):
        return f"model: {self.model_display_label()}  ·  /help  ·  /model to switch\n"
    def _sync_welcome_model(self):
        text = self._welcome_model_text()
        updated = False
        with self._frag_lock:
            for i, b in enumerate(self.blocks):
                if b.kind == "welcome_model" or (
                    b.kind == "text" and b.text.startswith("model:") and "/model to switch" in b.text
                ):
                    self.blocks[i] = UiBlock("welcome_model", text, b.style)
                    updated = True
                    break
        if updated and self.ui_delegate:
            self.ui_delegate.requestRefresh()
    def ctx_chars(self):
        return sum(a.chars for a in self.attachments if a.kind == "text")
    def ctx_pct(self):
        hist = sum(len(str(m.get("content", ""))) for m in self.history)
        pending = sum(len(b.text) for b in self.blocks if b.kind in {"md", "think", "text"})
        est = (self.ctx_chars() + hist + pending) // 4 + self.session_usage.input + self.usage.input
        return min(100.0, est / CTX_WINDOW * 100)
    def session_info(self):
        if not self.mcp.servers:
            self.warn(f"mcp unavailable — export {COMPOSIO_KEY} or add {MCP_FILE}")
        elif self.mcp.enabled:
            self.info("mcp connected")
    def _ask_model_dialog(self):
        if self.ui_delegate:
            return self.ui_delegate.pick_model()
        return None
    def reasoning_request(self, model=None):
        active_model = model or self.model
        effort = normalize_reasoning_for_model(active_model, self.reasoning_level)
        if self.goal or self.session_mode == "goal":
            if effort == "high":
                effort = "medium"
        return {"effort": effort}
    def _apply_model(self, val, reasoning=None):
        if not val:
            return
        self.model = val
        self.reasoning_level = normalize_reasoning_for_model(val, reasoning)
        save_prefs({"model": val, "reasoning": self.reasoning_level})
        self._sync_welcome_model()
        self.ok(f"model: {self.model_display_label()}")
        self.refresh_status()
        if self.ui_delegate and hasattr(self.ui_delegate, "sync_model_pickers"):
            self.ui_delegate.sync_model_pickers()
    def set_model(self, rest):
        q = rest.strip()
        if not q:
            return self.info("usage: /model <name> [variant]  ·  /model custom <openrouter-id> [variant]")
        parsed = parse_model_command(q)
        if parsed["kind"] == "variants":
            model_id = parsed["model_id"]
            reasoning = None
            variant_q = parsed.get("variant_q", "")
            if variant_q:
                allowed = {effort for _, effort in reasoning_variants_for_model(model_id)}
                aliases = {label.lower() for label, _ in reasoning_variants_for_model(model_id)}
                last = variant_q.split()[-1]
                if last in allowed or last in aliases:
                    reasoning = normalize_reasoning_for_model(model_id, last)
            return self._apply_model(model_id, reasoning)
        if parsed["kind"] == "custom_id":
            return self.warn("usage: /model custom <openrouter-model-id> [variant]")
        mid, _, rest2 = split_model_query(q)
        reasoning = None
        if mid and rest2:
            last = rest2.split()[-1].lower()
            allowed = {effort for _, effort in reasoning_variants_for_model(mid)}
            aliases = {label.lower() for label, _ in reasoning_variants_for_model(mid)}
            if last in allowed or last in aliases:
                reasoning = normalize_reasoning_for_model(mid, last)
        if mid == "custom":
            return self.warn("usage: /model custom <openrouter-model-id> [variant]")
        if not mid:
            mid = q.split()[0]
        return self._apply_model(mid, reasoning)
    def schedule_pick_model(self):
        val = self._ask_model_dialog()
        self._apply_model(val)
    def pick_attach(self):
        if self.ui_delegate:
            kind, path = self.ui_delegate.pick_attach_kind_and_path()
            if path:
                self.attach(path)
            return
        path = pick_macos_path("file")
        if path:
            self.attach(path)

    def _dispatch(self, line, sync=False):
        def work():
            self._clear_stop()
            self.busy = True
            if self.ui_delegate:
                try:
                    self.ui_delegate.set_busy(True)
                except Exception:
                    pass
            try:
                self.route(line)
            except Exception as e:
                self.err(str(e))
            finally:
                self.busy = False
                if self.ui_delegate:
                    try:
                        self.ui_delegate.set_busy(False)
                    except Exception:
                        pass
                if not sync:
                    self._finish_stream_ui()
                else:
                    self.ui_invalidate()
        if sync:
            work()
        else:
            threading.Thread(target=work, daemon=True).start()
    def route(self, raw):
        if not raw.startswith("/"):
            return self.send(raw)
        cmd, _, rest = raw.partition(" "); cmd = cmd.lower(); rest = rest.strip()
        if cmd == "/help": return self.help()
        if cmd == "/skills": return self.skills()
        if cmd == "/theme": return self.theme_cmd(rest)
        if cmd == "/compact": return self.compact_transcript()
        if cmd == "/side": return self.side_cmd(rest)
        if cmd == "/plan": return self.plan_cmd(rest)
        if cmd == "/goal": return self.goal_cmd(rest)
        if cmd in {"/grill-me", "/grill"}:
            if cmd == "/grill" and rest.lower().startswith("me"):
                rest = rest[2:].strip()
            return self.grill_me_cmd(rest)
        if cmd == "/diff": return self.diff_cmd(rest)
        if cmd == "/init": return self.init_cmd(rest)
        if cmd == "/review": return self.review_cmd(rest)
        if cmd == "/yeet": return self.yeet_cmd(rest)
        if cmd in {"/exit", "/quit"}: return self.exit_cmd()
        if cmd == "/model":
            return self.set_model(rest)
        if cmd == "/clear":
            self._clear_chat_ui()
            self.refresh_status()
            return self.info("chat view cleared — context memory retained")
        if cmd == "/attach":
            if rest:
                return self.attach(rest)
            return self.pick_attach()
        if cmd == "/drop": return self.drop(rest)
        if cmd == "/context": return self.context()
        if cmd == "/save": return self.save(rest or "response.md")
        if cmd == "/copy": return self.copy_last()
        if cmd == "/export": return self.export_chat(rest)
        if cmd == "/system": return self.set_system(rest)
        if cmd == "/mcp": return self.mcp_cmd(rest)
        if cmd == "/cache": return self.cache_cmd(rest)
        if cmd == "/sessions": return self.sessions_cmd()
        if cmd == "/rename": return self.rename_cmd(rest)
        if cmd[1:] in SKILLS:
            name = cmd[1:]
            if rest:
                return self.send(SKILLS.get(name, "") + rest)
            return self.schedule_ask_text(name)
        if cmd.startswith("/skill:"):
            name = SKILL_ALIASES.get(cmd.split(":", 1)[1], cmd.split(":", 1)[1])
            if rest:
                return self.send(SKILLS.get(name, "") + rest)
            return self.schedule_ask_text(name)
        return self.send(raw)
    def schedule_ask_text(self, skill_name):
        prompt = ""
        if self.ui_delegate:
            prompt = self.ui_delegate.ask_text(f"Skill: {skill_name}", f"Prompt for {skill_name}:")
        self.send(SKILLS.get(skill_name, "") + prompt)
    def attach(self, path):
        raw = (path or "").strip().strip('"').strip("'")
        if not raw:
            return self.err("no path given")
        p = Path(raw).expanduser()
        try:
            p = p.resolve()
        except Exception:
            pass
        if not p.exists():
            return self.err(f"path not found: {raw}")
        att = self.indexer.load(str(p), self.aid)
        if not att:
            if p.is_dir():
                return self.err(f"folder empty or no readable text files: {p.name}")
            ext = p.suffix.lower() or "(none)"
            if ext not in TEXT_EXT | {".docx"}:
                return self.err(f"could not read file: {p.name} — unsupported type {ext}")
            try:
                size = p.stat().st_size
                if ext == ".docx" and size > MAX_DOCX_FILE:
                    return self.err(f"could not read file: {p.name} — docx too large ({size/1024/1024:.1f}MB > {MAX_DOCX_FILE/1024/1024:.0f}MB limit, raise HC_MAX_DOCX_FILE to override)")
                if ext != ".docx" and size > MAX_FILE:
                    return self.err(f"could not read file: {p.name} — too large ({size/1024/1024:.1f}MB > {MAX_FILE/1024/1024:.1f}MB limit, raise HC_MAX_FILE to override)")
            except Exception:
                pass
            return self.err(f"could not read file: {p.name} — file may be corrupted, encrypted, or empty")
        self.attachments.append(att); self.aid += 1
        self.refresh_status()
        if p.is_dir():
            line = f"Attached #{att.id}  {p.name}/  ·  {att.files} files  ·  {att.chars:,} chars"
        else:
            line = f"Attached #{att.id}  {p.name}  ·  {att.chars:,} chars"
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("attach", line))
        if self.ui_delegate:
            self.ui_delegate.requestRefresh()
    def drop(self, target):
        if not target or target == "all":
            self.attachments.clear()
            return self.info("attachments cleared")
        self.attachments = [a for a in self.attachments if str(a.id) != target.lstrip("#")]
    def save(self, path):
        if not self.last: return self.warn("nothing to save")
        Path(path).expanduser().write_text(self.last, encoding="utf-8")
        self.ok(f"saved {path}")
    def copy_last(self):
        if not self.last:
            return self.warn("nothing to copy")
        ok, err = copy_to_clipboard(self.last)
        if ok:
            chars = len(self.last)
            return self.ok(f"copied last reply ({chars:,} chars)")
        return self.err(err or "copy failed")
    def export_messages(self):
        with self._frag_lock:
            blocks = list(self.blocks)
        msgs = []
        user_text = None
        asst_parts = []
        for b in blocks:
            if b.kind == "user":
                if user_text is not None:
                    msgs.append({"role": "user", "content": user_text})
                    if asst_parts:
                        msgs.append({"role": "assistant", "content": "\n\n".join(asst_parts).strip()})
                user_text = b.text.strip()
                asst_parts = []
            elif b.kind == "md" and b.text.strip():
                asst_parts.append(b.text.strip())
            elif b.kind == "think" and b.text.strip() and not self.compact:
                asst_parts.append(b.text.strip())
        if user_text is not None:
            msgs.append({"role": "user", "content": user_text})
            if asst_parts:
                msgs.append({"role": "assistant", "content": "\n\n".join(asst_parts).strip()})
        if len(msgs) >= len(self.history):
            return msgs
        return list(self.history)
    def format_chat_export(self, fmt="md", messages=None):
        messages = messages if messages is not None else self.history
        if fmt == "json":
            return json.dumps({
                "app": BANNER,
                "model": self.model,
                "model_label": self.model_label(),
                "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "messages": messages,
            }, indent=2, ensure_ascii=False)
        lines = [
            f"# {BANNER} chat export\n",
            f"model: {self.model_label()}\n",
            f"exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        ]
        for msg in messages:
            role = msg.get("role", "?")
            label = {"user": "You", "assistant": "Assistant"}.get(role, role.title())
            body = message_text(msg.get("content", "")).strip()
            if not body:
                continue
            lines.append(f"\n## {label}\n\n{body}\n")
        return "".join(lines)
    def export_chat(self, rest):
        rest = (rest or "").strip()
        fmt = "md"
        if rest.lower().startswith("json"):
            fmt = "json"
            rest = rest[4:].strip()
        messages = self.export_messages()
        if not messages:
            return self.warn("nothing to export")
        if rest:
            out = Path(rest).expanduser()
            if out.suffix.lower() not in {".md", ".json"}:
                out = out.with_suffix(".json" if fmt == "json" else ".md")
        else:
            out = export_download_dir() / export_default_name(fmt)
        try:
            body = self.format_chat_export(fmt, messages)
            out = write_export_file(out, body)
        except Exception as e:
            return self.err(f"export failed: {e}")
        turns = sum(1 for m in messages if m.get("role") == "user")
        self.ok(f"saved to Downloads → {out.name}")
    def set_system(self, text):
        if not text:
            self.ui("system", "class:label")
            self.ui(self.system, "class:text")
            return
        self.system = text
        self.ok("system updated")
    def mcp_cmd(self, rest):
        if not self.mcp.servers:
            return self.warn(f"mcp unavailable — export {COMPOSIO_KEY} or add {MCP_FILE}")
        verbose = rest.lower() in {"verbose", "v", "full"}
        tools = [t for t in self.mcp.tools() if t.get("name") != "ERROR"]
        if not tools:
            return self.warn("no mcp tools available")
        self.ui("MCP servers", "class:label")
        for name, srv in self.mcp.servers.items():
            cfg = srv.cfg if hasattr(srv, "cfg") else {}
            kind = "stdio" if "command" in cfg else "http"
            line = f"  {name}  [{kind}]"
            if verbose:
                if "url" in cfg:
                    line += f"  url={cfg.get('url')}"
                if "command" in cfg:
                    line += f"  cmd={' '.join([cfg.get('command', '')] + cfg.get('args', []))}"
            self.ui(line)
        self.ui("MCP tools", "class:label")
        for x in tools:
            desc = str(x.get("description") or "")
            if verbose:
                schema = x.get("inputSchema") or {}
                props = list((schema.get("properties") or {}).keys())[:8]
                extra = f"  schema={props}" if props else ""
                self.ui(f"  {x['server']}.{x['name']:<28} {desc[:120]}{extra}")
            else:
                self.ui(f"  {x['server']}.{x['name']:<28} {desc[:64]}")
        if verbose:
            self.info(f"mcp enabled={self.mcp.enabled}  servers={len(self.mcp.servers)}  tools={len(tools)}")
    def cache_cmd(self, rest):
        rest = (rest or "").strip()
        if rest == "clear":
            self.cache.clear()
            return self.info("cache cleared")
        if rest in ("list", "ls"):
            ws = self.cache.cached_folders()
            if not ws:
                return self.info("no cached folders")
            self.ui("Cached folders", "class:label")
            for w in ws[:30]:
                age = time.time() - w["mtime"]
                age_s = f"{int(age)}s" if age < 60 else f"{int(age/60)}m" if age < 3600 else f"{int(age/3600)}h" if age < 86400 else f"{int(age/86400)}d"
                self.ui(f"  {w['name']}  ·  {w['files']} files  ·  {w['chars']:,} chars  ·  {age_s} ago")
            return
        n, b = self.cache.stats()
        ws_n = len(self.cache.cached_folders())
        self.info(f"cache: {n} entries ({ws_n} folders), {b:,} bytes at {CACHE_DIR}  ·  /cache list  /cache clear")
    def _auto_refresh_attachments(self):
        if not self.attachments: return
        for i, a in enumerate(self.attachments):
            if a.kind != "text" or not a.path or not a.path.is_dir(): continue
            try:
                if not a.path.exists(): continue
                new_att = self.indexer.load(str(a.path), a.id)
                if new_att and new_att.content != a.content:
                    self.attachments[i] = new_att
            except Exception: pass
    def context(self):
        if not self.attachments:
            return self.info("no attachments")
        for a in self.attachments:
            kind = "folder" if a.path.is_dir() else "file"
            self.ui(f"  #{a.id}  [{kind}]  {a.name}  {a.files} files  {a.chars:,} chars  {a.path}")
    def help(self):
        self.ui("Commands", "class:label")
        for line in [
            "/model [name] [variant]  switch model + reasoning",
            "/model custom <id> [variant]  use any OpenRouter model id",
            "/compact            summarize transcript and replace chat context",
            "/side <question>     ask a side question (not added to main history)",
            "/plan               toggle planning mode",
            "/goal <objective>     start relentless execution + timer",
            "/goal pause|resume|clear|show  control active goal",
            "/grill-me (/grill)  immediately stress-test the current plan",
            "/diff               show live git diff (staged, unstaged, untracked)",
            "/init [force]       scaffold AGENTS.md in attached folder or home",
            "/review [focus]     full project review from attachments",
            "/yeet [message]     stage, commit, push, and open a GitHub PR",
            "/attach [path]      attach file or folder",
            "/                slash menu — ↑↓ navigate · Tab or Enter to complete",
            "Enter              send  ·  Ctrl+J new line",
            "Esc                stop generation while streaming",
            "/debug /build ...   direct skill commands",
            "/mcp [verbose]      list MCP servers/tools",
            "/sessions            list saved sessions (resume via HackClub AI → File → Resume Session)",
            "/clear              clear chat view (keeps compact summary/context)",
            "/exit (/quit)       quit",
        ]:
            self.ui(f"  {line}")
    def skills(self):
        self.ui("Skills", "class:label")
        for k, v in SKILLS.items():
            self.ui(f"  /{k:<10} {v.split('.')[0]}")
    def is_anthropic_model(self, model=None):
        m = (model or self.model or "").lower()
        return "claude" in m or "anthropic" in m
    def messages(self, prompt, model=None):
        # Input-token minimization:
        #  - Only send the (large) filesystem instructions when the turn actually needs them.
        #  - For Anthropic models, mark the stable prefix (system, attached context, summary,
        #    and the prior-turn history) with cache_control so it bills as cheap cached input
        #    instead of full-price input tokens on every turn.
        anthropic = self.is_anthropic_model(model)
        system = self.system + self.mode_prompt()
        if user_wants_fs(prompt, self):
            system += EXECUTION_RULES + local_fs_prompt(self.write_root())
        if self.mcp.enabled and self.mcp.servers and user_wants_mcp(prompt):
            system += mcp_integration_prompt(self.mcp, prompt)

        msgs = [{"role": "system", "content": system}]

        ctx_limit = self.max_ctx_limit()
        texts = [str(a.content) for a in self.attachments if a.kind == "text"]
        images = [{"type": "image_url", "image_url": {"url": f"data:{a.content['mime']};base64,{a.content['data']}"}} for a in self.attachments if a.kind == "image"]
        if texts:
            context_text = "\n\n".join(texts)[:ctx_limit]
            intro = ("The following attached context is stable across turns — it is the same on every turn until "
                     "files change. Refer back to it as needed; do not ask the user to re-paste it.\n\n")
            ctx_payload = intro + context_text
            if anthropic:
                ws_content = [{"type": "text", "text": ctx_payload, "cache_control": {"type": "ephemeral"}}]
                msgs.append({"role": "user", "content": ws_content})
            else:
                msgs.append({"role": "user", "content": ctx_payload})
            msgs.append({"role": "assistant", "content": "Acknowledged. I'll use the attached files as context for this conversation."})
        if self.transcript_summary:
            summary_text = "Compacted conversation summary from earlier in this session:\n\n" + self.transcript_summary
            if anthropic:
                msgs.append({"role": "user", "content": [
                    {"type": "text", "text": summary_text, "cache_control": {"type": "ephemeral"}}]})
            else:
                msgs.append({"role": "user", "content": summary_text})
            msgs.append({"role": "assistant", "content": "Acknowledged. I'll treat that summary as prior session context."})

        hist = self.history_window()
        if anthropic and hist:
            # Cache everything up to and including the previous turn; only the new prompt is uncached.
            cached_last = dict(hist[-1])
            if isinstance(cached_last.get("content"), str):
                cached_last["content"] = [{"type": "text", "text": cached_last["content"],
                                           "cache_control": {"type": "ephemeral"}}]
                hist = hist[:-1] + [cached_last]
        msgs += hist

        if images:
            msgs.append({"role": "user", "content": [{"type": "text", "text": prompt}, *images]})
        else:
            msgs.append({"role": "user", "content": prompt})
        return msgs
    def theme_cmd(self, rest):
        name = (rest or "").strip().lower()
        if not name:
            return self.ok(f"theme: {self.theme_name} (dark, light)")
        return self.ui_delegately_theme(name)
    def send(self, prompt):
        try:
            self._clear_stop()
            self._keep_at_top = False
            self.follow_output = True
            self.usage = Usage()
            self.refresh_status()
            self.show_user(prompt)
            msgs = self.messages(prompt, model=self.model)
            final = ""
            mcp_task = self.mcp.enabled and bool(self.mcp.servers) and user_wants_mcp(prompt)
            mcp_calls = 0
            nudges = 0
            self.show_assistant_start()
            fs_calls = 0
            fs_nudges = 0
            fs_task = user_wants_fs(prompt, self)
            for _ in range(FS_MAX_STEPS):
                if self._stopped():
                    break
                out, think = self.stream_text(msgs)
                if self._stopped():
                    final = out
                    break
                fs_call = parse_fs_call(out)
                if fs_call:
                    if self._stopped():
                        final = out
                        break
                    fs_calls += 1
                    self._hide_fs_json_block()
                    label = fs_call.get("path") or fs_call.get("command", "file")
                    self.info(f"fs: {label} ...")
                    try:
                        note = self.execute_fs_call(fs_call)
                        self.ok(note.split("\n")[0][:120])
                    except Exception as e:
                        note = "FS error: " + str(e)
                        self.err(str(e))
                    msgs += [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": note + "\n\n" + fs_continue_message()},
                    ]
                    continue
                call = parse_mcp_call(out)
                if call and self.mcp.enabled:
                    if self._stopped():
                        final = out
                        break
                    nudges = 0
                    self._hide_mcp_json_block()
                    tool_label = call["tool"]
                    self.info(f"running {tool_label} ...")
                    try:
                        result = self.mcp.call(tool_label, call.get("arguments", {}))
                        body = result.get("content") if isinstance(result, dict) else result
                        if isinstance(body, list):
                            parts = [p.get("text", "") for p in body if isinstance(p, dict) and p.get("text")]
                            body = "\n".join(parts) if parts else result
                        note = "MCP result for " + tool_label + ":\n" + json.dumps(body, ensure_ascii=False)[:20000]
                    except Exception as e:
                        note = "MCP error for " + tool_label + ": " + str(e)
                    mcp_calls += 1
                    msgs += [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": note + "\n\n" + mcp_continue_message()},
                    ]
                    continue
                if fs_task and fs_nudges < FS_MAX_NUDGES and looks_like_code_without_fs(out):
                    fs_nudges += 1
                    msgs += [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": fs_nudge_message(fs_nudges)},
                    ]
                    continue
                if mcp_task and nudges < MCP_MAX_NUDGES and out.strip():
                    nudges += 1
                    self._hide_mcp_json_block()
                    msgs += [
                        {"role": "assistant", "content": out},
                        {"role": "user", "content": mcp_nudge_message(nudges)},
                    ]
                    continue
                final = out
                break
            if self._stopped():
                self.warn("generation stopped")
            if mcp_task and mcp_calls == 0 and not self._stopped():
                self.warn("no tools were executed — the reply may not have actually done anything")
            if final.strip():
                self._fill_usage_fallback(prompt, msgs, final)
                self.last = final
                if self.session_mode != "side":
                    self.history += [{"role": "user", "content": prompt}, {"role": "assistant", "content": final}]
                    self.history = self.history[-self.max_history_msgs():]
                self.session_usage.input += self.usage.input
                self.session_usage.output += self.usage.output
                self.session_usage.cached += self.usage.cached
                self._auto_refresh_attachments()
                self._last_activity = time.strftime("%Y-%m-%dT%H:%M:%S")
                self.persist_session()
                self.refresh_status(invalidate=True)
                if not self._stopped():
                    self.auto_compact_if_needed()
        except Exception as e:
            self.err(str(e))
    def stream_text(self, msgs, model=None, _is_fallback=False):
        active_model = model or self.model
        self._ensure_ui()
        out = ""
        think = ""
        think_i = None
        out_i = None
        with self._frag_lock:
            spin_i = len(self.blocks)
            base = "Thinking" if not _is_fallback else f"Thinking · fallback {active_model}"
            self.blocks.append(UiBlock("spin", SPINNER_BAR[0] + "  " + base, "class:spin"))
        self.follow_latest(force=True)
        stop = threading.Event()
        def spin():
            i = 0
            # Switch label to "Writing" once response text has started streaming.
            while not stop.wait(0.07):
                with self._frag_lock:
                    if spin_i is None or spin_i >= len(self.blocks) or self.blocks[spin_i].kind != "spin":
                        break
                    verb = "Writing" if out_i is not None else base
                    dots = SPINNER_DOTS[(i // 4) % len(SPINNER_DOTS)]
                    glyph = SPINNER_BAR[i % len(SPINNER_BAR)]
                    self.blocks[spin_i] = UiBlock("spin", f"{glyph}  {verb}{dots}", "class:spin")
                i += 1
        worker = threading.Thread(target=spin, daemon=True)
        worker.start()
        def end_spin():
            nonlocal spin_i
            stop.set()
            worker.join(timeout=0.3)
            with self._frag_lock:
                if spin_i is not None and spin_i < len(self.blocks) and self.blocks[spin_i].kind == "spin":
                    self.blocks.pop(spin_i)
            spin_i = None
        try:
            for chunk in self.client.chat.send(
                model=active_model,
                messages=msgs,
                reasoning=self.reasoning_request(active_model),
                stream=True,
            ):
                if self._stopped():
                    break
                self.read_usage(chunk, invalidate=False)
                for kind, piece in self.delta_parts(chunk):
                    if kind == "reasoning":
                        think += piece
                        if not self.compact:
                            # Stream reasoning live, inserted just above the working
                            # indicator so the spinner stays pinned at the bottom.
                            with self._frag_lock:
                                if think_i is None:
                                    think_i = spin_i if spin_i is not None else len(self.blocks)
                                    self.blocks.insert(think_i, UiBlock("think_live", think))
                                    if spin_i is not None:
                                        spin_i += 1
                                elif think_i < len(self.blocks):
                                    self.blocks[think_i].text = think
                            self.touch_body(scroll_bottom=True)
                        continue
                    if out_i is None:
                        end_spin()
                        with self._frag_lock:
                            out_i = len(self.blocks)
                            self.blocks.append(UiBlock("stream", ""))
                    out += piece
                    with self._frag_lock:
                        self.blocks[out_i].text = out
                    self.touch_body(scroll_bottom=True)
            self.refresh_status(invalidate=True)
            self._finalize_stream_blocks(out, think, out_i, think_i, spin_i, end_spin)
            if self._stopped():
                return out, think
        except Exception as e:
            end_spin()
            if self._stopped():
                self._finalize_stream_blocks(out, think, out_i, think_i, spin_i, lambda: None)
                return out, think
            with self._frag_lock:
                if out_i is not None and out_i < len(self.blocks):
                    self.blocks.pop(out_i)
                    out_i = None
                if think_i is not None and think_i < len(self.blocks):
                    self.blocks.pop(think_i)
                    think_i = None
            reason = self._classify_error(e)
            if not _is_fallback and active_model != FALLBACK_MODEL and FALLBACK_MODEL and not self._stopped():
                self.warn(f"primary model failed ({reason}: {str(e)[:160]}) — retrying with fallback {FALLBACK_MODEL}")
                self.stream_i = None
                return self.stream_text(msgs, model=FALLBACK_MODEL, _is_fallback=True)
            out = f"Request failed: {e}"
            self.err(out)
        finally:
            self.stream_i = None
        return out, think
    def _classify_error(self, e):
        s = str(e).lower()
        if "429" in s or "rate" in s and "limit" in s: return "rate limited"
        if "401" in s or "403" in s or "unauthorized" in s: return "auth error"
        if "404" in s or "not found" in s: return "model not found"
        if "timeout" in s or "timed out" in s: return "timeout"
        if "5" in s[:4] and ("502" in s or "503" in s or "504" in s or "500" in s): return "upstream server error"
        if "connection" in s or "network" in s: return "network error"
        return "error"
    def _hide_fs_json_block(self):
        with self._frag_lock:
            for i in range(len(self.blocks) - 1, -1, -1):
                b = self.blocks[i]
                if b.kind in {"md", "text", "think", "stream"} and parse_fs_call(b.text):
                    self.blocks[i] = UiBlock(b.kind, "")
                    return

    def _hide_mcp_json_block(self):
        with self._frag_lock:
            for i in range(len(self.blocks) - 1, -1, -1):
                b = self.blocks[i]
                if b.kind in {"md", "text", "think", "stream"} and parse_mcp_call(b.text):
                    self.blocks[i] = UiBlock(b.kind, "")
                    return
    def delta_parts(self, chunk):
        try:
            d = chunk.choices[0].delta
            parts = []
            for key in ("reasoning", "content"):
                val = getattr(d, key, None)
                if val is None or val is UNSET:
                    continue
                text = val if isinstance(val, str) else str(val)
                if text:
                    parts.append((key, text))
            return parts
        except Exception:
            return []
    def _fill_usage_fallback(self, prompt, msgs, response):
        if self.usage.input == 0:
            parts = [message_text(m.get("content", "")) for m in msgs]
            est_in = len("\n".join(parts)) // 4
            if est_in > 0:
                self.usage.input = est_in
        if self.usage.output == 0 and response:
            est_out = len(response) // 4
            if est_out > 0:
                self.usage.output = est_out

    def read_usage(self, chunk, invalidate=True):
        u = getattr(chunk, "usage", None)
        if not u:
            return
        if isinstance(u, dict):
            inp = u.get("prompt_tokens") or u.get("input_tokens") or 0
            out_tok = u.get("completion_tokens") or u.get("output_tokens") or 0
            details = u.get("prompt_tokens_details") or {}
            cached = (details.get("cached_tokens") if isinstance(details, dict) else 0) or u.get("cache_read_input_tokens") or 0
        else:
            inp = getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", None) or 0
            out_tok = getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", None) or 0
            details = getattr(u, "prompt_tokens_details", None)
            cached = getattr(details, "cached_tokens", 0) if details else (getattr(u, "cache_read_input_tokens", 0) or 0)
        # prompt_tokens (OpenAI-compatible) includes cached reads; report only the
        # non-cached portion as "input" so prompt-cache savings are reflected in the metric.
        noncached = max(0, int(inp) - int(cached)) if inp else 0
        changed = False
        if inp and noncached != self.usage.input:
            self.usage.input = noncached
            changed = True
        if out_tok and int(out_tok) != self.usage.output:
            self.usage.output = int(out_tok)
            changed = True
        if cached and int(cached) != self.usage.cached:
            self.usage.cached = int(cached)
            changed = True
        if changed:
            self.refresh_status(invalidate=invalidate)

if __name__ == "__main__":
    if sys.platform != "darwin":
        raise SystemExit("HackClub AI is a macOS desktop app. Run: python hackclub_app.py")
    from hackclub_app import main
    main()
