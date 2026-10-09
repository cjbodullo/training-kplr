// Runs on experts.afterquery.com. Reads the Firebase ID token from the page's
// IndexedDB and forwards it to the background service worker. Polls periodically
// and on tab focus so the token stays fresh.

function readFirebaseToken() {
  return new Promise((resolve) => {
    let db;
    try {
      const req = indexedDB.open("firebaseLocalStorageDb");
      req.onsuccess = () => {
        db = req.result;
        let store;
        try {
          store = db.transaction("firebaseLocalStorage", "readonly").objectStore("firebaseLocalStorage");
        } catch {
          resolve(null);
          return;
        }
        const all = store.getAll();
        all.onsuccess = () => {
          let best = null;
          for (const row of all.result || []) {
            const stm = row?.value?.stsTokenManager;
            if (stm && stm.accessToken) {
              const exp = Number(stm.expirationTime) || 0;
              if (!best || exp > best.exp) {
                best = {
                  token: stm.accessToken,
                  exp,
                  email: row.value.email || null,
                  // refresh token + web api key let the background worker mint a
                  // fresh id token on its own, without needing a page refresh.
                  refreshToken: stm.refreshToken || null,
                  apiKey: row.value.apiKey || null,
                };
              }
            }
          }
          resolve(best);
        };
        all.onerror = () => resolve(null);
      };
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

async function pushToken() {
  const best = await readFirebaseToken();
  if (best?.token) {
    chrome.runtime.sendMessage({
      type: "aq-token",
      token: best.token,
      exp: best.exp,
      email: best.email,
      refreshToken: best.refreshToken,
      apiKey: best.apiKey,
    });
  }
}

pushToken();
setInterval(pushToken, 60_000);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") pushToken();
});
