"""Window tools (Hyprland)."""
from runner import Result
from tools.common import dispatch, hypr_json

# ---------- windows ----------

def list_windows(runner):
    rows = [f'{w["class"]} | {w["title"][:60]} | workspace {w["workspace"]["name"]}'
            for w in hypr_json(runner, "clients") if w.get("mapped") and w["class"] != "companion"]
    return Result(True, "\n".join(rows) or "no windows", untrusted=True)


def find_window(runner, query):
    """Return the address of the first window whose class or title contains query."""
    q = query.lower()
    for w in hypr_json(runner, "clients"):
        if q in w["class"].lower() or q in w["title"].lower():
            return w["address"]
    return None


def window_action(lua_template):
    def run(runner, window):
        addr = find_window(runner, window)
        if not addr:
            return Result(False, f'no window matches "{window}"', final=True)
        return dispatch(runner, lua_template.format(sel=f"address:{addr}"))
    return run


def describe_window(runner, window):
    for w in hypr_json(runner, "clients"):
        if window.lower() in w["class"].lower() or window.lower() in w["title"].lower():
            return True, f'close the window "{w["title"][:50]}" ({w["class"]})'
    return False, f'no window matches "{window}". Call list_windows first.'


def move_window(runner, window, workspace):
    addr = find_window(runner, window)
    if not addr:
        return Result(False, f'no window matches "{window}"', final=True)
    return dispatch(runner, f'hl.dsp.window.move({{ window = "address:{addr}", workspace = {int(workspace)} }})')
