import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Django's paths, forwarded by this dev server so one public address (ngrok) serves both the
// reader app at / and the newsroom dashboard at /newsroom/. The Host header and ngrok's
// X-Forwarded-Proto pass through unchanged, so Django builds https://<ngrok host> links.
// Not /fantasy: that is a reader app route here.
const DJANGO = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
const DJANGO_PATHS = ["/api", "/newsroom", "/static", "/admin", "/accounts", "/media"];

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    // host: true so the app is reachable from a phone on the same network (and from Docker).
    host: true,
    port: 5173,
    // Tunnels: ngrok's free static domains (.ngrok-free.dev, older .ngrok-free.app), paid ngrok
    // domains, and Cloudflare quick tunnels.
    allowedHosts: [".ngrok-free.dev", ".ngrok-free.app", ".ngrok.app", ".ngrok.io", ".trycloudflare.com"],
    proxy: Object.fromEntries(DJANGO_PATHS.map((path) => [path, { target: DJANGO }])),
  },
});
