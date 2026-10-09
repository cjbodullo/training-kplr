const $ = (id) => document.getElementById(id);
const DEFAULT_URL = "http://127.0.0.1:47615";

async function render() {
  const s = await chrome.storage.local.get(["token", "exp", "email", "lastPush", "lastPushOk", "serverUrl", "serverSecret"]);
  $("serverUrl").value = s.serverUrl || DEFAULT_URL;
  $("serverSecret").value = s.serverSecret || "";
  const parts = [];
  if (s.email) parts.push(`<div class="muted">account: ${s.email}</div>`);
  if (s.exp) {
    const mins = Math.round((s.exp * 1000 - Date.now()) / 60000);
    parts.push(`<div class="muted">token valid ~${mins}m</div>`);
  } else {
    parts.push(`<div class="muted">no token yet — open experts.afterquery.com and sign in</div>`);
  }
  if (s.lastPush) parts.push(`<div class="${s.lastPushOk ? "ok" : "err"}">${s.lastPush}</div>`);
  $("status").innerHTML = parts.join("");
}

$("save").addEventListener("click", async () => {
  const url = ($("serverUrl").value || DEFAULT_URL).trim().replace(/\/+$/, "");
  const secret = ($("serverSecret").value || "").trim();
  await chrome.storage.local.set({ serverUrl: url, serverSecret: secret });
  $("status").textContent = "settings saved, syncing…";
  chrome.runtime.sendMessage({ type: "aq-repush" });
  setTimeout(render, 800);
});

$("sync").addEventListener("click", async () => {
  $("status").textContent = "syncing…";
  chrome.runtime.sendMessage({ type: "aq-repush" });
  setTimeout(render, 800);
});

render();
