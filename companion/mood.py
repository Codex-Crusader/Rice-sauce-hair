"""The companion's mood, her sense of time, and the saved conversation.

Kept by the store (state.json in the data folder), so they survive a restart.
The mood changes slowly: with the hour, with how the user talks to her, and with
what she finds on the system. It fades back to the time-of-day mood after two hours.
"""
import re
import time

FADE_SECONDS = 2 * 3600

WARM = re.compile(r"\b(thank|thanks|thx|love|cute|good job|well done|great|awesome|nice|sweet|kind(?! of))\b|❤|🥰|😊|🦋", re.IGNORECASE)
HARSH = re.compile(r"\b(stupid|useless|dumb|shut up|idiot|hate you)\b", re.IGNORECASE)
PLAYFUL = re.compile(r"\b(haha|lol|lmao|tease|joke|silly)\b|😂|😜|😏", re.IGNORECASE)

# How each mood colors her words. One line each, so the prompt stays short. {user} is the user's name.
# persona.toml can replace any line in a [moods] table.
MOODS = {
    "calm": "calm and gentle",
    "cheerful": "light and warm; a small smile in your words",
    "playful": "playful; you tease gently and enjoy the banter",
    "sleepy": "drowsy and soft-spoken; you worry a little that {user} is awake so late",
    "worried": "anxious underneath your composure; something on the system or with {user} troubles you",
    "wistful": "quietly wistful; old memories drift by",
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
    def __init__(self, store, user="the user", moods=None):
        self.store = store
        self.user = user
        self.moods = {**MOODS, **(moods or {})}
        self.state = store.state()
        self.state.setdefault("history", [])
        self.previous_visit = self.state.get("last_seen")  # for the greeting after a restart

    # ----- what changes the mood -----

    def set(self, mood, reason):
        self.state.update(mood=mood, reason=reason, mood_since=time.time())

    def note_user(self, text):
        self.state["last_seen"] = time.time()
        if HARSH.search(text):
            self.set("hurt", f"{self.user} spoke harshly to you")
        elif WARM.search(text):
            self.set("cheerful", f"{self.user} was kind to you")
        elif PLAYFUL.search(text):
            self.set("playful", f"{self.user} is joking with you")

    def note_result(self, result):
        """Problems found by a tool worry her; a fix makes her cheerful again."""
        text = str(result)
        # whole words at the start of a line or after a colon, so a file named error.log does not count
        if re.search(r"(^|:\s*)(WARN|FAIL|failed|error)\b|\bFOUND$", text, re.MULTILINE) and "no errors" not in text:
            self.set("worried", "you just found a problem on the system")

    # ----- what she reads -----

    def current(self):
        mood, since = self.state.get("mood"), self.state.get("mood_since", 0)
        if not mood or time.time() - since > FADE_SECONDS:
            return time_of_day_mood(time.localtime().tm_hour)
        return mood, self.state.get("reason", "")

    def describe(self):
        mood, reason = self.current()
        return f"Your mood right now: {mood} ({reason}). Let it color your words: {self.moods.get(mood, mood).format(user=self.user)}."

    def away_text(self):
        """How long the user was away before this session, for the greeting."""
        if not self.previous_visit:
            return f"This is the first time you meet {self.user} here."
        return f"{self.user} was last here {ago(time.time() - self.previous_visit)} ago."

    # ----- saved conversation -----

    def history(self):
        return self.state["history"]

    def save(self, history):
        self.state["history"] = history[-16:]
        self.store.save_state(self.state)
