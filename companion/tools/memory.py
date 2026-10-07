"""Long-term memory: facts about the user, kept by the store."""
import re

from runner import Result

# ---------- memory ----------

MEMORY_LIMIT = 50
STOP_WORDS = {"the", "a", "an", "my", "i", "me", "about", "that", "this", "thing", "stuff", "please", "of", "to", "and"}


def remember(store, fact):
    facts = store.memory()
    fact = " ".join(str(fact).split())[:300]
    if not fact or fact in facts:
        return Result(True, "remembered")
    facts.append(fact)
    dropped = facts[:-MEMORY_LIMIT]
    store.save_memory(facts[-MEMORY_LIMIT:])
    if dropped:
        return Result(True, f'remembered. Memory is full, so the oldest fact was dropped: "{dropped[0][:80]}"')
    return Result(True, "remembered")


def matching_memories(store, words):
    """Memories that contain all the given words as whole words (small words do not count)."""
    keys = [w for w in re.findall(r"[\w'-]+", str(words).lower()) if w not in STOP_WORDS]
    if not keys:
        return []
    return [f for f in store.memory() if all(re.search(rf"\b{re.escape(k)}\b", f.lower()) for k in keys)]


def recall(store, words):
    hits = matching_memories(store, words)
    return Result(True, "\n".join(hits), untrusted=True) if hits else Result(False, "nothing in memory about that", final=True)


def forget(store, words):
    hits = matching_memories(store, words)
    store.save_memory([f for f in store.memory() if f not in hits])
    return Result(True, f"forgot {len(hits)} memories")


def preview_forget(store, words):
    hits = matching_memories(store, words)
    if not hits:
        return False, "nothing in memory matches all of those words. Call recall to see the memories."
    more = f" (and {len(hits) - 5} more)" if len(hits) > 5 else ""
    return True, f"forget these {len(hits)} memories: " + "; ".join(h[:60] for h in hits[:5]) + more
