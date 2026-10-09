#!/usr/bin/env node
// AQ Bot token server.
//
// Receives the AfterQuery session token from the browser extension and writes it
// to token.txt (raw JWT) plus token.json (metadata) so the automation can read a
// live, always-fresh token. No dependencies — plain Node http.
//
// Run:  node token_write.js            (listens on 127.0.0.1:47615)
//   env KEPLER_TOKEN_PORT   override port (default 47615)
//   env KEPLER_TOKEN_FILE   override token.txt path (default ./token.txt)
//
// Endpoints:
//   GET  /ping    -> {ok:true, app:"aqbot"}         (extension reachability probe)
//   POST /token   -> {token} ; writes files ; -> {ok, email, exp, validMinutes}
//   GET  /status  -> current token metadata (no token value)

const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.KEPLER_TOKEN_PORT || 47615);
const HOST = process.env.KEPLER_TOKEN_HOST || "127.0.0.1";
const TOKEN_FILE = process.env.KEPLER_TOKEN_FILE || path.join(__dirname, "token.txt");
const META_FILE = TOKEN_FILE.replace(/\.txt$/, "") + ".json";
const COOKIE_FILE = process.env.KEPLER_COOKIE_FILE || path.join(__dirname, "cookies.txt");
// Shared secret. When set, /token and /status require header `x-aq-secret` (or ?secret=).
// STRONGLY recommended when binding to a public interface (0.0.0.0) — otherwise anyone
// who can reach the port can push a token or read your account email.
const SECRET = process.env.KEPLER_TOKEN_SECRET || "";

function authorized(req) {
  if (!SECRET) return true;
  const hdr = req.headers["x-aq-secret"];
  if (hdr && hdr === SECRET) return true;
  try {
    const u = new URL(req.url, "http://x");
    if (u.searchParams.get("secret") === SECRET) return true;
  } catch {}
  return false;
}

function decodePayload(token) {
  try {
    const part = token.split(".")[1];
    const json = Buffer.from(part.replace(/-/g, "+").replace(/_/g, "/"), "base64").toString("utf8");
    return JSON.parse(json);
  } catch {
    return {};
  }
}

function currentMeta() {
  try {
    return JSON.parse(fs.readFileSync(META_FILE, "utf8"));
  } catch {
    return {};
  }
}

// CORS + Chrome Private Network Access (extension -> loopback needs this).
function cors(res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "content-type, x-aq-secret");
  res.setHeader("Access-Control-Allow-Private-Network", "true");
}

function send(res, code, obj) {
  cors(res);
  res.setHeader("Content-Type", "application/json");
  res.writeHead(code);
  res.end(JSON.stringify(obj));
}

const server = http.createServer((req, res) => {
  if (req.method === "OPTIONS") {
    cors(res);
    res.writeHead(204);
    res.end();
    return;
  }

  const route = req.url.split("?")[0];

  // /ping stays open (unauthenticated) so reachability checks work.
  if (req.method === "GET" && route === "/ping") {
    return send(res, 200, { ok: true, app: "aqbot" });
  }

  if ((route === "/status" || route === "/token") && !authorized(req)) {
    return send(res, 401, { ok: false, error: "unauthorized (bad or missing x-aq-secret)" });
  }

  if (req.method === "GET" && route === "/status") {
    const m = currentMeta();
    const validMin = m.exp ? Math.round((m.exp * 1000 - Date.now()) / 60000) : null;
    return send(res, 200, { ok: true, email: m.email || null, exp: m.exp || null, validMinutes: validMin, capturedAt: m.capturedAt || null });
  }

  if (req.method === "POST" && route === "/token") {
    let body = "";
    req.on("data", (c) => {
      body += c;
      if (body.length > 1e6) req.destroy();
    });
    req.on("end", () => {
      let token, cookies;
      try {
        const parsed = JSON.parse(body);
        token = parsed.token;
        cookies = parsed.cookies;
      } catch {
        return send(res, 400, { ok: false, error: "bad json" });
      }
      // Persist cookies (Vercel challenge cookie) so the client can pass the checkpoint.
      if (typeof cookies === "string" && cookies) {
        try {
          fs.writeFileSync(COOKIE_FILE, cookies, "utf8");
        } catch {}
      }
      if (!token || typeof token !== "string" || token.split(".").length !== 3) {
        return send(res, 400, { ok: false, error: "not a jwt" });
      }
      const p = decodePayload(token);
      const exp = Number(p.exp) || 0;

      // Only accept a newer (later-expiring) token than what we already hold.
      const cur = currentMeta();
      if (cur.exp && exp && exp < cur.exp) {
        return send(res, 200, { ok: true, email: cur.email || null, exp: cur.exp, note: "kept newer existing token" });
      }

      const meta = { email: p.email || null, exp, capturedAt: Date.now() };
      try {
        fs.writeFileSync(TOKEN_FILE, token, "utf8");
        fs.writeFileSync(META_FILE, JSON.stringify(meta, null, 2), "utf8");
      } catch (e) {
        return send(res, 500, { ok: false, error: String(e && e.message) });
      }
      const validMin = exp ? Math.round((exp * 1000 - Date.now()) / 60000) : null;
      const stamp = new Date().toLocaleTimeString();
      console.log(`[${stamp}] token written for ${meta.email || "unknown"} (valid ~${validMin}m) -> ${TOKEN_FILE}`);
      return send(res, 200, { ok: true, email: meta.email, exp, validMinutes: validMin });
    });
    return;
  }

  send(res, 404, { ok: false, error: "not found" });
});

server.listen(PORT, HOST, () => {
  console.log(`AQ Bot token server on http://${HOST}:${PORT}`);
  console.log(`  writing: ${TOKEN_FILE}`);
  console.log(`  auth: ${SECRET ? "shared secret REQUIRED on /token + /status" : "OPEN (no secret)"}`);
  if (HOST === "0.0.0.0" && !SECRET) {
    console.warn("  WARNING: bound to all interfaces with NO secret — anyone who can reach this");
    console.warn("           port can push a token or read your account email. Set KEPLER_TOKEN_SECRET.");
  }
});
