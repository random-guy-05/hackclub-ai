import os, sys, re, json, time, base64, hashlib, mimetypes, zipfile, subprocess, threading, queue, urllib.request, urllib.error, shutil, asyncio
from pathlib import Path
from dataclasses import dataclass
import xml.etree.ElementTree as ET
import questionary
from prompt_toolkit.application import Application, run_in_terminal
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.history import FileHistory
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, ScrollablePane
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.key_binding.defaults import load_key_bindings
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.key_binding.bindings.mouse import load_mouse_bindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.mouse_events import MouseEventType
from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit.styles import Style as PTStyle
from openrouter import OpenRouter
from openrouter.types import UNSET
API_URL = os.getenv("HACKCLUB_AI_BASE_URL", "https://ai.hackclub.com/proxy/v1")
API_KEY = "HACKCLUB_API_KEY"
COMPOSIO_KEY = "COMPOSIO_API_KEY"
HOME = Path.home() / ".hackclub-ai-shell"
CACHE_DIR = HOME / "cache"
MCP_FILE = Path(os.getenv("HC_MCP_CONFIG", str(HOME / "mcp.json")))
MAX_FILE = int(os.getenv("HC_MAX_FILE", "5000000"))
MAX_DOCX_FILE = int(os.getenv("HC_MAX_DOCX_FILE", "30000000"))
INDEX_VERSION = "v3"
MAX_CTX = int(os.getenv("HC_MAX_CONTEXT", "180000"))
MAX_FILES = int(os.getenv("HC_MAX_FILES", "400"))
MAX_TURNS = int(os.getenv("HC_MAX_TURNS", "20"))
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
SKILLS = {
    "fix": "Fix the bug. Start with root cause in 1-2 sentences, then show the minimal code change. No drive-by refactors.\n\n",
    "ship": "Ship the smallest working solution first. List assumptions, give copy-pasteable code/commands, note what to verify after.\n\n",
    "read": "Read the attached context (or what I describe) and explain: purpose, main files, data flow, and the riskiest parts. Be specific, cite paths.\n\n",
    "plan": "Before coding: break this into numbered steps, call out blockers and unknowns, estimate what to do first vs later.\n\n",
    "diff": "Reply with only the exact changes needed — unified diff or before/after snippets. No essay unless I ask.\n\n",
    "grep": "Find where this lives in the codebase. List file paths, line-level clues, and the symbol/string to search for.\n\n",
    "bash": "Give safe macOS/Linux commands. Flag destructive steps, show dry-run when possible, one command per line with a short why.\n\n",
    "api": "Design or implement the API: method, path, auth, request/response JSON, status codes, and one example curl.\n\n",
    "sql": "Write SQL that works. Include schema assumptions, explain the query plan in plain English, suggest an index if slow.\n\n",
    "test": "Write focused tests for happy path, one edge case, and one failure case. Use the project's existing test style if visible.\n\n",
    "review": "Code review: bugs, security, perf, naming, missing tests — ordered by severity. Skip nitpicks.\n\n",
    "pr": "Write a PR: title, summary (3 bullets), test plan checklist, and risks/rollback notes.\n\n",
    "regex": "Write the regex, explain capture groups, and give 3 match/non-match examples.\n\n",
    "json": "Parse, transform, or validate the JSON/data I give. Output valid JSON and note schema edge cases.\n\n",
    "quick": "Shortest correct answer. No preamble, no recap, no alternatives unless blocked.\n\n",
}
COMMANDS = ["/help", "/model", "/clear", "/exit", "/attach", "/drop", "/context", "/skills", "/save", "/copy", "/export", "/system", "/mcp", "/cache", "/theme", "/compact"] + [f"/skill:{k}" for k in SKILLS]
CMD_SET = set(COMMANDS)
SLASH_MENU_LINES = 8
CMD_DESCRIPTIONS = {
    "/help": "List all commands",
    "/model": "Switch model (Tab to pick)",
    "/attach": "Attach file or folder via Finder",
    "/drop": "Remove attachment(s)",
    "/context": "List attached files and folders",
    "/skills": "List skill shortcuts",
    "/skill:fix": "Fix a bug — root cause + minimal patch",
    "/skill:ship": "Ship the smallest working solution",
    "/skill:read": "Explain codebase structure and flow",
    "/skill:plan": "Break work into numbered steps",
    "/skill:diff": "Show only the exact code changes",
    "/skill:grep": "Find where something lives in the repo",
    "/skill:bash": "Safe shell commands with explanations",
    "/skill:api": "Design or implement an API endpoint",
    "/skill:sql": "Write and explain SQL queries",
    "/skill:test": "Focused tests for happy and edge cases",
    "/skill:review": "Code review ordered by severity",
    "/skill:pr": "Write a pull request description",
    "/skill:regex": "Regex with examples",
    "/skill:json": "Parse, transform, or validate JSON",
    "/skill:quick": "Shortest correct answer",
    "/save": "Save last reply to a file",
    "/copy": "Copy last reply to clipboard",
    "/export": "Download chat as markdown or json",
    "/system": "View or set the system prompt",
    "/mcp": "List connected MCP tools",
    "/cache": "Cache stats or clear",
    "/theme": "Switch dark or light theme",
    "/compact": "Toggle compact UI and context",
    "/clear": "Clear chat history",
    "/exit": "Quit HackClub CLI",
}
for _sk in SKILLS:
    CMD_DESCRIPTIONS.setdefault(f"/skill:{_sk}", SKILLS[_sk].split(".")[0].strip())
PREFS_FILE = HOME / "prefs.json"
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
BANNER = "HackClub CLI"
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
OUTPUT_TOP_MARGIN = 1          # margin above HackClub CLI header
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
CONTENT_INDENT = 2
DEFAULT_MODEL = os.getenv("HC_DEFAULT_MODEL", "~openai/gpt-mini-latest")
FALLBACK_MODEL = os.getenv("HC_FALLBACK_MODEL", "deepseek/deepseek-v4-flash")
THINK_INDENT = 4
FOLLOW_MIN_S = 0.15
STREAM_REDRAW_S = 0.12

def load_prefs():
    try:
        return json.loads(PREFS_FILE.read_text())
    except Exception:
        return {}

def save_prefs(data):
    try:
        cur = load_prefs()
        cur.update(data)
        PREFS_FILE.write_text(json.dumps(cur, indent=2))
    except Exception:
        pass

def default_model():
    return load_prefs().get("model") or DEFAULT_MODEL

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

