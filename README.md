<div align="center">

# HackClub AI

**A native macOS desktop chat client for the [Hack Club AI](https://ai.hackclub.com) proxy.**

Free access to frontier models — GPT, Claude, Gemini — with attachments, skills, MCP integrations, session history, and a polished desktop UI.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#requirements)

**Repository:** [github.com/random-guy-05/hackclub-ai](https://github.com/random-guy-05/hackclub-ai)

</div>

---

> [!IMPORTANT]
> **Disclaimer.** This project is an unofficial, community-built client. It is **not affiliated with, endorsed by, or supported by Hack Club, Composio, OpenRouter, or any model provider.**
>
> Use of upstream services is subject to their respective terms of service. You alone are responsible for ensuring your usage complies with those terms, your eligibility for the services, and any applicable laws.

---

## Table of contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [First launch](#first-launch)
4. [Daily usage](#daily-usage)
5. [Slash commands](#slash-commands)
6. [Settings & configuration](#settings--configuration)
7. [Troubleshooting](#troubleshooting)
8. [Development](#development)
9. [Project layout](#project-layout)

---

## Requirements

| Requirement | Details |
|---|---|
| **macOS** | 12 Monterey or later |
| **Hack Club AI API key** | Free at [ai.hackclub.com](https://ai.hackclub.com) |
| **Python 3.10+** | Only needed if you run from source or build the app yourself |
| **Composio API key** | Optional — enables MCP tool integrations |

---

## Installation

Pick **one** method below.

### Method 1 — Install with Homebrew (recommended)

Best if you want the fastest install path with the fewest manual steps.

```bash
brew install --cask random-guy-05/tap/hackclub-ai
```

What this cask does:

- downloads the release DMG from GitHub Releases
- installs **HackClub AI.app** into your Applications folder
- removes the quarantine attribute automatically
- launches the app automatically after install

If you prefer to add the tap first, this works too:

```bash
brew tap random-guy-05/tap && brew install --cask hackclub-ai
```

> [!WARNING]
> This is still a workaround for an unsigned, non-notarized app. It is designed to reduce friction, not to replace proper Apple code signing and notarization.

---

### Method 2 — Install from DMG

Best if you just want the app and do not need to touch the source code.

1. **Get a DMG**
   - Download a release from [GitHub Releases](https://github.com/random-guy-05/hackclub-ai/releases), **or**
   - Build one locally (see [Method 3](#method-3--build-the-app-from-source)).

2. **Open the DMG**  
   Double-click `HackClub-AI.dmg`.

3. **Drag to Applications**  
   Drag **HackClub AI** onto the **Applications** folder shortcut in the window.

4. **Launch the app**
   - Open **Applications** and double-click **HackClub AI**, or
   - Press `⌘Space`, type `HackClub AI`, and press Return.

5. **First launch security (if macOS blocks the app)**  
   If you see “cannot be opened because the developer cannot be verified”:
   - Open **System Settings → Privacy & Security**
   - Click **Open Anyway** next to the HackClub AI message, then confirm.

   Alternatively, right-click the app in Finder → **Open** → **Open** again.

---

### Method 3 — Build the app from source

Best if you are developing, want the latest code, or need to create a DMG to share.

```bash
# 1. Clone the repo
git clone https://github.com/random-guy-05/hackclub-ai.git ~/Documents/hackclub-ai
cd ~/Documents/hackclub-ai

# 2. Build the app bundle, install it, and create a DMG
chmod +x scripts/build_macos_app.sh
./scripts/build_macos_app.sh
```

**What this produces:**

| Output | Location |
|---|---|
| Installed app | `~/Applications/HackClub AI.app` |
| Distributable DMG | `dist/HackClub-AI.dmg` |
| Build artifacts (ignored by git) | `build/` |

The built app bundles its own Python runtime — you do not need a separate venv to run it.

**Launch after build:**

```bash
open ~/Applications/HackClub\ AI.app
```

---

### Method 4 — Run from source (development)

Use this when you are actively editing code and want instant changes without rebuilding the `.app`.

```bash
# 1. Clone the repo
git clone https://github.com/random-guy-05/hackclub-ai.git ~/Documents/hackclub-ai
cd ~/Documents/hackclub-ai

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the UI
python hackclub_app.py
```

**Optional launch flags:**

```bash
python hackclub_app.py "explain quicksort"     # start with an initial prompt
python hackclub_app.py --resume                  # pick a saved session on launch
python hackclub_app.py --resume SESSION_ID       # resume a specific session
```

---

## First launch

1. **HackClub AI opens** with an empty chat or welcome screen.

2. **Enter your API key** when prompted.  
   Get a free key at [ai.hackclub.com](https://ai.hackclub.com).

3. **The key is saved locally** at:

   ```
   ~/.hackclub-ai/config.json
   ```

   You can change it anytime in **Settings** (`⌘,`).

4. **Start chatting** — type a message and press Return.

> **Upgrading from an older install?**  
> If you previously used `.hackclub-ai-shell/`, the app automatically migrates your config and sessions to `~/.hackclub-ai/` on first launch.

---

## Daily usage

### Sending messages

| Action | How |
|---|---|
| Send | `Return` |
| New line | `Shift-Return` |
| Open slash commands | Type `/` in the composer |
| Open settings | `⌘,` or click **Settings** in the top bar |

The composer footer shows **context usage** and token counts (`ctx`, `in`, `out`).

### Managing chats

| Action | How |
|---|---|
| **New chat** | Sidebar **New Chat** button, or **File → New Session** (`⌘N`) |
| **Resume a chat** | Click a session in the sidebar, or **File → Resume Session…** (`⌘R`) |
| **Rename a chat** | Top-bar **Rename**, double-click a sidebar item, right-click → **Rename…**, or `/rename <title>` |
| **Search chats** | Sidebar search field |
| **Clear all chats** | Sidebar **Clear** (confirmation required) |
| **Export chat** | **File → Export Chat…** (`⌘E`) or `/export` |

Sessions auto-save to `~/.hackclub-ai/sessions/`.

### Attachments

Attach files or folders when you want the model to read project context:

| Action | How |
|---|---|
| Attach file | Top-bar **Attach**, **File → Attach File…** (`⌘O`), or `/attach` |
| Attach folder | **File → Attach Folder…** (`⇧⌘O`) |
| List attachments | `/context` |
| Remove attachments | `/drop` |

There is no fixed workspace — attach context only when you need it.

### Menu bar reference

| Menu | Items |
|---|---|
| **HackClub AI** | About, Settings (`⌘,`), Quit (`⌘Q`) |
| **File** | Attach File (`⌘O`), Attach Folder (`⇧⌘O`), Export Chat (`⌘E`), New Session (`⌘N`), Resume Session (`⌘R`) |
| **View** | Dark Theme, Light Theme, Toggle Compact |

### Themes

- Switch in **Settings**, **View** menu, or with `/theme`.
- **Compact message view** — denser transcript; toggle in Settings or **View → Toggle Compact**.

---

## Slash commands

Type `/` in the composer to open the command menu, or enter a command directly.

| Command | Description |
|---|---|
| `/help` | List all commands |
| `/model` | Switch model and reasoning effort |
| `/rename` | Rename the current chat |
| `/clear` | Clear the current chat history |
| `/attach` | Attach a file or folder |
| `/drop` | Remove attachment(s) |
| `/context` | List attached files and folders |
| `/export` | Export chat as Markdown or JSON |
| `/compact` | Summarize and compress transcript context |
| `/skills` | Built-in prompt shortcuts |
| `/goal` | Relentless execution mode for an objective |
| `/plan` | Toggle planning mode |
| `/review` | Full project review from attachments |
| `/grill-me` | Stress-test the current plan |
| `/mcp` | MCP tool status |
| `/cache` | Cache stats or clear cached folders |
| `/theme` | Switch dark or light theme |
| `/side` | Ask a side question without polluting main history |
| `/save` | Save last reply to a file |
| `/copy` | Copy last reply to clipboard |
| `/system` | View or set the system prompt |
| `/diff` | Show live git diff |
| `/init` | Scaffold AGENTS.md in an attached folder |
| `/yeet` | Stage, commit, push, and open a GitHub PR |
| `/sessions` | List saved chat sessions |
| `/exit` | Quit HackClub AI |

Exported chats are saved to `~/Downloads/hackclub-chat-*.{md,json}`.

---

## Settings & configuration

### In-app settings

Open **Settings** (`⌘,`):

| Setting | Purpose |
|---|---|
| **Hack Club API Key** | Required — powers all chat requests |
| **Composio API Key** | Optional — MCP integrations |
| **Appearance** | Dark or light theme |
| **Compact message view** | Denser transcript layout |

### Local data paths

| Path | Contents |
|---|---|
| `~/.hackclub-ai/config.json` | API keys |
| `~/.hackclub-ai/prefs.json` | Theme and UI preferences |
| `~/.hackclub-ai/sessions/` | Saved chat sessions |
| `~/.hackclub-ai/cache/` | Attachment index cache |
| `~/Library/Logs/HackClub-AI.log` | App error log |

### Environment variables (optional)

These override defaults. The built `.app` reads `HACKCLUB_API_KEY` from config first; env vars are mainly useful when running from source.

| Variable | Default | Purpose |
|---|---|---|
| `HACKCLUB_API_KEY` | — | Hack Club AI proxy key |
| `COMPOSIO_API_KEY` | — | Composio MCP integrations |
| `HACKCLUB_AI_BASE_URL` | `https://ai.hackclub.com/proxy/v1` | API endpoint |
| `HC_DEFAULT_MODEL` | `~openai/gpt-mini-latest` | Default model |
| `HC_MAX_CONTEXT` | `180000` | Max attachment context chars |
| `HC_HISTORY_BUDGET` | `90000` | Max history chars per request |
| `HC_AUTO_COMPACT_PCT` | `75` | Auto-compact when context exceeds this % |
| `HC_AUTO_COMPACT_KEEP` | `6` | Recent turns kept after auto-compact |
| `HC_MCP_CONFIG` | `~/.hackclub-ai/mcp.json` | MCP config path |

---

## Troubleshooting

### App will not open / “damaged” or “unverified developer”

This is most likely with locally built apps or direct DMG installs because the app is not notarized by Apple.

1. Try the Homebrew install path first. It removes quarantine automatically and opens the app after install.
2. If you installed from a DMG or built locally, right-click **HackClub AI** in Applications → **Open** → confirm **Open**.
3. Or use **System Settings → Privacy & Security → Open Anyway**.

### API key errors / “unauthorized”

1. Confirm your key at [ai.hackclub.com](https://ai.hackclub.com).
2. Open **Settings** (`⌘,`) and re-enter the key.
3. Or edit `~/.hackclub-ai/config.json` directly.

### Blank window or crash on launch

Check the log:

```bash
tail -50 ~/Library/Logs/HackClub-AI.log
```

Then rebuild:

```bash
cd ~/Documents/hackclub-ai
./scripts/build_macos_app.sh
```

### Rebuild from a clean state

```bash
cd ~/Documents/hackclub-ai
rm -rf build dist ~/Applications/HackClub\ AI.app
./scripts/build_macos_app.sh
```

---

## Development

### Regenerate the app icon

```bash
python scripts/make_icon.py
```

### Render the UI offscreen (visual debugging)

```bash
python scripts/render_ui.py           # conversation view
WELCOME=1 python scripts/render_ui.py # welcome screen
```

### Build only (same as Method 3)

```bash
./scripts/build_macos_app.sh
```

### Generate the Homebrew cask

`./scripts/build_macos_app.sh` now regenerates `Casks/hackclub-ai.rb` automatically after building the DMG.

You can also regenerate it directly:

```bash
python3 scripts/generate_homebrew_cask.py
```

### Release checklist

1. Set the release version in `VERSION`.
2. Run `./scripts/build_macos_app.sh`.
3. Upload `dist/HackClub-AI.dmg` to GitHub Releases under tag `v<version>`.
4. Commit the updated `Casks/hackclub-ai.rb`.
5. Copy `Casks/hackclub-ai.rb` into the `homebrew-tap` repository so users can run `brew install --cask random-guy-05/tap/hackclub-ai`.

---

## Project layout

| Path | Purpose |
|---|---|
| `hackclub_app.py` | Native macOS UI (PyObjC) — launch entry point |
| `hackclub_ai.py` | Core chat engine, sessions, API, slash commands |
| `scripts/build_macos_app.sh` | Build app, install to `~/Applications`, create DMG |
| `scripts/generate_homebrew_cask.py` | Generate the Homebrew cask from `VERSION` and the DMG |
| `scripts/make_icon.py` | Generate app icon assets |
| `scripts/render_ui.py` | Offscreen UI rendering for debugging |
| `Casks/hackclub-ai.rb` | Homebrew cask definition for release installs |
| `VERSION` | Canonical app and release version |
| `assets/AppIcon-1024.png` | App icon source |
| `requirements.txt` | Python dependencies |
| `dist/HackClub-AI.dmg` | Distributable disk image (after build) |

---

## License

Released under the [MIT License](LICENSE).
