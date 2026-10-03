"""The persona, all paths, and the repo folder in one object. main.py loads it one time.

Nothing here reads or writes a file at import. REPO is derived from this file's place
(companion/ is inside the repo), so no code needs a fixed "~/dotfiles" string.
"""
import tomllib
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_DENY = ["~/.ssh", "~/.gnupg", "~/.password-store", "~/.local/share/keyrings", "~/.config/companion"]
REPO = HERE.parent


@dataclass
class Config:
    persona: dict
    repo: Path = REPO
    data_dir: Path = Path.home() / ".local/share/companion"   # memory, mood, chat, avatar images
    cache_dir: Path = Path.home() / ".cache/companion"        # the log
    config_dir: Path = Path.home() / ".config/companion"      # the Chrome token, the off switch

    @property
    def user(self):
        return self.persona["user"]

    @property
    def name(self):
        return self.persona["name"]

    @property
    def model(self):
        return self.persona["model"]

    @property
    def log_file(self):
        return self.cache_dir / "brain.log"

    @property
    def avatar_dir(self):
        return self.data_dir / "avatar"

    @property
    def handoff_dir(self):
        """An empty working folder for Path A when the task names no folder."""
        return self.cache_dir / "handoff"

    @property
    def deny_paths(self):
        """Paths that never go to Claude Code: not in a brief, never the working folder."""
        paths = self.persona.get("handoff", {}).get("deny", DEFAULT_DENY)
        return [Path(p).expanduser().resolve() for p in paths]

    def bin(self, name):
        """A script in the repo's bin folder."""
        return self.repo / "bin" / name


def load(persona_file=HERE / "persona.toml", **paths):
    """Read the persona. paths (data_dir=..., cache_dir=...) replace the default folders, for tests."""
    return Config(tomllib.loads(Path(persona_file).read_text()), **paths)
