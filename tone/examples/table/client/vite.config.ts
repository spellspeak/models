import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      // The cast lives beside client/ and server/, shared with the bot.
      "@cast": path.resolve(__dirname, "../characters.json"),
    },
  },
  server: { fs: { allow: [".."] } },
})
