"""Bridge to the Castorice Chrome extension.

The extension connects to ws://127.0.0.1:8765 and sends the secret token first.
Then this bridge sends commands ({id, cmd, args}) and waits for replies ({id, result}).
The token is in ~/.config/castorice/token. The extension's copy is in
chrome-extension/token.js (made by setup.sh, not in git).
"""
import asyncio
import json
import secrets
import threading
from pathlib import Path

import websockets

HOST, PORT = "127.0.0.1", 8765
TOKEN_FILE = Path.home() / ".config/castorice/token"
FILLER = {"tab", "tabs", "the", "a", "an", "two", "three", "my", "chrome", "page", "pages", "window", "and"}


def load_token():
    if not TOKEN_FILE.exists():
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(secrets.token_hex(24))
        TOKEN_FILE.chmod(0o600)
    return TOKEN_FILE.read_text().strip()


class ChromeBridge:
    def __init__(self):
        self.token = load_token()
        self.socket = None
        self.pending = {}
        self.next_id = 0
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._serve, daemon=True).start()

    # ----- server (runs in its own thread) -----

    def _serve(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._main())

    async def _main(self):
        async with websockets.serve(self._handle, HOST, PORT):
            await asyncio.Future()  # run forever

    async def _handle(self, socket):
        try:
            if await asyncio.wait_for(socket.recv(), 5) != self.token:
                await socket.close(code=4001, reason="bad token")
                return
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            return
        self.socket = socket
        try:
            async for message in socket:
                if message == "ping":  # keep-alive from the extension
                    continue
                reply = json.loads(message)
                future = self.pending.pop(reply.get("id"), None)
                if future and not future.done():
                    future.set_result(reply.get("result"))
        except websockets.ConnectionClosed:
            pass
        finally:
            if self.socket is socket:
                self.socket = None

    async def _send(self, cmd, args):
        self.next_id += 1
        future = self.loop.create_future()
        self.pending[self.next_id] = future
        await self.socket.send(json.dumps({"id": self.next_id, "cmd": cmd, "args": args}))
        return await asyncio.wait_for(future, 5)

    # ----- called from the brain thread -----

    def call(self, cmd, **args):
        if not self.socket:
            return "Chrome is not connected. Is Chrome open, with the Castorice extension on?"
        try:
            result = asyncio.run_coroutine_threadsafe(self._send(cmd, args), self.loop).result(6)
        except Exception as e:  # timeout or closed connection
            return f"Chrome did not answer: {e}"
        return result if isinstance(result, str) else json.dumps(result)

    def tabs(self):
        """All open tabs as a list of dicts, or None when Chrome is not connected."""
        raw = self.call("list")
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return None

    def find(self, queries, keep=()):
        """Tabs whose title or URL contains one of the words (or whose id matches).
        "all" means every tab. Tabs that match a word in keep are left out."""
        tabs = self.tabs()
        if tabs is None:
            return None
        kept = [t for t in tabs if any(str(k).lower() in (t["title"] + " " + t["url"]).lower() for k in keep if str(k).strip())]
        if any(str(q).lower().strip() in ("all", "everything", "*") for q in queries):
            return [t for t in tabs if t not in kept]
        found = []
        for q in queries:
            q = str(q).lower().strip()
            found += [t for t in tabs if q == str(t["id"]) and t not in found + kept]  # a tab id
            if q in FILLER or len(q) < 2:  # words like "tabs" or "the" would match far too much
                continue
            for t in tabs:
                if (q in t["title"].lower() or q in t["url"].lower()) and t not in found + kept:
                    found.append(t)
        return found

    def list_tabs(self):
        tabs = self.tabs()
        if tabs is None:
            return "Chrome is not connected. Is Chrome open, with the Castorice extension on?"
        return "\n".join(f'{"* " if t["active"] else ""}{t["title"][:70]} | {t["url"][:80]}' for t in tabs)

    def describe(self, tabs, keep=()):
        """For the yes/no question: what exactly would be closed."""
        found = self.find(tabs, keep)
        if found is None:
            return False, "Chrome is not connected."
        if not found:
            return False, f"no tab matches {tabs}. Call list_tabs and use words from the titles."
        names = ", ".join(t["title"][:40] for t in found)
        return True, f"close {'this tab' if len(found) == 1 else f'these {len(found)} tabs'}: {names}"

    def switch_tab(self, tab):
        found = self.find([tab])
        if not found:
            return f'no tab matches "{tab}"'
        return self.call("switch", tab_id=found[0]["id"])

    def open_tab(self, url):
        return self.call("open", url=url)

    def group_tabs(self, tabs, title):
        found = self.find(tabs)
        if not found:
            return f"no tab matches {tabs}"
        return self.call("group", tab_ids=[t["id"] for t in found], title=title)

    def close_tabs(self, tabs, keep=()):
        found = self.find(tabs, keep)
        if not found:
            return f"no tab matches {tabs}"
        return self.call("close", tab_ids=[t["id"] for t in found])
