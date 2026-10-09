// PM2 process config for the AQ Bot token server.
//
//   pm2 start ecosystem.config.js     # start (or reload) the token server
//   pm2 logs kepler-token-server      # tail logs (token writes print here)
//   pm2 save                          # persist across reboots (after pm2 startup)
//   pm2 restart kepler-token-server
//   pm2 stop kepler-token-server
//
// Override port/host/token path via env below.

module.exports = {
  apps: [
    {
      name: "kepler-token-server",
      script: "token_write.js",
      cwd: __dirname,
      instances: 1,
      exec_mode: "fork",
      autorestart: true,
      watch: false,
      max_restarts: 20,
      restart_delay: 2000,
      env: {
        KEPLER_TOKEN_PORT: "47615",
        // Bind to all interfaces so the browser can reach the VPS public IP.
        KEPLER_TOKEN_HOST: "0.0.0.0",
        // STRONGLY recommended when public: set a shared secret and put the SAME
        // value in the extension popup. Generate one: openssl rand -hex 24
        KEPLER_TOKEN_SECRET: "0b03412b77e49a70e73fcbadd27c08f2bcd3c5332d79dd52",
        // KEPLER_TOKEN_FILE: "/home/Afterquery/kepler-tools/token.txt",
      },
    },
  ],
};
