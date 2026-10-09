// Service worker: collects the AfterQuery token (from the content script and by
// sniffing Authorization headers) and pushes it to the configured AQ Bot API
// using the pairing token as a bearer.

const AQ_HOST = "https://experts.afterquery.com";
// The token server URL is configurable from the popup (stored in chrome.storage).
// Defaults to the loopback listener if the user has not set one.
const DEFAULT_APP_URL = "http://127.0.0.1:47615";

async function appUrl() {
  const { serverUrl } = await chrome.storage.local.get(["serverUrl"]);
  return (serverUrl || DEFAULT_APP_URL).replace(/\/+$/, "");
}

async function appSecret() {
  const { serverSecret } = await chrome.storage.local.get(["serverSecret"]);
  return serverSecret || "";
}

function decodeExp(token) {
  try {
    const p = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
    return typeof p.exp === "number" ? p.exp : 0;
  } catch {
    return 0;
  }
}

/** Keep the token with the latest expiry in storage; push it when it changes. */
async function considerToken(token, email) {
  if (!token) return;
  const exp = decodeExp(token);
  const cur = await chrome.storage.local.get(["token", "exp"]);
  if (cur.token === token || (cur.exp && exp && exp <= cur.exp)) return; // not newer
  await chrome.storage.local.set({ token, exp, email: email || cur.email || null, capturedAt: Date.now() });
  await pushToApp(token);
}

// Collect experts.afterquery.com cookies (incl. the Vercel challenge cookie
// _vcrcs) so the headless client can pass the Vercel Security Checkpoint.
async function collectCookies() {
  try {
    const cks = await chrome.cookies.getAll({ domain: "afterquery.com" });
    return cks.map((c) => `${c.name}=${c.value}`).join("; ");
  } catch {
    return "";
  }
}

async function pushToApp(token) {
  const url = await appUrl();
  const secret = await appSecret();
  const cookies = await collectCookies();
  try {
    const headers = { "Content-Type": "application/json" };
    if (secret) headers["x-aq-secret"] = secret;
    const res = await fetch(`${url}/token`, {
      method: "POST",
      headers,
      body: JSON.stringify({ token, cookies }),
    });
    const body = await res.json().catch(() => ({}));
    await chrome.storage.local.set({
      lastPush: res.ok ? `synced ${body.email || ""} ${new Date().toLocaleTimeString()}` : `server rejected (${res.status})`,
      lastPushOk: res.ok,
    });
  } catch (e) {
    // Distinguish "server closed" from other failures (e.g. Private Network Access).
    const reachable = await fetch(`${url}/ping`).then((r) => r.ok).catch(() => false);
    await chrome.storage.local.set({
      lastPush: reachable ? `sync blocked: ${e?.message || "fetch failed"}` : "token server not running (start token_write.js)",
      lastPushOk: false,
    });
  }
}

// Mint a FRESH id token from the long-lived refresh token via Google's secure
// token endpoint — works even when the page is idle (no page refresh needed).
async function refreshViaSecureToken() {
  const { refreshToken, apiKey } = await chrome.storage.local.get(["refreshToken", "apiKey"]);
  if (!refreshToken || !apiKey) return false;
  try {
    const res = await fetch(`https://securetoken.googleapis.com/v1/token?key=${apiKey}`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: `grant_type=refresh_token&refresh_token=${encodeURIComponent(refreshToken)}`,
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.refresh_token) await chrome.storage.local.set({ refreshToken: data.refresh_token });
    const idToken = data.id_token || data.access_token;
    if (idToken) {
      await considerToken(idToken);
      return true;
    }
  } catch {}
  return false;
}

// Refresh if the current token is within 25 min of expiry, then push the freshest.
async function maintain() {
  const { exp } = await chrome.storage.local.get(["exp"]);
  const minsLeft = exp ? (exp * 1000 - Date.now()) / 60000 : -1;
  if (minsLeft < 25) await refreshViaSecureToken();
  await repush();
}

// 1. Token from the content script (IndexedDB read) — also carries refresh creds.
chrome.runtime.onMessage.addListener((msg) => {
  if (msg?.type === "aq-token") {
    if (msg.refreshToken && msg.apiKey) {
      chrome.storage.local.set({ refreshToken: msg.refreshToken, apiKey: msg.apiKey });
    }
    considerToken(msg.token, msg.email);
  }
  if (msg?.type === "aq-repush") maintain();
});

// 2. Token by sniffing the Authorization header on AfterQuery API calls.
chrome.webRequest.onBeforeSendHeaders.addListener(
  (details) => {
    const h = details.requestHeaders?.find((x) => x.name.toLowerCase() === "authorization");
    const v = h?.value || "";
    if (v.startsWith("Bearer ")) considerToken(v.slice(7));
  },
  { urls: [`${AQ_HOST}/*`] },
  ["requestHeaders"],
);

// 3. Every minute, refresh-if-near-expiry (via securetoken) and push the freshest
//    token — this keeps token.txt fresh with NO manual sync and NO page refresh.
chrome.alarms.create("repush", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((a) => {
  if (a.name === "repush") maintain();
});
// Also refresh right when the worker starts.
maintain();

async function repush() {
  const { token } = await chrome.storage.local.get(["token"]);
  if (token) await pushToApp(token);
}
