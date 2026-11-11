import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api va /media so'rovlari Django'ga uzatiladi (CORS muammosi bo'lmaydi).
// changeOrigin: tunnel (ngrok va h.k.) orqali kirilganda Django ALLOWED_HOSTS xatosi chiqmasligi uchun.
// allowedHosts: Telegram Mini App uchun tashqi (https) manzildan ochishga ruxsat.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/media": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
