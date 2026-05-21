<div align="center">

# HackClub CLI

**A keyboard-first terminal chat client for the Hack Club AI proxy.**

Free access to frontier models — GPT, Claude, Gemini — through a fast, modern TUI with attachments, skills, MCP integrations, exports, and theming.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)](#requirements)
[![GitHub stars](https://img.shields.io/github/stars/random-guy-05/hackclub-cli?style=social)](https://github.com/random-guy-05/hackclub-cli/stargazers)

_If this project is useful to you, please consider [starring it on GitHub](https://github.com/random-guy-05/hackclub-cli) — it helps others discover it and motivates continued development._

</div>

---

> [!IMPORTANT]
> **Disclaimer.** This project is an unofficial, community-built client. It is **not affiliated with, endorsed by, or supported by Hack Club, Composio, OpenRouter, or any model provider.**
>
> Use of upstream services (Hack Club AI, Composio, etc.) is subject to their respective terms of service. You alone are responsible for ensuring your usage complies with those terms, your eligibility for the services, and any applicable laws.
>
> The author of this project provides this software **"as is", without warranty of any kind**, and **accepts no liability** for any consequences arising from its use — including but not limited to account termination, service disruption, data loss, or any direct, indirect, incidental, or consequential damages.
>
> **By installing or using this software you agree that any decision to do so, and any consequences thereof, are entirely your own.** See [LICENSE](LICENSE) for the full legal text.

---

## Table of contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Keyboard shortcuts](#keyboard-shortcuts)
  - [Slash commands](#slash-commands)
  - [One-shot mode](#one-shot-mode)
- [MCP & Composio](#mcp--composio)
- [Environment variables](#environment-variables)
- [Files & data layout](#files--data-layout)
- [Updating](#updating)
- [Uninstalling](#uninstalling)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Support](#support)
- [License](#license)

---

## Features

- **Streaming chat** across any model on the Hack Club AI proxy
- **Slash-command menu** with live filtering — `/model`, `/attach`, `/export`, `/skills`, and more
- **Attachments** — single files, entire folders, images, and `.docx` documents (folders are cached for fast re-attach)
- **Skills** — curated one-shot expert prompts (`/skill:code`, `/skill:debug`, `/skill:explain`, …)
- **MCP / Composio integration** — call Gmail, GitHub, Slack, Notion, Linear and 200+ other apps from chat
- **Exports** — save conversations as Markdown or JSON to `~/Downloads`
- **Themes** — `dark` and `light`
- **Compact mode** — reduced context window and tighter UI for low-bandwidth sessions
- **Status bar** with model, context %, MCP state, and live token counts
- **Local cache** for indexed folders and MCP tool listings

---

## Requirements

| | |
|---|---|
| **Operating system** | macOS or Linux |
| **Python** | 3.10 or newer (developed on 3.14) |
| **Hack Club AI key** | Free at <https://ai.hackclub.com> *(intended for Hack Club members — see [Disclaimer](#disclaimer))* |
| **Composio API key** | Optional. Free at <https://app.composio.dev> — required only for MCP integrations |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/random-guy-05/hackclub-cli.git ~/Documents/hackclub-cli
cd ~/Documents/hackclub-cli
```

### 2. Create a virtual environment and install dependencies

```bash
python3 -m venv ~/.hackclub_venv
~/.hackclub_venv/bin/pip install -r requirements.txt
```

### 3. Configure your API key(s)

Add the following to `~/.bashrc` or `~/.zshrc`:

```bash
# Required
export HACKCLUB_API_KEY="sk-hc-v1-..."

# Optional — enables MCP / Composio integrations
export COMPOSIO_API_KEY="ck_..."
```

Then reload your shell:

```bash
source ~/.bashrc   # or: source ~/.zshrc
```

### 4. Add the launcher

Add this function to the same shell config file:

```bash
hackclub() {
  ~/.hackclub_venv/bin/python ~/Documents/hackclub-cli/hackclub_ai.py "$@"
}
```

Reload your shell once more, then launch:

```bash
hackclub
```

On first run you'll be prompted to choose between **Playground mode** (free chat) and **Workspace mode** (attach a folder for context).

---

## Configuration

All configuration lives in environment variables (see [Environment variables](#environment-variables)) and a small preferences file at `~/.hackclub-ai-shell/prefs.json`, which the CLI manages automatically when you change themes, models, or modes.

---

## Usage

### Keyboard shortcuts

| Key | Action |
|---|---|
| `Enter` | Send message |
| `Ctrl+J` | Insert a new line (multi-line prompts) |
| `↑` / `↓` | Browse prompt history (or navigate the slash menu) |
| `Tab` | Complete slash command |
| `PageUp` / `PageDown` | Scroll the output pane |
| `Ctrl+G` | Jump to the latest output |
| `Ctrl+C` / `/exit` | Quit |

### Slash commands

| Command | Description |
|---|---|
| `/help` | List all commands |
| `/model [name\|#]` | Switch model (or open the picker) |
| `/attach [path]` | Attach a file or folder |
| `/drop [#\|all]` | Remove attachment(s) |
| `/context` | List current attachments |
| `/skills` | List available skill shortcuts |
| `/skill:<name>` | Run a skill prompt (e.g. `/skill:debug`) |
| `/system [text]` | View or set the system prompt |
| `/save [path]` | Save the last reply to a file |
| `/copy` | Copy the last reply to the clipboard |
| `/export [json]` | Download the conversation to `~/Downloads` |
| `/mcp` | List connected MCP tools |
| `/cache [clear]` | Show cache stats or clear the cache |
| `/theme [dark\|light]` | Switch theme |
| `/compact [on\|off]` | Toggle compact mode |
| `/clear` | Clear chat history |
| `/exit` | Quit |

### One-shot mode

Pass a prompt as an argument to run non-interactively:

```bash
hackclub "summarize the file ~/notes/today.md"
```

---

## MCP & Composio

The CLI ships with [Composio](https://composio.dev) MCP support enabled by default. When `COMPOSIO_API_KEY` is set, the assistant can invoke external integrations directly from chat.

### Setup

1. Create a free account at <https://app.composio.dev>.
2. Copy your API key and export it as `COMPOSIO_API_KEY`.
3. Connect the apps you want from the Composio dashboard (Gmail, GitHub, Slack, etc.).
4. Restart the CLI — the status bar should now read **`mcp connected`**.

Ask naturally, e.g. *"send an email to alex@example.com saying I'll be late"*. The assistant will search for the right tool and execute it.

Run `/mcp` to list every available tool.

### Custom MCP servers

Define additional servers in `~/mcp.json`:

```json
{
  "mcpServers": {
    "myserver": {
      "command": "node",
      "args": ["/path/to/server.js"]
    },
    "remote": {
      "url": "https://example.com/mcp",
      "headers": { "Authorization": "Bearer ${MY_TOKEN}" }
    }
  }
}
```

Environment variables in the form `${NAME}` are expanded at load time.

---

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `HACKCLUB_API_KEY` | yes | — | Hack Club AI proxy key |
| `COMPOSIO_API_KEY` | no | — | Enables Composio MCP integrations |
| `HACKCLUB_AI_BASE_URL` | no | `https://ai.hackclub.com/proxy/v1` | Override the API endpoint |
| `HC_DEFAULT_MODEL` | no | `~openai/gpt-mini-latest` | Default model on launch |
| `HC_MCP_CONFIG` | no | `~/mcp.json` | Path to MCP configuration file |
| `HC_MCP_CACHE_TTL` | no | `300` | MCP tool list cache TTL (seconds) |
| `HC_MAX_FILE` | no | `5000000` | Max size (bytes) for plain-text files in folder attachments |
| `HC_MAX_DOCX_FILE` | no | `30000000` | Max size (bytes) for `.docx` files (figures/images bloat file size; text content is much smaller) |
| `HC_MAX_FILES` | no | `120` | Max files indexed per folder attachment |
| `HC_MAX_CONTEXT` | no | `180000` | Max chars of file content included in context per attachment |

---

## Files & data layout

| Path | Purpose |
|---|---|
| `~/Documents/hackclub-cli/hackclub_ai.py` | The CLI |
| `~/.hackclub_venv/` | Virtual environment with dependencies |
| `~/.hackclub-ai-shell/prefs.json` | Saved preferences (model, theme, compact mode) |
| `~/.hackclub-ai-shell/history` | Prompt history |
| `~/.hackclub-ai-shell/cache/` | Indexed folder cache and MCP tool cache |
| `~/Downloads/hackclub-chat-*.{md,json}` | Exported conversations |

No secrets are ever written to this repository — all keys are read from your shell environment at runtime.

---

## Updating

```bash
cd ~/Documents/hackclub-cli
git pull
~/.hackclub_venv/bin/pip install -r requirements.txt
```

---

## Uninstalling

```bash
rm -rf ~/Documents/hackclub-cli ~/.hackclub_venv ~/.hackclub-ai-shell
```

Then remove the `hackclub()` function and `HACKCLUB_API_KEY` / `COMPOSIO_API_KEY` exports from your shell config.

---

## Troubleshooting

| Symptom | Resolution |
|---|---|
| `Missing HACKCLUB_API_KEY` | Export the variable and reload your shell config. |
| `mcp unavailable` | Either `COMPOSIO_API_KEY` is not set or `~/mcp.json` is missing. Composio is optional. |
| Status shows `mcp connected` but tools fail to execute | Restart the CLI, then try again. Check connected apps in the Composio dashboard. |
| Arrow keys or control codes appear as literal characters | Your terminal isn't passing ANSI input correctly. Try a modern terminal (iTerm2, Alacritty, Kitty, Ghostty). |
| UI feels laggy on long sessions | Enable compact mode: `/compact on`. |

---

## Contributing

Contributions, issues, and feature requests are welcome. Please open an issue or pull request on [GitHub](https://github.com/random-guy-05/hackclub-cli).

When reporting bugs, please include:

- Operating system and version
- Python version (`python3 --version`)
- Terminal emulator
- Steps to reproduce and the full error output

---

## Support

If this project saved you time or you enjoy using it, the best way to say thanks is to **[star the repository on GitHub](https://github.com/random-guy-05/hackclub-cli)**. Stars make the project easier to discover and help justify the time spent maintaining it.

Other ways to help:

- Report bugs and request features via [issues](https://github.com/random-guy-05/hackclub-cli/issues)
- Open a pull request — see [Contributing](#contributing)
- Share the project with anyone you think might find it useful

---

## Disclaimer

This project is **not affiliated with Hack Club, Composio, OpenRouter, or any model provider**. It is an independent, community-built client.

Hack Club AI is intended for current Hack Club members. **Use of the Hack Club AI proxy by non-members may violate the service's terms of use.** It is your responsibility to verify your eligibility and to comply with the terms of every upstream service you connect to (including Composio and any model provider whose models you invoke).

The author of this project provides this software **"as is"** under the terms of the [MIT License](LICENSE) and makes **no warranties and accepts no liability** for any outcome resulting from its installation or use, including but not limited to: account suspension or termination by any upstream provider, loss of data, service disruption, financial loss, or any other direct, indirect, incidental, or consequential damages.

**By installing or using this software, you acknowledge that you are doing so entirely at your own risk and on your own initiative.**

---

## License

Released under the [MIT License](LICENSE).
