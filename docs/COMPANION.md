# The companion

Back to the [README](../README.md). How she works inside: [companion/README.md](../companion/README.md).

The companion is a small character in the bottom-right corner of the desktop. Her model runs on your computer
(Ollama). She does desktop tasks from plain or vague words, and she hands hard tasks to Claude Code.
In the code she is called `companion` (the process, the service, and the folders). Her name on the screen
comes from your persona file.

Her model, the chat, and the memory stay on your computer. Only a hand-off to Claude Code sends a short
brief to Anthropic (see [Privacy](../companion/README.md#privacy)).

## Use her

| Action | How |
|---|---|
| Talk | **Super+A**, or click her face. Type, then press Enter. **Esc** stops typing. |
| Hide or show her | **Super+Shift+A** |
| Menu | Right-click her face: stop, health check, pause her remarks, hide, restart, log, off |
| Answer a question | Click **Yes** or **No** in her speech bubble, or type `yes` or `no` |
| Turn her off or on | `companion-switch off` / `companion-switch on` (off stays off after a new login) |

Example requests: "bring up my code thing", "open that pdf from yesterday", "close all tabs except my mail",
"volume 20 and bluetooth off", "search hyprland on the arch wiki", "is my pc ok?",
"remember that my exam is on 5 March", "why is my build failing?", "open claude and tell it hi".
When she guesses wrong, say "no, I meant ...": she learns the words for next time.

## Make your own character

Edit `companion/persona.toml` (the installer made it from `persona.example.toml`).

| Part | What it sets |
|---|---|
| `name`, `user`, `model` | Her name, your name, and the Ollama model |
| `[expressions]` | The face files (see [Customize](CUSTOMIZE.md)) |
| `[prompt] system` | Her character and her voice. Write her character under **WHO YOU ARE**. Keep it short: a small model follows a short character best. No tool rules are needed: the planner decides the tools. |
| `[moods]` (optional) | Your own text for a mood, for example a wistful line that fits her story |
| `[handoff] deny` | Paths that never go to Claude Code, and that the file tools never open. Add your own private folders. |
| `[[eval]]` (optional) | Tests for `tests/eval.py` that need your character |

Restart her after a change (right-click her face, then **Restart her**).

## The model

The default is `qwen3:8b`. It needs about 6 GB of RAM or VRAM. A smaller model is faster but makes more
mistakes. The model must give JSON output (Ollama structured output). Change it in `persona.toml`, then run
`ollama pull <model>`.

## Her files

| File | Content |
|---|---|
| `~/.local/share/companion/memory.json` | What you asked her to remember |
| `~/.local/share/companion/state.json` | Her mood and the recent chat |
| `~/.local/share/companion/aliases.json` | Words that she learned ("code thing" -> your IDE) |
| `~/.cache/companion/brain.log` | Everything she did, each decision, and each hand-off. Read it when something goes wrong. |
| `~/.config/companion/token` | The secret for the Chrome extension |

## Test her

```sh
cd ~/dotfiles/companion
python3 -m unittest discover -s tests -p 'test_*.py'   # no model needed, under 1 second
python3 tests/eval.py                                  # the real model, about 3 minutes
python3 tests/eval.py close                            # only the cases with "close" in the name
```

The eval uses the real model, but nothing real happens: window, tab, settings, and terminal actions are
only recorded, and the hand-off to Claude Code is replaced by a recorder. Her real memory and chat are not touched.

These rules lower the risk. They do not remove it. A small model makes mistakes. Read each question before
you click Yes.
