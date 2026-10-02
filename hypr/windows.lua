-- Window behaviour: tiling by default (Hyprland arranges windows), floating per
-- workspace with Super+T, snap, maximize, minimize, Alt+Tab.
-- Other files and hyprctl can call these functions through the global "Desk":
--   hyprctl dispatch 'Desk.minimize'

Desk = {}

local GAP = 8
local MINIMIZED = "special:minimized"

local floating_workspaces = {} -- workspace id -> true when floating mode is on
local saved_geometry = {}      -- window address -> { x, y, w, h } before a snap

local function dispatch(d) hl.dispatch(d) end

local function notify(text)
    hl.exec_cmd("notify-send -t 1500 -a Desktop '" .. text .. "'")
end

-- Free area of the monitor: the monitor minus the bars.
local function work_area(m)
    local r = m.reserved or {}
    local x = m.x + (r.left or 0) + GAP
    local y = m.y + (r.top or 0) + GAP
    local w = m.width - (r.left or 0) - (r.right or 0) - 2 * GAP
    local h = m.height - (r.top or 0) - (r.bottom or 0) - 2 * GAP
    return x, y, w, h
end

-- Resize first: a resize keeps the window center, so a move after it is exact.
local function place(win, x, y, w, h)
    dispatch(hl.dsp.window.resize({ window = win, x = w, y = h, relative = false }))
    dispatch(hl.dsp.window.move({ window = win, x = x, y = y, relative = false }))
end

-- Tiling by default. New windows float only on workspaces in floating mode.
hl.on("window.open", function(win)
    local ws = win and win.workspace
    if ws and not ws.special and floating_workspaces[ws.id] and not win.floating then
        dispatch(hl.dsp.window.float({ window = win, action = "enable" }))
    end
end)

-- Super+T: floating mode on or off for the current workspace.
function Desk.toggle_floating()
    local ws = hl.get_active_workspace()
    if not ws then return end
    local float = not floating_workspaces[ws.id]
    floating_workspaces[ws.id] = float or nil
    for _, win in ipairs(ws:get_windows()) do
        dispatch(hl.dsp.window.float({ window = win, action = float and "enable" or "disable" }))
    end
    notify(float and "Floating on" or "Tiling on")
end

-- Super+Left/Right: snap the active window to half of the screen.
function Desk.snap(side)
    local win = hl.get_active_window()
    if not win then return end
    if not win.floating then  -- tiled: move it one place in the layout
        dispatch(hl.dsp.window.move({ window = win, direction = side }))
        return
    end
    local m = win.monitor or hl.get_active_monitor()
    if not saved_geometry[win.address] then
        saved_geometry[win.address] = { x = win.at.x, y = win.at.y, w = win.size.x, h = win.size.y }
    end
    if win.fullscreen ~= 0 then
        dispatch(hl.dsp.window.fullscreen({ window = win, action = "unset" }))
    end
    local x, y, w, h = work_area(m)
    local half = math.floor((w - GAP) / 2)
    if side == "left" then
        place(win, x, y, half, h)
    else
        place(win, x + half + GAP, y, half, h)
    end
end

-- Super+Up: maximize (the bars stay visible).
function Desk.maximize()
    dispatch(hl.dsp.window.fullscreen({ mode = "maximized", action = "set" }))
end

-- Super+Down: undo maximize, or undo a snap.
function Desk.restore()
    local win = hl.get_active_window()
    if not win then return end
    if win.fullscreen ~= 0 then
        dispatch(hl.dsp.window.fullscreen({ window = win, action = "unset" }))
        return
    end
    local g = saved_geometry[win.address]
    if g then
        place(win, g.x, g.y, g.w, g.h)
        saved_geometry[win.address] = nil
    end
end

-- Minimize: move the window to a hidden special workspace.
function Desk.minimize()
    local win = hl.get_active_window()
    if win then
        dispatch(hl.dsp.window.move({ window = win, workspace = MINIMIZED, follow = false }))
    end
end

-- Restore a minimized window to the workspace on screen, focused and on top.
local function restore(win)
    local target = hl.get_active_workspace()
    dispatch(hl.dsp.window.move({ window = win, workspace = target.id, follow = true }))
    dispatch(hl.dsp.focus({ window = "address:" .. win.address }))
    dispatch(hl.dsp.window.alter_zorder({ window = win, mode = "top" }))
    if hl.get_active_special_workspace() then
        dispatch(hl.dsp.workspace.toggle_special("minimized"))
    end
end

local function minimized(win)
    return win and win.workspace and win.workspace.name == MINIMIZED
end

-- A taskbar click asks Hyprland to activate the window. When it gets focus, restore it.
hl.on("window.active", function(win)
    if minimized(win) then restore(win) end
end)

-- With focus_on_activate off, Hyprland only marks the window urgent. Restore it when the
-- pointer is on the taskbar (a click there); an app that only wants attention stays hidden.
TASKBAR_ZONE = 90 -- px from the bottom edge of the screen
hl.on("window.urgent", function(win)
    if not minimized(win) then return end
    local pointer, monitor = hl.get_cursor_pos(), hl.get_active_monitor()
    if pointer.y > monitor.y + monitor.height - TASKBAR_ZONE then
        restore(win)
    end
end)

-- Alt+Tab: focus the next window and raise it.
function Desk.cycle(forward)
    dispatch(hl.dsp.window.cycle_next({ next = forward }))
    dispatch(hl.dsp.window.alter_zorder({ mode = "top" }))
end
