# AQ Bot Token Bridge (Chrome extension)

Captures your AfterQuery session token in your **normal browser** (where Google
sign-in works — Google blocks sign-in inside the desktop app's embedded window)
and pushes it to the **AQ Bot desktop app** running locally.

## Install

1. Open `chrome://extensions`, enable **Developer mode**.
2. **Load unpacked** → select this `extension` folder.

## Use

1. Open the **AQ Bot desktop app** (it must be running — it listens on
   `127.0.0.1:47615`).
2. In Chrome, open **experts.afterquery.com** and sign in with Google as usual.
3. The extension captures your token and syncs it to the app automatically. The
   account shows up in **AQ Bot → Settings → Connected accounts**.

Add more accounts by signing into each one in Chrome — they all sync to the app.

Click the extension icon to see status / force a re-sync. To check the app is
reachable, open `http://127.0.0.1:47615/ping` — it should return
`{"ok":true,"app":"aqbot"}`.

No pairing code, no server — the token never leaves your machine.
