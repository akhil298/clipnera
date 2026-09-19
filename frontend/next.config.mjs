/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `next build` and `next dev` share .next by default, so a verification build
  // run while the dev server is up deletes the chunks it has already loaded and
  // the running app dies with "Cannot find module ./vendor-chunks/...".
  // Set NEXT_DIST_DIR to build into a scratch directory instead.
  distDir: process.env.NEXT_DIST_DIR || '.next',
};

export default nextConfig;
