// Castorice Tabs: a local bridge between Chrome and the Castorice companion.
// It connects only to ws://127.0.0.1:8765 and sends the token from token.js first.
importScripts("token.js"); // defines CASTORICE_TOKEN (made by setup.sh)

const URL = "ws://127.0.0.1:8765";
let socket = null;

const commands = {
  async list() {
    const tabs = await chrome.tabs.query({});
    return tabs.map(t => ({ id: t.id, title: t.title, url: t.url, active: t.active, window: t.windowId }));
  },
  async switch({ tab_id }) {
    const tab = await chrome.tabs.update(tab_id, { active: true });
    await chrome.windows.update(tab.windowId, { focused: true });
    return `switched to: ${tab.title}`;
  },
  async open({ url }) {
    if (!/^https?:\/\//.test(url)) url = "https://" + url;
    const tab = await chrome.tabs.create({ url });
    return `opened tab ${tab.id}`;
  },
  async group({ tab_ids, title }) {
    const groupId = await chrome.tabs.group({ tabIds: tab_ids });
    await chrome.tabGroups.update(groupId, { title });
    return `grouped ${tab_ids.length} tabs as "${title}"`;
  },
  async close({ tab_ids }) {
    await chrome.tabs.remove(tab_ids);
    return `closed ${tab_ids.length} tabs`;
  },
};

function connect() {
  if (socket && socket.readyState <= WebSocket.OPEN) return;
  socket = new WebSocket(URL);
  socket.onopen = () => socket.send(CASTORICE_TOKEN);
  socket.onmessage = async (event) => {
    const { id, cmd, args } = JSON.parse(event.data);
    let result;
    try {
      result = commands[cmd] ? await commands[cmd](args || {}) : `unknown command ${cmd}`;
    } catch (e) {
      result = `error: ${e.message}`;
    }
    socket.send(JSON.stringify({ id, result }));
  };
  socket.onclose = () => { socket = null; };
}

// Keep the service worker alive while connected, and reconnect when the companion restarts.
setInterval(() => { if (socket && socket.readyState === WebSocket.OPEN) socket.send("ping"); else connect(); }, 20000);
chrome.alarms.create("reconnect", { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(connect);
connect();
