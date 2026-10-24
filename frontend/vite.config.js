import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // host: true so the app is reachable from a phone on the same network (and from Docker).
  server: { host: true, port: 5173 },
});
