/// <reference types="vitest/config" />
import { createReadStream } from "node:fs";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

const require = createRequire(import.meta.url);
const pdfjsWasm = join(dirname(require.resolve("pdfjs-dist/package.json")), "wasm");

// The decoders pdf.js needs for the images scanners write (JBIG2, JPEG 2000)
// and for colour profiles: served under /pdfjs/wasm/, copied from the package
// rather than kept in the repository.
const WASM_FILES = ["jbig2.wasm", "openjpeg.wasm", "qcms_bg.wasm"];

function pdfjsWasmFiles(): Plugin {
  return {
    name: "editpdf-pdfjs-wasm",
    configureServer(server) {
      server.middlewares.use("/pdfjs/wasm/", (request, response, next) => {
        const name = (request.url ?? "").replace(/^\//, "").split("?")[0] ?? "";
        if (!WASM_FILES.includes(name)) {
          next();
          return;
        }
        response.setHeader("content-type", "application/wasm");
        createReadStream(join(pdfjsWasm, name)).pipe(response);
      });
    },
    async generateBundle() {
      for (const name of WASM_FILES) {
        this.emitFile({ type: "asset", fileName: `pdfjs/wasm/${name}`, source: await readFile(join(pdfjsWasm, name)) });
      }
    },
  };
}

// `npm run dev` serves the interface on :5173 and sends the API to the
// backend's dev server (`npm run dev:api`, :8787).
export default defineConfig({
  plugins: [react(), pdfjsWasmFiles()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8787",
      "/problems": "http://127.0.0.1:8787",
    },
  },
  build: {
    target: "es2022",
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: false,
    // pdf.js is large and loaded only once a document is dropped.
    chunkSizeWarningLimit: 1400,
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
