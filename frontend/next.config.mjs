import { fileURLToPath } from 'node:url';

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `next build` and `next dev` share .next by default, so a verification build
  // run while the dev server is up deletes the chunks it has already loaded and
  // the running app dies with "Cannot find module ./vendor-chunks/...".
  // Set NEXT_DIST_DIR to build into a scratch directory instead.
  distDir: process.env.NEXT_DIST_DIR || '.next',
  webpack(config) {
    // The studio editor (frontend/opencut) transcribes in the browser with
    // @huggingface/transformers; webpack still follows its Node build, whose native
    // onnxruntime and sharp binaries can't be bundled and are never used in a browser.
    // Its timeline maths runs in opencut-wasm, whose .wasm webpack can't parse; the shim
    // fetches it as a plain file instead (see opencut/src/clipnera/opencut-wasm.ts).
    config.resolve.alias = {
      ...config.resolve.alias,
      'onnxruntime-node$': false,
      sharp$: false,
      'opencut-wasm$': fileURLToPath(new URL('./opencut/src/clipnera/opencut-wasm.ts', import.meta.url)),
    };
    config.module.rules.push({ test: /opencut_wasm_bg\.wasm$/, type: 'asset/resource' });
    return config;
  },
  async headers() {
    return [
      {
        // OAuth callbacks carry an authorization code in the URL; never send it on as a Referer.
        source: '/dashboard/connect/:platform',
        headers: [{ key: 'Referrer-Policy', value: 'no-referrer' }],
      },
      {
        source: '/login/google',
        headers: [{ key: 'Referrer-Policy', value: 'no-referrer' }],
      },
    ];
  },
};

export default nextConfig;
