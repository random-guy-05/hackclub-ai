<div align="center">

# HackClub AI

**A native macOS desktop chat client for the Hack Club AI proxy.**

Free access to frontier models — GPT, Claude, Gemini — with attachments, skills, MCP integrations, session history, and a polished desktop UI.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#requirements)

</div>

---

> [!IMPORTANT]
> **Disclaimer.** This project is an unofficial, community-built client. It is **not affiliated with, endorsed by, or supported by Hack Club, Composio, OpenRouter, or any model provider.**
>
> Use of upstream services is subject to their respective terms of service. You alone are responsible for ensuring your usage complies with those terms, your eligibility for the services, and any applicable laws.

---

## Features

- **Native macOS app** — real `.app` bundle with Dock icon, not a terminal TUI
- **Instant chat** — no workspace or project-folder setup on launch
- **In-app settings** — API keys saved locally; no shell `export` required
- **Session sidebar** — search, resume, rename, and clear saved chats
- **Token-efficient context** — prompt caching, conditional system prompts, budgeted history, and auto-compaction for long conversations
- **Inline reasoning** — live thinking stream with a styled reasoning panel and loading animation
- **Attachments** — files and folders via menu or `/attach`
- **Slash commands** — models, skills, export, MCP, goals, review, and more
- **Dark / light themes** — switch in Settings or with `/theme`

---

## Requirements

| | |
|---|---|
| **Operating system** | macOS 12+ |
| **Python** | 3.10 or newer (for development; the built `.app` bundles its own runtime) |
| **Hack Club AI key** | Free at <https://ai.hackclub.com> |
| **Composio API key** | Optional — for MCP integrations |

---

## Installation

### Option A — Build the macOS app (recommended)

```bash
git clone https://github.com/random-guy-05/hackclub-cli.git ~/Documents/hackclub-cli
cd ~/Documents/hackclub-cli
chmod +x scripts/build_macos_app.sh
./scripts/build_macos_app.sh
```

This creates a self-contained app at **`~/Applications/HackClub AI.app`** with its own Python environment and icon. Launch from **Applications**, **Spotlight**, or the Dock.

On first launch you'll be prompted for your **Hack Club API Key**. It is stored at `~/.hackclub-ai-shell/config.json`.

### Option B — Run from source

```bash
git clone https://github.com/random-guy-05/hackclub-cli.git ~/Documents/hackclub-cli
cd ~/Documents/hackclub-cli
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python hackclub_app.py
```

---

## Usage

### Keyboard & composer

| Key | Action |
|---|---|
| `Return` | Send message |
| `Shift-Return` | New line |
| `/` | Slash command menu |
| `⌘,` | Settings |

The composer footer shows **context usage** and **input/output token counts** (`ctx`, `in`, `out`).

### Chat management

| Action | How |
|---|---|
| **New chat** | Sidebar **New Chat** button |
| **Rename** | Top-bar **Rename**, double-click a sidebar chat, right-click → **Rename…**, or `/rename <title>` |
| **Clear all chats** | Sidebar **Clear** (with confirmation) |
| **Search chats** | Sidebar search field |
| **Resume session** | Click a chat in the sidebar, or **File → Resume Session…** |

Sessions are saved automatically to `~/.hackclub-ai-shell/sessions/`.

### Attachments

Use **Attach** in the top bar, **File → Attach File…** / **Attach Folder…**, or `/attach` in chat. There is no project workspace binding — attach context only when you need it.

### Slash commands

| Command | Description |
|---|---|
| `/help` | List all commands |
| `/model` | Switch model and reasoning effort |
| `/rename` | Rename the current chat |
| `/attach` | Attach a file or folder |
| `/export` | Export chat as markdown or JSON |
| `/compact` | Summarize and compress transcript context |
| `/context` | List attached files |
| `/skills` | Built-in prompt shortcuts |
| `/goal` | Relentless execution mode |
| `/review` | Full project review from attachments |
| `/mcp` | MCP tool status |
| `/theme` | Switch dark or light theme |

Launch with an initial prompt or resume a session:

```bash
python hackclub_app.py "explain quicksort"
python hackclub_app.py --resume
python hackclub_app.py --resume SESSION_ID
```

---

## Settings

Open **Settings** from the top bar or menu. Configure:

- **Hack Club API Key** (required)
- **Composio API Key** (optional, for MCP)
- **Appearance** — dark / light theme
- **Compact message view** — denser transcript layout

Keys are stored at `~/.hackclub-ai-shell/config.json`. Preferences at `~/.hackclub-ai-shell/prefs.json`.

---

## Configuration

Environment variables (optional overrides):

| Variable | Default | Purpose |
|---|---|---|
| `HACKCLUB_API_KEY` | — | Hack Club AI proxy key (also set in-app) |
| `COMPOSIO_API_KEY` | — | Composio MCP integrations |
| `HACKCLUB_AI_BASE_URL` | `https://ai.hackclub.com/proxy/v1` | API endpoint |
| `HC_DEFAULT_MODEL` | `~openai/gpt-mini-latest` | Default model |
| `HC_MAX_CONTEXT` | `180000` | Max attachment context chars |
| `HC_HISTORY_BUDGET` | `90000` | Max history chars sent per request |
| `HC_AUTO_COMPACT_PCT` | `75` | Auto-compact when live context exceeds this % |
| `HC_AUTO_COMPACT_KEEP` | `6` | Recent turns kept verbatim after auto-compact |
| `HC_MCP_CONFIG` | `~/mcp.json` | MCP config path |

---

## Project layout

| Path | Purpose |
|---|---|
| `hackclub_app.py` | Native macOS UI (PyObjC) — launch entry point |
| `hackclub_ai.py` | Core chat engine, sessions, API, slash commands |
| `scripts/build_macos_app.sh` | Build & install `HackClub AI.app` |
| `scripts/make_icon.py` | Generate app icon assets |
| `assets/AppIcon-1024.png` | App icon source |
| `~/.hackclub-ai-shell/` | Config, prefs, cache, saved sessions |
| `~/Downloads/hackclub-chat-*.{md,json}` | Exported conversations |

---

## Development

Regenerate the app icon:

```bash
python scripts/make_icon.py
```

Render the UI offscreen for visual debugging:

```bash
python scripts/render_ui.py          # conversation view
WELCOME=1 python scripts/render_ui.py  # welcome screen
```

App logs: `~/Library/Logs/HackClub-AI.log`

---

## License

Released under the [MIT License](LICENSE).
