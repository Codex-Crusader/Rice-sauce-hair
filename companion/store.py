"""All files on disk: memory, mood state with the saved chat, and learned words (aliases).

Paths come from config, so a test gives a temporary folder and needs no patches.
Each write is atomic and private: a temporary file (mode 0600), then a rename.
"""
import json
import os
import tempfile


def read_json(path, default):
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default
    return data if isinstance(data, type(default)) else default


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")  # mkstemp makes the file 0600
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


class Store:
    def __init__(self, config):
        self.memory_file = config.data_dir / "memory.json"    # facts about the user (a list)
        self.state_file = config.data_dir / "state.json"      # mood and the saved chat (a dict)
        self.aliases_file = config.data_dir / "aliases.json"  # learned words: "code thing" -> "PyCharm"

    def memory(self):
        return read_json(self.memory_file, [])

    def save_memory(self, facts):
        write_json(self.memory_file, facts)

    def state(self):
        return read_json(self.state_file, {})

    def save_state(self, state):
        write_json(self.state_file, state)

    def aliases(self):
        return read_json(self.aliases_file, {})

    def save_aliases(self, aliases):
        write_json(self.aliases_file, aliases)

    def learn(self, words, meaning, limit=100):
        """Remember that words ("code thing") mean meaning ("PyCharm"). The newest limit pairs stay."""
        aliases = {k: v for k, v in self.aliases().items() if k != words}
        aliases[words] = meaning
        self.save_aliases(dict(list(aliases.items())[-limit:]))
