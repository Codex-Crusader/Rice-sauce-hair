"""Only the HTTP call to Ollama. No logic.

chat()   the tool-calling chat that the brain uses now
plan()   structured output (format = JSON schema), temperature 0, no tools  (for the planner)
speak()  a reply in the persona's voice, no tools                          (for the planner)
"""
import json
import urllib.request

OLLAMA = "http://127.0.0.1:11434/api/chat"
OPTIONS = {"temperature": 0.75, "num_ctx": 8192, "num_predict": 400}


def chat(model, messages, tools=None, fmt=None, options=None, timeout=180):
    """One chat call. Returns the message dict ({"content": ..., "tool_calls": [...]})."""
    body = {"model": model, "messages": messages, "stream": False, "think": False, "keep_alive": "5m",
            "options": {**OPTIONS, **(options or {})}}
    if tools:
        body["tools"] = tools
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(OLLAMA, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]


def plan(model, messages, schema, options=None):
    """A decision as JSON that matches schema. Returns the parsed dict."""
    msg = chat(model, messages, fmt=schema, options={"temperature": 0, **(options or {})})
    return json.loads(msg.get("content") or "{}")


def speak(model, messages, options=None):
    """A reply in her voice. Returns the text."""
    return chat(model, messages, options=options).get("content", "")