def ask_attach_kind():
    try:
        val = questionary.select(
            "Attach file or folder?",
            choices=[
                questionary.Choice("File", "file"),
                questionary.Choice("Folder", "folder"),
            ],
            style=STYLE,
        ).ask()
        return val
    except Exception:
        try:
            choice = input("Attach [f]ile or [d]irectory? ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if choice in {"f", "file"}:
            return "file"
        if choice in {"d", "dir", "directory", "folder"}:
            return "folder"
        return None

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
    if sys.platform == "darwin":
        return pick_macos_path(kind)
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        if kind == "folder":
            path = filedialog.askdirectory(title="Attach folder")
        else:
            path = filedialog.askopenfilename(title="Attach file")
        root.destroy()
        return path or None
    except Exception:
        pass
    try:
        label = "folder" if kind == "folder" else "file"
        return input(f"Path to {label}: ").strip() or None
    except (EOFError, KeyboardInterrupt):
        print()
        return None

def pick_workspace_folder():
    return pick_macos_path("folder") if sys.platform == "darwin" else pick_path_for_kind("folder")

def leave_startup_screen():
    sys.stdout.write("\033[?25h\033[?1049l\033[2J\033[H\033[3J")
    sys.stdout.flush()

def play_startup_animation():
    import random
    sys.stdout.write("\033[?1049h\033[2J\033[H\033[?25l")
    sys.stdout.flush()
    print()
    shown = []
    for line in LOGO:
        shown.append(line)
        sys.stdout.write("\033[2J\033[H\n")
        for prev in shown:
            print(f"{CYAN}{prev}{RST}")
        sys.stdout.flush()
        time.sleep(0.07)
    print()
    time.sleep(0.12)
    for _ in range(4):
        sys.stdout.write("\033[2J\033[H\n")
        for line in shown:
            if not line:
                print()
                continue
            chars = list(line)
            for _ in range(max(1, len(chars) // 16)):
                i = random.randrange(len(chars))
                if chars[i] not in LOGO_PROTECT:
                    chars[i] = random.choice(GLITCH)
            print(f"{CYAN}{''.join(chars)}{RST}")
        print()
        sys.stdout.flush()
        time.sleep(0.045)
    sys.stdout.write("\033[2J\033[H\n")
    for line in shown:
        print(f"{CYAN}{line}{RST}")
    print()
    width = 34
    for i in range(28):
        filled = max(1, int(width * (i + 1) / 28))
        bar = "▰" * filled + "▱" * (width - filled)
        pct = int(100 * (i + 1) / 28)
        sys.stdout.write(f"\r  {CYAN}{SPINNER[i % len(SPINNER)]}{RST}  {DIM}boot{RST}  {BLUE}[{bar}]{RST}  {pct:3d}%")
        sys.stdout.flush()
        time.sleep(0.032)
    sys.stdout.write(f"\r  {CYAN}◆{RST}  {BOLD}ready{RST}  {BLUE}[{'▰' * width}]{RST}  100%\n\n")
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()

def ask_startup_mode():
    try:
        val = questionary.select(
            "Where do you want to work?",
            choices=[
                questionary.Choice("Workspace  — open a project folder", "workspace"),
                questionary.Choice("Playground — start without attachments", "playground"),
            ],
            style=STYLE,
        ).ask()
        return val or "playground"
    except Exception:
        try:
            choice = input("Workspace [w] or Playground [p]? ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "playground"
        if choice in {"w", "workspace", "folder", "dir"}:
            return "workspace"
        return "playground"

def run_startup(shell):
    try:
        play_startup_animation()
        mode = ask_startup_mode()
        shell.mode = mode
        if mode != "workspace":
            return
        print("  Choose your project folder in Finder...\n")
        path = pick_workspace_folder()
        if path:
            shell.workspace_name = Path(path).name
            shell.attach(path)
        else:
            shell.mode = "playground"
            print("  No folder selected — starting in playground.\n")
            time.sleep(0.6)
    finally:
        leave_startup_screen()

def terminal_model_picker(current_label):
    print("\nModels — number, name, or id (Enter to cancel):\n")
    for i, (n, _) in enumerate(MODELS, 1):
        mark = " *" if n == current_label else ""
        print(f"  {i:2}. {n}{mark}")
    print(f"\nCurrent: {current_label}")
    try:
        choice = input("> ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not choice:
        return None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(MODELS):
            mid = MODELS[idx][1]
            if mid == "custom":
                try:
                    mid = input("Model ID: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return None
                return mid or None
            return mid
    low = choice.lower()
    for n, mid in MODELS:
        if low == mid.lower() or low in n.lower():
            if mid == "custom":
                try:
                    mid = input("Model ID: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return None
                return mid or None
            return mid
    return choice

def questionary_model_picker(current_label):
    try:
        val = questionary.select(
            "Select model (↑↓ move, Enter select)",
            choices=[questionary.Choice(f"{n:<22} {m}", m) for n, m in MODELS],
            style=STYLE,
            use_shortcuts=True,
        ).ask()
    except Exception:
        return terminal_model_picker(current_label)
    if not val:
        return None
    if val == "custom":
        try:
            custom = questionary.text("OpenRouter model ID:", style=STYLE).ask()
        except Exception:
            custom = None
        return custom or None
    return val

def pt_style(name):
    if name == "light":
        return PTStyle.from_dict({
            "prompt": "#0066cc bold bg:#e8e8e8",
            "input_row": "bg:#e8e8e8",
            "status": "#000000",
            "text": "#111111",
            "label": "bold #000000",
            "dim": "#555555",
            "ok": "#0066cc",
            "warn": "#996600",
            "error": "#cc0000",
            "md_strong": "bold #111111",
            "md_em": "italic #111111",
            "md_h": "bold underline #0066cc",
            "code": "#006600 bg:#eeeeee",
            "think": "#888888",
            "think_label": "#666666 bold",
            "think_strong": "bold #777777",
            "think_em": "italic #888888",
            "think_h": "bold underline #777777",
            "think_code": "#888888 bg:#eeeeee",
            "sep": "#cccccc",
            "user_label": "bold #0066cc",
            "user_msg": "#222222",
            "asst_label": "bold #006600",
            "attach": "bold #006600",
            "slash_sel": "bold #000000",
            "slash_cmd": "#333333",
            "slash_desc": "#666666",
            "slash_sel_desc": "bold #444444",
            "scrollbar.background": "#eeeeee",
            "scrollbar.button": "#bbbbbb",
            "scrollbar.arrow": "#666666",
        })
    return PTStyle.from_dict({
        "prompt": "#6ac6ff bold bg:#2a2a2a",
        "input_row": "bg:#2a2a2a",
        "status": "#ffffff",
        "text": "#e4e4e4",
        "label": "bold #ffffff",
        "dim": "#888888",
        "ok": "#6ac6ff",
        "warn": "#e5a045",
        "error": "#ff6b6b",
        "md_strong": "bold #e4e4e4",
        "md_em": "italic #cccccc",
        "md_h": "bold underline #6ac6ff",
        "code": "#a8e6a8 bg:#1a1a1a",
        "think": "#666666",
        "think_label": "#555555 bold",
        "think_strong": "bold #777777",
        "think_em": "italic #666666",
        "think_h": "bold underline #777777",
        "think_code": "#888888 bg:#1a1a1a",
        "sep": "#444444",
        "user_label": "bold #6ac6ff",
        "user_msg": "#cccccc",
        "asst_label": "bold #a8e6a8",
        "attach": "bold #a8e6a8",
        "slash_sel": "bold #ffffff",
        "slash_cmd": "#cccccc",
        "slash_desc": "#888888",
        "slash_sel_desc": "bold #aaaaaa",
        "scrollbar.background": "#2a2a2a",
        "scrollbar.button": "#555555",
        "scrollbar.arrow": "#888888",
    })

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

STYLE = questionary.Style([("qmark", "fg:cyan bold"), ("question", "bold"), ("pointer", "fg:cyan bold"), ("highlighted", "fg:cyan bold"), ("instruction", "fg:gray italic")])

IGNORE_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__", ".pytest_cache", "build", "dist", ".next", ".idea", ".vscode"}
IGNORE_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", ".DS_Store"}
TEXT_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".xml", ".sh", ".zsh", ".bash", ".go", ".rs", ".java", ".c", ".cpp", ".h", ".sql", ".php", ".rb", ".swift", ".kt", ".vue", ".svelte", ".env"}

class Slash(Completer):
    def get_completions(self, doc, event):
        line = doc.text_before_cursor
        if not line and doc.text.startswith("/"):
            line = doc.text
        m = re.search(r"(/\S*)$", line)
        if not m:
            return
        frag = m.group(1).lower()
        if " " in frag:
            return
        for cmd in sorted(COMMANDS):
            if cmd.startswith(frag):
                yield Completion(cmd, start_position=-len(frag), display=cmd)

def slash_menu_key_bindings(shell):
    kb = KeyBindings()
    menu_open = Condition(lambda: shell.slash_menu_open())

    @kb.add("up", filter=menu_open)
    @kb.add("c-p", filter=menu_open)
    def _slash_up(event):
        shell.slash_menu_index = max(0, shell.slash_menu_index - 1)
        event.app.invalidate()

    @kb.add("down", filter=menu_open)
    @kb.add("c-n", filter=menu_open)
    def _slash_down(event):
        matches = shell.slash_matches()
        if matches:
            shell.slash_menu_index = min(len(matches) - 1, shell.slash_menu_index + 1)
        event.app.invalidate()

    @kb.add("tab", filter=menu_open)
    def _slash_tab(event):
        shell.apply_slash_selection(trailing_space=True)

    @kb.add("s-tab", filter=menu_open)
    def _slash_shift_tab(event):
        matches = shell.slash_matches()
        if matches:
            shell.slash_menu_index = (shell.slash_menu_index - 1) % len(matches)
        event.app.invalidate()

    @kb.add("enter", filter=menu_open, eager=True)
    def _slash_enter(event):
        shell.apply_slash_selection(trailing_space=True)

    return kb

def input_key_bindings(shell):
    kb = KeyBindings()
    input_focus = has_focus(shell.input_control)
    menu_open = Condition(lambda: shell.slash_menu_open())

    @kb.add("enter", filter=input_focus & ~menu_open, eager=True)
    def _input_send(event):
        event.current_buffer.validate_and_handle()

    @kb.add("c-j", filter=input_focus, eager=True)
    def _input_newline(event):
        event.current_buffer.newline()

    return kb

class ChatScrollPane(ScrollablePane):
    def __init__(self, shell, content):
        super().__init__(
            content,
            show_scrollbar=True,
            height=Dimension(weight=1),
            keep_cursor_visible=False,
            keep_focused_window_visible=False,
        )
        self.shell = shell
        self._max_scroll = 0
        self.visible_height = 24

    def _make_window_visible(self, visible_height, content_height, visible_win_write_pos, cursor_position=None):
        if getattr(self.shell, "_keep_at_top", False):
            self.vertical_scroll = 0
            return
        super()._make_window_visible(visible_height, content_height, visible_win_write_pos, cursor_position)

    def write_to_screen(self, screen, mouse_handlers, write_position, parent_style, erase_bg, z_index):
        keep_top = getattr(self.shell, "_keep_at_top", False)
        if keep_top:
            self.vertical_scroll = 0
        elif self.shell.follow_output:
            self._refresh_scroll_metrics(write_position)
            self.vertical_scroll = self._max_scroll

        super().write_to_screen(screen, mouse_handlers, write_position, parent_style, erase_bg, z_index)

        self._refresh_scroll_metrics(write_position)
        if self.vertical_scroll > self._max_scroll:
            self.vertical_scroll = self._max_scroll
        self._bind_scroll_wheel(mouse_handlers, write_position, self.show_scrollbar())

    def _refresh_scroll_metrics(self, write_position):
        show_sb = self.show_scrollbar()
        virtual_width = write_position.width - (1 if show_sb else 0)
        virtual_height = self.content.preferred_height(virtual_width, self.max_available_height).preferred
        virtual_height = max(virtual_height, write_position.height)
        self._max_scroll = max(0, virtual_height - write_position.height)
        self.visible_height = write_position.height
        if self.vertical_scroll > self._max_scroll:
            self.vertical_scroll = self._max_scroll

    def _bind_scroll_wheel(self, mouse_handlers, write_position, show_sb):
        shell = self.shell

        def on_wheel(event):
            if event.event_type == MouseEventType.SCROLL_UP:
                shell.scroll_output(-3)
            elif event.event_type == MouseEventType.SCROLL_DOWN:
                shell.scroll_output(3)

        x_end = write_position.xpos + write_position.width - (1 if show_sb else 0)
        for y in range(write_position.ypos, write_position.ypos + write_position.height):
            row = mouse_handlers.mouse_handlers[y]
            for x in range(write_position.xpos, x_end):
                row[x] = on_wheel

def output_key_bindings(shell):
    kb = KeyBindings()

    @kb.add("pageup")
    def _page_up(event):
        shell.scroll_output(-max(1, shell.output_pane.visible_height - 2))

    @kb.add("pagedown")
    def _page_down(event):
        shell.scroll_output(max(1, shell.output_pane.visible_height - 2))

    @kb.add("c-up")
    def _line_up(event):
        shell.scroll_output(-1)

    @kb.add("c-down")
    def _line_down(event):
        shell.scroll_output(1)

    @kb.add("c-g")
    def _jump_bottom(event):
        shell.follow_latest(force=True)

    @kb.add(Keys.ScrollUp)
    def _wheel_up(event):
        shell.scroll_output(-3)

    @kb.add(Keys.ScrollDown)
    def _wheel_down(event):
        shell.scroll_output(3)

    return kb

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
    input: int = 0; output: int = 0
    @property
    def total(self): return self.input + self.output

class Cache:
    def __init__(self): CACHE_DIR.mkdir(parents=True, exist_ok=True)
    def path(self, key): return CACHE_DIR / (hashlib.sha256(key.encode()).hexdigest() + ".json")
    def get(self, key, ttl=CACHE_TTL):
        p = self.path(key)
        try:
            if not p.exists() or time.time() - p.stat().st_mtime > ttl: return None
            return json.loads(p.read_text())
        except Exception: return None
    def set(self, key, value):
        try: self.path(key).write_text(json.dumps(value))
        except Exception: pass
    def clear(self):
        for p in CACHE_DIR.glob("*.json"): p.unlink(missing_ok=True)
    def stats(self): return len(list(CACHE_DIR.glob("*.json"))), sum(p.stat().st_size for p in CACHE_DIR.glob("*.json"))

class Indexer:
    def __init__(self, cache): self.cache = cache
    def load(self, raw, aid):
        path = Path(raw).expanduser().resolve()
        if not path.exists(): return None
        sig = self.sig_dir(path) if path.is_dir() else self.sig_file(path)
        key = f"idx:{INDEX_VERSION}:{sig}"
        hit = self.cache.get(key)
        if hit: return Attachment(aid, hit["name"], hit["kind"], path, hit["content"], hit["chars"], hit["files"], True)
        att = self.dir(path, aid) if path.is_dir() else self.file(path, aid)
        if att: self.cache.set(key, {"name": att.name, "kind": att.kind, "content": att.content, "chars": att.chars, "files": att.files})
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
                not_loaded[rel_path] = "per-workspace file limit reached"
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
            f"Workspace dump — {count}/{len(all_files)} files loaded into context, "
            f"{len(not_loaded)} listed in tree only. .docx files ARE parsed (text + tables); "
            f"if a .docx is marked [not loaded] the reason is shown next to it."
        )
        header = ["### Workspace: " + root.name, notice, "```text", *tree_lines[:600], "```"]
        body_parts = header + [loaded[k] for k in sorted(loaded.keys(), key=lambda x: x.lower())]
        body = "\n".join(body_parts)
        return Attachment(aid, f"Workspace: {root.name}", "text", root, body, len(body), count)
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
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "hackclub-shell", "version": "1.0"}}, init=True)
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
        self.rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "hackclub-shell", "version": "1.0"}}, init=True)
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
    def __init__(self):
        key = os.getenv(API_KEY)
        if not key:
            raise SystemExit(f"Missing {API_KEY}. Run: export {API_KEY}=...")
        HOME.mkdir(parents=True, exist_ok=True)
        self.blocks = []
        self._frag_lock = threading.Lock()
        self.stream_i = None
        self.app = None
        self.busy = False
        self.input_buffer = Buffer(
            completer=Slash(),
            history=FileHistory(str(HOME / "history")),
            multiline=True,
            complete_while_typing=False,
        )
        self.input_control = None
        self.slash_menu_index = 0
        self.cache = Cache()
        self.client = OpenRouter(api_key=key, server_url=API_URL)
        self.mcp = MCP(self.cache)
        self.model = default_model()
        self.history = []
        self.attachments = []
        self.last = ""
        self.aid = 1
        self.usage = Usage()
        self.session_usage = Usage()
        self.mcp_tool_count = 0
        self._status_ver = 0
        self.follow_output = False
        self.output_pane = None
        self.mode = "playground"
        self.workspace_name = None
        self._keep_at_top = True
        self._body_ver = 0
        self.output_control = None
        self.indexer = Indexer(self.cache)
        prefs = load_prefs()
        self.theme_name = prefs.get("theme", "dark")
        self.compact = prefs.get("compact", False)
        self.system = (
            "You are concise, accurate, and practical. Answer the user directly. "
            "Do not bring up Composio, MCP, or third-party integrations unless the user "
            "explicitly asks to use an external app or service."
        )
        self._last_touch = 0.0

    def _ui_invalidate(self, scroll_bottom=False):
        if scroll_bottom:
            self.follow_output = True
            self._keep_at_top = False
        if self.app:
            self.app.invalidate()

    def _finish_stream_ui(self):
        def do():
            self.follow_output = True
            self._keep_at_top = False
            self._body_ver += 1
            if self.output_control:
                self.output_control.reset()
            if self.output_pane:
                self.output_pane.vertical_scroll = 10**9
            app = self.app
            if app:
                app._invalidated = False
                app.invalidate()

        if self.app and getattr(self.app, "loop", None) and not self.app.loop.is_closed():
            self.app.loop.call_soon_threadsafe(do)
            self.app.loop.call_soon_threadsafe(lambda: self.app.loop.call_later(0.06, do))
        else:
            do()

    def refresh_status(self, invalidate=True):
        self._status_ver += 1
        if invalidate and self.app:
            self.app.invalidate()

    def touch_body(self, scroll_bottom=False):
        self._body_ver += 1
        if scroll_bottom:
            self.follow_output = True
        now = time.time()
        if scroll_bottom and now - self._last_touch < STREAM_REDRAW_S:
            return
        self._last_touch = now
        if self.app and getattr(self.app, "loop", None) and not self.app.loop.is_closed():
            self.app.loop.call_soon_threadsafe(lambda: self._ui_invalidate(scroll_bottom))
        else:
            self._ui_invalidate(scroll_bottom)

    def repaint_output(self, scroll_bottom=False):
        self._body_ver += 1
        if scroll_bottom:
            self._finish_stream_ui()
        else:
            self._ui_invalidate()
    def follow_latest(self, force=False):
        if getattr(self, "_keep_at_top", False):
            if self.output_pane:
                self.output_pane.vertical_scroll = 0
            self._ui_invalidate()
            return
        if force:
            self.follow_output = True
        if not self.follow_output:
            return
        now = time.time()
        if not force and now - getattr(self, "_follow_ts", 0) < FOLLOW_MIN_S:
            return
        self._follow_ts = now
        self._ui_invalidate(scroll_bottom=True)
    def scroll_output(self, delta):
        if not self.output_pane:
            return
        if delta < 0:
            self.follow_output = False
        pane = self.output_pane
        pane.vertical_scroll = max(0, min(pane._max_scroll, pane.vertical_scroll + delta))
        if delta > 0 and pane.vertical_scroll >= max(0, pane._max_scroll - 1):
            self.follow_output = True
        if self.app:
            self.app.invalidate()
    def refresh_mcp_count(self):
        try:
            self.mcp_tool_count = len([t for t in self.mcp.tools() if t["name"] != "ERROR"])
        except Exception:
            self.mcp_tool_count = 0
    def _ensure_ui(self):
        if not hasattr(self, "_frag_lock"):
            self._frag_lock = threading.Lock()
        if not hasattr(self, "blocks"):
            self.blocks = []
    def ui(self, text, style="class:text", nl=True):
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("text", text + ("\n" if nl else ""), style))
        if self.app:
            self.app.invalidate()
    def notify(self, msg, style):
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("notify", msg + "\n", style))
        if self.app:
            self.app.invalidate()
    def slash_fragment(self):
        line = self.input_buffer.document.current_line
        m = re.search(r"(/\S*)$", line)
        if not m:
            return None
        frag = m.group(1)
        if " " in frag:
            return None
        return frag.lower()
    def slash_menu_open(self):
        if self.busy:
            return False
        return self.slash_fragment() is not None
    def slash_matches(self):
        frag = self.slash_fragment() or "/"
        return [c for c in sorted(COMMANDS) if c.startswith(frag)]
    def apply_slash_selection(self, trailing_space=False):
        matches = self.slash_matches()
        if not matches:
            return
        idx = max(0, min(self.slash_menu_index, len(matches) - 1))
        cmd = matches[idx]
        doc = self.input_buffer.document
        line = doc.current_line
        m = re.search(r"(/\S*)$", line)
        if not m:
            return
        suffix = " " if trailing_space else ""
        line_start = doc.cursor_position - len(line)
        start = line_start + m.start(1)
        text = self.input_buffer.text
        new = text[:start] + cmd + suffix + text[start + len(m.group(1)):]
        self.input_buffer.document = Document(new, cursor_position=start + len(cmd) + len(suffix))
        self.slash_menu_index = 0
        if self.app:
            self.app.invalidate()
    def render_slash_menu(self):
        matches = self.slash_matches()
        if not matches:
            return [("class:dim", "  no matching commands\n")]
        self.slash_menu_index = max(0, min(self.slash_menu_index, len(matches) - 1))
        width = max(40, self.body_width())
        cmd_w = min(28, max(18, width // 3))
        out = []
        visible = matches[:SLASH_MENU_LINES]
        scroll = 0
        if len(matches) > SLASH_MENU_LINES and self.slash_menu_index >= SLASH_MENU_LINES:
            scroll = min(self.slash_menu_index - SLASH_MENU_LINES + 1, len(matches) - SLASH_MENU_LINES)
            visible = matches[scroll:scroll + SLASH_MENU_LINES]
        for i, cmd in enumerate(visible):
            real_i = scroll + i
            selected = real_i == self.slash_menu_index
            prefix = "→ " if selected else "  "
            desc = CMD_DESCRIPTIONS.get(cmd, "")
            cmd_style = "class:slash_sel" if selected else "class:slash_cmd"
            desc_style = "class:slash_sel_desc" if selected else "class:slash_desc"
            out.append((cmd_style, prefix + cmd.ljust(cmd_w)))
            out.append((desc_style, desc + "\n"))
        hidden = len(matches) - (scroll + len(visible))
        if hidden > 0:
            out.append(("class:dim", f"  ↓ {hidden} more below\n"))
        return out
    def body_width(self):
        try:
            if self.app and getattr(self.app, "output", None):
                size = self.app.output.get_size()
                if size and size.columns:
                    return max(40, size.columns - 2)
        except Exception:
            pass
        return max(40, shutil.get_terminal_size(fallback=(100, 24)).columns - 2)
    def render_body(self):
        self._ensure_ui()
        _ = self._body_ver
        with self._frag_lock:
            blocks = list(self.blocks)
        if not blocks:
            return [("class:dim", "")]
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
                    out.append(("class:text", BLANK))
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
            elif b.kind == "md":
                if self.compact:
                    text = re.sub(r"\s+", " ", b.text.strip())
                    if len(text) > 240:
                        text = text[:240] + "..."
                    out.append(("class:user_msg", f"  {text}{LINE}"))
                else:
                    out.extend(md_to_fragments(b.text, width, indent=CONTENT_INDENT))
                    if not b.text.endswith("\n"):
                        out.append(("class:text", LINE))
            elif b.kind == "think":
                if self.compact:
                    continue
                if b.text.strip():
                    pad = " " * THINK_INDENT
                    out.append(("class:think_label", pad + f"thinking{HEADER_GAP}"))
                    out.extend(md_to_fragments(b.text, width, indent=THINK_INDENT, tone="think"))
                    if not b.text.endswith("\n"):
                        out.append(("class:text", LINE))
                    if nxt == "md":
                        nxt_text = blocks[i + 1].text.strip() if i + 1 < len(blocks) else "x"
                        nxt2 = blocks[i + 2].kind if i + 2 < len(blocks) else None
                        if not (not nxt_text and nxt2 == "notify"):
                            out.append(("class:text", THINK_REPLY_GAP))
            elif b.kind == "spin":
                out.append(("class:dim", "  " + b.text + LINE))
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
                if nxt is not None:
                    out.append(("class:text", THINK_TOOL_GAP))
            else:
                out.append((b.style, b.text))
                if nxt is not None and b.kind in WELCOME_KINDS and nxt in WELCOME_KINDS:
                    continue
        return out
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
            tok = f"in {tot_in}  out {tot_out}"
            if self.compact:
                bits = [self.model_label(), f"ctx {ctx:.0f}%", mcp, tok]
                return " | ".join(bits)
            bits = [self.model_label(), f"ctx {ctx:.0f}%", mcp, f"turns {len(self.history)//2}", tok]
            if self.mode == "workspace" and self.workspace_name:
                bits.insert(1, f"ws:{self.workspace_name}")
            elif self.mode == "playground":
                bits.insert(1, "playground")
            return "  ".join(bits)
        except Exception:
            return "in 0  out 0"
    def render_status(self):
        return [("class:status", self.status_text())]
    def apply_theme(self, name):
        if name not in THEMES:
            return self.warn(f"unknown theme: {name} (dark, light)")
        self.theme_name = name
        save_prefs({"theme": name, "compact": self.compact, "model": self.model})
        if self.app:
            self.app.style = pt_style(name)
            self.app.invalidate()
        self.ok(f"theme: {name}")
    def max_history_msgs(self):
        return 6 if self.compact else MAX_TURNS * 2
    def max_ctx_limit(self):
        return MAX_CTX // 4 if self.compact else MAX_CTX
    def _trim_ui(self):
        with self._frag_lock:
            if len(self.blocks) > 48:
                self.blocks = self.blocks[-48:]
        if self.app:
            self.app.invalidate()
    def toggle_compact(self, rest):
        if rest in {"on", "off"}:
            self.compact = rest == "on"
        else:
            self.compact = not self.compact
        save_prefs({"theme": self.theme_name, "compact": self.compact, "model": self.model})
        if self.compact:
            self._trim_ui()
            self.history = self.history[-self.max_history_msgs():]
        self.ok(f"compact: {'on' if self.compact else 'off'}")
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
    def _welcome_model_text(self):
        return f"model: {self.model_label()}  ·  /help  ·  /model to switch\n"
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
        if updated and self.app:
            self.app.invalidate()
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
        return questionary_model_picker(self.model_label())
    def _apply_model(self, val):
        if not val:
            return
        self.model = val
        save_prefs({"model": val})
        self._sync_welcome_model()
        self.ok(f"model: {self.model_label()}")
        self.refresh_status()
    def set_model(self, rest):
        q = rest.strip()
        if not q:
            return self.schedule_pick_model()
        if q.isdigit():
            idx = int(q) - 1
            if 0 <= idx < len(MODELS):
                mid = MODELS[idx][1]
                if mid == "custom":
                    return self.schedule_pick_model()
                self.model = mid
                save_prefs({"model": mid})
                self._sync_welcome_model()
                self.refresh_status()
                return self.ok(f"model: {self.model_label()}")
        ql = q.lower()
        for n, mid in MODELS:
            if ql == mid.lower() or ql in n.lower():
                if mid == "custom":
                    return self.schedule_pick_model()
                self.model = mid
                save_prefs({"model": mid})
                self._sync_welcome_model()
                self.refresh_status()
                return self.ok(f"model: {self.model_label()}")
        self.model = q
        save_prefs({"model": q})
        self._sync_welcome_model()
        self.refresh_status()
        return self.ok(f"model: {self.model_label()}")
    def schedule_pick_model(self):
        if self.app:
            self.app.create_background_task(self._pick_model_task())
        else:
            val = self._ask_model_dialog()
            self._apply_model(val)
    async def _pick_model_task(self):
        try:
            val = await run_in_terminal(self._ask_model_dialog, in_executor=True)
        except Exception as e:
            self.warn(f"model picker failed: {e}")
            return
        self._apply_model(val)
    def pick_attach(self):
        if self.app:
            self.app.create_background_task(self._pick_attach_task())
            return
        kind = ask_attach_kind()
        if not kind:
            return
        path = pick_path_for_kind(kind)
        if path:
            self.attach(path)
    async def _pick_attach_task(self):
        self.busy = True
        if self.app:
            self.app.invalidate()
        try:
            kind = await run_in_terminal(ask_attach_kind, in_executor=True)
            if not kind:
                return
            path = await run_in_terminal(lambda: pick_path_for_kind(kind), in_executor=True)
            if path:
                self.attach(path)
        except Exception as e:
            self.warn(f"attach failed: {e}")
        finally:
            self.busy = False
            if self.app:
                self.app.invalidate()
    async def _intro_animation(self):
        welcome = [
            UiBlock("text", BANNER + "\n", "class:label"),
        ]
        if self.mode == "workspace" and self.workspace_name:
            welcome.append(UiBlock("text", f"workspace: {self.workspace_name}  ·  /context to view files\n", "class:dim"))
        else:
            welcome.append(UiBlock("text", "playground  ·  /attach to add files\n", "class:dim"))
        welcome.append(UiBlock("welcome_model", self._welcome_model_text(), "class:dim"))
        with self._frag_lock:
            self.blocks = welcome + list(self.blocks)
        self.follow_output = False
        self._keep_at_top = True
        if self.output_pane:
            self.output_pane.vertical_scroll = 0
        self.session_info()
        if self.app:
            self.app.invalidate()
    def on_submit(self, buffer):
        if self.busy:
            return True
        raw = buffer.text
        line = normalize_input(raw)
        if not line:
            return False
        if line.lower() in {"/exit", "exit", "quit"}:
            if self.app:
                self.app.exit()
            return False
        sync = line.startswith("/")
        self._dispatch(line, sync=sync)
        return False
    def _dispatch(self, line, sync=False):
        def work():
            self.busy = True
            try:
                self.route(line)
            except Exception as e:
                self.err(str(e))
            finally:
                self.busy = False
                if not sync:
                    self._finish_stream_ui()
                elif self.app:
                    self.app.invalidate()
        if sync:
            work()
        else:
            threading.Thread(target=work, daemon=True).start()
    def build_app(self):
        self.input_buffer.accept_handler = self.on_submit

        def on_input_change(_):
            self.slash_menu_index = 0
            if self.app:
                self.app.invalidate()

        self.input_buffer.on_text_changed += on_input_change
        self.input_control = BufferControl(buffer=self.input_buffer)
        self.output_control = FormattedTextControl(self.render_body, focusable=False)
        self.output_pane = ChatScrollPane(
            self,
            Window(self.output_control, wrap_lines=True),
        )
        slash_menu_filter = Condition(lambda: self.slash_menu_open())
        slash_menu = ConditionalContainer(
            Window(
                height=SLASH_MENU_LINES + 1,
                content=FormattedTextControl(self.render_slash_menu, focusable=False),
            ),
            filter=slash_menu_filter,
        )
        root = HSplit([
            self.output_pane,
            Window(height=OUTPUT_BOTTOM_MARGIN, content=FormattedTextControl([("class:text", "")])),
            Window(height=INPUT_PAD_Y, style="class:input_row"),
            VSplit([
                Window(width=INPUT_PAD_LEFT, height=1, style="class:input_row"),
                Window(width=2, height=1, content=FormattedTextControl([("class:prompt", "→ ")]), style="class:input_row"),
                Window(width=INPUT_PAD_AFTER_ARROW, height=1, style="class:input_row"),
                Window(height=Dimension(min=1, max=INPUT_MAX_LINES), content=self.input_control, style="class:input_row"),
                Window(width=INPUT_PAD_RIGHT, height=1, style="class:input_row"),
            ]),
            Window(height=INPUT_PAD_Y, style="class:input_row"),
            Window(height=INPUT_SLASH_GAP, content=FormattedTextControl([("class:text", "")])),
            slash_menu,
            Window(height=SLASH_STATUS_GAP, content=FormattedTextControl([("class:text", "")])),
            Window(height=1, content=FormattedTextControl(self.render_status)),
            Window(height=STATUS_BOTTOM_MARGIN, content=FormattedTextControl([("class:text", "")])),
        ])
        self.output_pane.vertical_scroll = 0
        layout = Layout(root)
        layout.focus(self.input_control)
        return Application(
            layout=layout,
            key_bindings=merge_key_bindings([
                load_key_bindings(),
                load_mouse_bindings(),
                output_key_bindings(self),
                slash_menu_key_bindings(self),
                input_key_bindings(self),
            ]),
            style=pt_style(self.theme_name),
            full_screen=True,
            mouse_support=True,
            erase_when_done=False,
            refresh_interval=0.4,
        )
    def run(self, first=""):
        pending = first.strip()
        if not pending:
            run_startup(self)
        self.follow_output = False
        self._keep_at_top = True
        self.app = self.build_app()

        def boot():
            if self.output_pane:
                self.output_pane.vertical_scroll = 0
            if not pending:
                self.app.create_background_task(self._intro_animation())

        if pending:
            self.ui(BANNER, "class:label")
            self.info(f"model: {self.model_label()}")
            self.session_info()
        if pending:
            self.busy = True
            try:
                line = normalize_input(pending)
                if line and line.lower() not in {"/exit", "exit", "quit"}:
                    self.route(line)
            except Exception as e:
                self.err(str(e))
            finally:
                self.busy = False
        try:
            self.app.run(pre_run=boot)
        finally:
            sys.stdout.write("\033[?25h\033[0m")
            sys.stdout.flush()
    def route(self, raw):
        if not raw.startswith("/"):
            return self.send(raw)
        cmd, _, rest = raw.partition(" "); cmd = cmd.lower(); rest = rest.strip()
        if cmd == "/help": return self.help()
        if cmd == "/skills": return self.skills()
        if cmd == "/theme": return self.theme_cmd(rest)
        if cmd == "/compact": return self.toggle_compact(rest)
        if cmd == "/model":
            return self.set_model(rest)
        if cmd == "/clear":
            self.history.clear()
            self.refresh_status()
            return self.info("history cleared")
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
        if cmd.startswith("/skill:"):
            name = cmd.split(":", 1)[1]
            if rest:
                return self.send(SKILLS.get(name, "") + rest)
            return self.schedule_ask_text(name)
        return self.send(raw)
    def schedule_ask_text(self, skill_name):
        if self.app:
            self.app.create_background_task(self._ask_text_task(skill_name))
        else:
            try:
                prompt = input(f"Prompt for {skill_name}: ").strip()
            except (EOFError, KeyboardInterrupt):
                prompt = ""
            self.send(SKILLS.get(skill_name, "") + prompt)
    async def _ask_text_task(self, skill_name):
        def ask():
            try:
                return input(f"Prompt for {skill_name}: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return ""
        try:
            prompt = await run_in_terminal(ask, in_executor=True)
        except Exception as e:
            self.warn(str(e))
            return
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
        if p.is_dir():
            self.workspace_name = p.name
            self.mode = "workspace"
        self.refresh_status()
        if p.is_dir():
            line = f"Attached #{att.id}  {p.name}/  ·  {att.files} files  ·  {att.chars:,} chars"
        else:
            line = f"Attached #{att.id}  {p.name}  ·  {att.chars:,} chars"
        self._ensure_ui()
        with self._frag_lock:
            self.blocks.append(UiBlock("attach", line))
        if self.app:
            self.app.invalidate()
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
                "mode": self.mode,
                "workspace": self.workspace_name,
                "messages": messages,
            }, indent=2, ensure_ascii=False)
        lines = [
            f"# {BANNER} chat export\n",
            f"model: {self.model_label()}\n",
            f"exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        ]
        if self.mode == "workspace" and self.workspace_name:
            lines.append(f"workspace: {self.workspace_name}\n")
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
        tools = [t for t in self.mcp.tools() if t.get("name") != "ERROR"]
        if not tools:
            return self.warn("no mcp tools available")
        self.ui("MCP tools", "class:label")
        for x in tools:
            self.ui(f"  {x['server']}.{x['name']:<28} {str(x.get('description') or '')[:64]}")
    def cache_cmd(self, rest):
        if rest == "clear":
            self.cache.clear()
            return self.info("cache cleared")
        n, b = self.cache.stats()
        self.info(f"cache: {n} entries, {b:,} bytes at {CACHE_DIR}")
    def context(self):
        if not self.attachments:
            return self.info("no attachments")
        for a in self.attachments:
            kind = "folder" if a.path.is_dir() else "file"
            self.ui(f"  #{a.id}  [{kind}]  {a.name}  {a.files} files  {a.chars:,} chars  {a.path}")
    def help(self):
        self.ui("Commands", "class:label")
        for line in [
            "/model [name|#]  switch model (or /model alone to pick)",
            "/attach [path]     pick file or folder, then choose in Finder",
            "/                slash menu — ↑↓ navigate · Tab or Enter to complete",
            "Enter              send  ·  Ctrl+J new line",
            "PgUp/PgDn          scroll output  ·  Ctrl+G jump to latest",
            "/drop [#|all]     remove attachment(s)",
            "/context          list attachments",
            "/skills           list skill shortcuts",
            "/skill:<name>     run a skill prompt",
            "/system [text]    view or set system prompt",
            "/save [path]      save last reply to file",
            "/copy             copy last reply to clipboard",
            "/export            download chat to ~/Downloads",
            "/export json       download chat as json",
            "/mcp               list connected MCP tools",
            "/cache [clear]    cache stats or clear",
            "/theme [dark|light]  switch theme",
            "/compact [on|off] less UI + smaller API context",
            "/clear            clear chat history",
            "/exit             quit",
        ]:
            self.ui(f"  {line}")
    def skills(self):
        self.ui("Skills", "class:label")
        for k, v in SKILLS.items():
            self.ui(f"  /skill:{k:<10} {v.split('.')[0]}")
    def messages(self, prompt):
        system = self.system
        if self.mcp.enabled and self.mcp.servers and user_wants_mcp(prompt):
            system += mcp_integration_prompt(self.mcp, prompt)
        msgs = [{"role": "system", "content": system}, *self.history[-self.max_history_msgs():]]
        ctx_limit = self.max_ctx_limit()
        texts = [str(a.content) for a in self.attachments if a.kind == "text"]
        images = [{"type": "image_url", "image_url": {"url": f"data:{a.content['mime']};base64,{a.content['data']}"}} for a in self.attachments if a.kind == "image"]
        if texts or images:
            content = [{"type": "text", "text": "\n\n".join(texts)[:ctx_limit] + "\n\nUSER:\n" + prompt}, *images]
            msgs.append({"role": "user", "content": content})
        else:
            msgs.append({"role": "user", "content": prompt})
        return msgs
    def theme_cmd(self, rest):
        name = (rest or "").strip().lower()
        if not name:
            return self.ok(f"theme: {self.theme_name} (dark, light)")
        return self.apply_theme(name)
    def send(self, prompt):
        try:
            self._keep_at_top = False
            self.follow_output = True
            self.usage = Usage()
            self.refresh_status()
            self.show_user(prompt)
            msgs = self.messages(prompt)
            final = ""
            mcp_task = self.mcp.enabled and bool(self.mcp.servers) and user_wants_mcp(prompt)
            mcp_calls = 0
            nudges = 0
            self.show_assistant_start()
            for _ in range(MCP_MAX_STEPS):
                out, think = self.stream_text(msgs)
                combined = out + ("\n" + think if think else "")
                call = parse_mcp_call(combined)
                if call and self.mcp.enabled:
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
                        {"role": "assistant", "content": combined},
                        {"role": "user", "content": note + "\n\n" + mcp_continue_message()},
                    ]
                    continue
                if mcp_task and nudges < MCP_MAX_NUDGES and combined.strip():
                    nudges += 1
                    self._hide_mcp_json_block()
                    msgs += [
                        {"role": "assistant", "content": combined},
                        {"role": "user", "content": mcp_nudge_message(nudges)},
                    ]
                    continue
                final = out
                break
            if mcp_task and mcp_calls == 0:
                self.warn("no tools were executed — the reply may not have actually done anything")
            if final.strip():
                self._fill_usage_fallback(prompt, msgs, final)
                self.last = final
                self.history += [{"role": "user", "content": prompt}, {"role": "assistant", "content": final}]
                self.history = self.history[-self.max_history_msgs():]
                self.session_usage.input += self.usage.input
                self.session_usage.output += self.usage.output
                self.refresh_status(invalidate=True)
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
            label = "thinking" if not _is_fallback else f"thinking (fallback: {active_model})"
            self.blocks.append(UiBlock("spin", SPINNER[0] + " " + label, "class:dim"))
        self.follow_latest(force=True)
        stop = threading.Event()
        def spin():
            i = 0
            while not stop.wait(0.08):
                with self._frag_lock:
                    if spin_i >= len(self.blocks) or self.blocks[spin_i].kind != "spin":
                        break
                    self.blocks[spin_i] = UiBlock("spin", SPINNER[i % len(SPINNER)] + " " + label, "class:dim")
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
            for chunk in self.client.chat.send(model=active_model, messages=msgs, stream=True):
                self.read_usage(chunk, invalidate=False)
                for kind, piece in self.delta_parts(chunk):
                    if kind == "reasoning":
                        if self.compact:
                            think += piece
                            continue
                        if think_i is None:
                            end_spin()
                            with self._frag_lock:
                                think_i = len(self.blocks)
                                self.blocks.append(UiBlock("think", ""))
                        think += piece
                        with self._frag_lock:
                            self.blocks[think_i].text = think
                        self.touch_body(scroll_bottom=True)
                    else:
                        if out_i is None:
                            end_spin()
                            with self._frag_lock:
                                out_i = len(self.blocks)
                                self.blocks.append(UiBlock("md", ""))
                        out += piece
                        with self._frag_lock:
                            self.blocks[out_i].text = out
                    self.touch_body(scroll_bottom=True)
            self.refresh_status(invalidate=True)
            end_spin()
            with self._frag_lock:
                if think_i is not None and think.strip():
                    self.blocks[think_i].text = think.rstrip() + "\n"
                if out_i is not None and out.strip():
                    self.blocks[out_i].text = out.rstrip() + "\n"
                elif out_i is None and think_i is None and spin_i is not None and spin_i < len(self.blocks):
                    self.blocks[spin_i] = UiBlock("spin", "thinking", "class:dim")
        except Exception as e:
            end_spin()
            with self._frag_lock:
                if out_i is not None and out_i < len(self.blocks):
                    self.blocks.pop(out_i)
                    out_i = None
                if think_i is not None and think_i < len(self.blocks):
                    self.blocks.pop(think_i)
                    think_i = None
            reason = self._classify_error(e)
            if not _is_fallback and active_model != FALLBACK_MODEL and FALLBACK_MODEL:
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
    def _hide_mcp_json_block(self):
        with self._frag_lock:
            for i in range(len(self.blocks) - 1, -1, -1):
                b = self.blocks[i]
                if b.kind in {"md", "text", "think"} and parse_mcp_call(b.text):
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
        else:
            inp = getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", None) or 0
            out_tok = getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", None) or 0
        changed = False
        if inp and int(inp) != self.usage.input:
            self.usage.input = int(inp)
            changed = True
        if out_tok and int(out_tok) != self.usage.output:
            self.usage.output = int(out_tok)
            changed = True
        if changed:
            self.refresh_status(invalidate=invalidate)

if __name__ == "__main__":
    try:
        Shell().run(" ".join(sys.argv[1:]))
    except KeyboardInterrupt:
        pass
    except SystemExit:
        raise
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
