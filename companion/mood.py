"""Castorice's mood, her sense of time, and the saved conversation.

Kept in ~/.local/share/castorice/state.json, so they survive a restart.
The mood changes slowly: with the hour, with how the user talks to her, and with
what she finds on the system. It fades back to the time-of-day mood after two hours.
"""
import json
import re
import time
from pathlib import Path

STATE_FILE = Path.home() / ".local/share/castorice/state.json"
FADE_SECONDS = 2 * 3600

WARM = re.compile(r"\b(thank|thanks|thx|love|cute|good job|well done|great|awesome|nice|sweet|kind)\b|❤|🥰|😊|🦋", re.I)
HARSH = re.compile(r"\b(stupid|useless|dumb|shut up|idiot|hate you)\b", re.I)
PLAYFUL = re.compile(r"\b(haha|lol|lmao|tease|joke|silly)\b|😂|😜|😏", re.I)

# How each mood colors her words. One line each, so the prompt stays short.
MOODS = {
    "calm": "calm and gentle",
    "cheerful": "light and warm; a small smile in your words",
    "playful": "playful; you tease gently and enjoy the banter",
    "sleepy": "drowsy and soft-spoken; you worry a little that the user is awake so late",
    "worried": "anxious underneath your composure; something on the system or with the user troubles you",
    "wistful": "quietly wistful; thoughts of Aidonia's snow and of people you have outlived drift by",
    "hurt": "hurt, though you hide it behind politeness; you stay kind but a little distant",
}


def time_of_day_mood(hour):
    if 0 <= hour < 5:
        return "sleepy", "it is very late at night"
    if 5 <= hour < 9:
        return "calm", "it is early morning"
    if 18 <= hour < 21:
        return "wistful", "it is evening"
    return "calm", "an ordinary hour"


def ago(seconds):
    for unit, size in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if seconds >= size:
            n = int(seconds // size)
            return f"{n} {unit}{'s' if n > 1 else ''}"
    return "a moment"


class Mood:
    def __init__(self):
        try:
            self.state = json.loads(STATE_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            self.state = {}
        self.state.setdefault("history", [])
        self.previous_visit = self.state.get("last_seen")  # for the greeting after a restart

    # ----- what changes the mood -----

    def set(self, mood, reason):
        self.state.update(mood=mood, reason=reason, mood_since=time.time())

    def note_user(self, text):
        self.state["last_seen"] = time.time()
        if HARSH.search(text):
            self.set("hurt", "The user spoke harshly to you")
        elif WARM.search(text):
            self.set("cheerful", "The user was kind to you")
        elif PLAYFUL.search(text):
            self.set("playful", "The user is joking with you")

    def note_result(self, result):
        """Problems found by a tool worry her; a fix makes her cheerful again."""
        text = str(result)
        if re.search(r"\bWARN\b|FOUND|failed|error", text) and "no errors" not in text:
            self.set("worried", "you just found a problem on the system")

    # ----- what she reads -----

    def current(self):
        mood, since = self.state.get("mood"), self.state.get("mood_since", 0)
        if not mood or time.time() - since > FADE_SECONDS:
            return time_of_day_mood(time.localtime().tm_hour)
        return mood, self.state.get("reason", "")

    def describe(self):
        mood, reason = self.current()
        return f"Your mood right now: {mood} ({reason}). Let it color your words: {MOODS.get(mood, mood)}."

    def away_text(self):
        """How long the user was away before this session, for the greeting."""
        if not self.previous_visit:
            return "This is the first time you meet the user here."
        return f"The user was last here {ago(time.time() - self.previous_visit)} ago."

    # ----- saved conversation -----

    def history(self):
        return self.state["history"]

    def save(self, history):
        self.state["history"] = history[-16:]
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(self.state, ensure_ascii=False, indent=1))
