import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Frontend /api va /media so'rovlarini Django'ga uzatadi (CORS muammosi bo'lmaydi).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
    },
  },
});
