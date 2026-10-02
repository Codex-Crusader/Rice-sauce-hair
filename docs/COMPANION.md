# The companion

Back to the [README](../README.md).

The companion is a small character in the bottom-right corner of the desktop. She talks through a local AI model
(Ollama), and she can do things on the computer with tools. In the code she is called `castorice`
(the process, the service, and the folders). Her name on the screen comes from your persona file.

Everything runs on your computer. The model, the chat, and the memory stay local.

## Use her

| Action | How |
|---|---|
| Talk | **Super+A**, or click her face. Type, then press Enter. **Esc** stops typing. |
| Hide or show her | **Super+Shift+A** |
| Menu | Right-click her face: health check, pause her remarks, hide, restart, open her log |
| Answer a question | Click **Yes** or **No** in her speech bubble, or type `yes` or `no` |

Example requests: "open firefox", "close all tabs except whatsapp", "turn the volume down to 30",
"search hyprland on the arch wiki", "is my pc ok?", "remember that my exam is on 5 March",
"open claude and tell it hi".

## Make your own character

Edit `companion/persona.toml` (the installer made it from `persona.example.toml`).

- `name`, `user`, `model`: her name, your name, and the Ollama model.
- `[expressions]`: the face files (see [Customize](CUSTOMIZE.md)).
- `[prompt] system`: her instructions. Keep the **TOOL RULES** part as it is: the tools depend on it.
  Write her character under **WHO YOU ARE**. Keep it short: a small model follows a short character best.

Restart her after a change (right-click her face, then **Restart her**).

## How she works

| File | What it does |
|---|---|
| `main.py` | Starts her, the greeting, the remarks, and the battery warning |
| `ui.py` | Her window, the speech bubble, blinking, and the right-click menu |
| `brain.py` | The chat with the model, the tool loop, and the checks on the model's answers |
| `tools.py` | All tools, in tiers |
| `chrome_bridge.py` | The connection to the Chrome extension (local only, with a secret token) |
| `escalate.py` | Hand-off to Claude Code in a Kitty window |
| `mood.py` | Her mood and the saved chat |

### Tools and safety

| Tier | Tools | Rule |
|---|---|---|
| Read | system status, health check, find files, list windows and tabs, memory, virus scan | Runs at once |
| Small | open apps, files, and web pages, switch and group tabs, volume, brightness, Wi-Fi, run commands in a visible terminal | Runs at once |
| Confirm | close windows or tabs, forget a memory | She asks Yes or No first |
| Hand-off | anything big: install, remove, sudo, config changes | Opens Claude Code with the task |

More rules:

- A command that can change or delete files asks Yes or No first.
- A command that would destroy the system or the home folder (for example `rm -rf ~`) is refused. She does not even ask.
- Commands with `sudo` never run. They go to Claude Code, which asks you before each step.
- Text from web pages, window titles, and file names is marked as data, not instructions.
- If she says that she did something, but no tool did it, the code makes her do it or say that it is not done.

These rules lower the risk. They do not remove it. A small model makes mistakes. Read each question before you click Yes.

### The model

The default is `qwen3:8b`. It needs about 6 GB of RAM or VRAM. A smaller model is faster but makes more mistakes
with tools. A model must support tool calling. Change it in `persona.toml`, then run `ollama pull <model>`.

## Her files

| File | Content |
|---|---|
| `~/.local/share/castorice/memory.json` | What you asked her to remember |
| `~/.local/share/castorice/state.json` | Her mood and the recent chat |
| `~/.cache/castorice/brain.log` | Everything she did. Read it when something goes wrong. |
| `~/.config/castorice/token` | The secret for the Chrome extension |

## Test her

```sh
python3 ~/dotfiles/companion/tests/eval.py          # all cases, about 3 minutes
python3 ~/dotfiles/companion/tests/eval.py close    # only cases with "close" in the name
```

The tests use the real model, but nothing real happens: window, tab, and terminal actions are only recorded.
Her real memory and chat are not touched.
