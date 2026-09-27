/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // `next build` and `next dev` share .next by default, so a verification build
  // run while the dev server is up deletes the chunks it has already loaded and
  // the running app dies with "Cannot find module ./vendor-chunks/...".
  // Set NEXT_DIST_DIR to build into a scratch directory instead.
  distDir: process.env.NEXT_DIST_DIR || '.next',
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
