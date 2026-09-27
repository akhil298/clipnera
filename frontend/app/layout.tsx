import type { Metadata } from "next";
import "./globals.css";
import Script from "next/script";
import { CookieNotice } from "@/components/legal/CookieNotice";
// Fonts are self-hosted (SIL OFL 1.1 / Apache 2.0) so pages make no request to Google Fonts.
import "@fontsource/plus-jakarta-sans/400.css";
import "@fontsource/plus-jakarta-sans/500.css";
import "@fontsource/plus-jakarta-sans/600.css";
import "@fontsource/plus-jakarta-sans/700.css";
import "@fontsource/plus-jakarta-sans/800.css";
import "@fontsource/syne/700.css";
import "@fontsource/syne/800.css";
import "@fontsource/jetbrains-mono/500.css";
import "@fontsource/jetbrains-mono/700.css";
// Caption faces, mirroring the files bundled in backend/static/fonts for burn-in.
import "@fontsource/anton/400.css";
import "@fontsource/archivo-black/400.css";
import "@fontsource/bangers/400.css";
import "@fontsource/bebas-neue/400.css";
import "@fontsource/dm-serif-display/400.css";
import "@fontsource/luckiest-guy/400.css";
import "@fontsource/permanent-marker/400.css";

export const metadata: Metadata = {
  title: "Clipnera — AI Video Editing & Shorts Creator",
  description: "Transform raw videos into stunning shorts and long-form content with AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning={true}>
      <head>
        {/* React Grab (dev only): hover a component and press ⌘C to copy its source location and context. */}
        {process.env.NODE_ENV === "development" && (
          <Script
            src="https://unpkg.com/react-grab/dist/index.global.js"
            crossOrigin="anonymous"
            strategy="beforeInteractive"
          />
        )}
        <Script
          id="hydration-fix"
          strategy="beforeInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                const ATTRS = ['data-new-gr-c-s-check-loaded', 'data-gr-ext-installed'];
                const removeAttrs = () => {
                  document.querySelectorAll('[' + ATTRS.join('],[') + ']').forEach(el => {
                    ATTRS.forEach(attr => el.removeAttribute(attr));
                  });
                };
                let observer;
                const startObserver = () => {
                  if (observer) return;
                  removeAttrs();
                  observer = new MutationObserver(() => removeAttrs());
                  observer.observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ATTRS });
                };
                if (document.readyState === 'loading') {
                  document.addEventListener('DOMContentLoaded', startObserver);
                } else {
                  startObserver();
                }
              })();
            `,
          }}
        />
      </head>
      <body className="bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif] selection:bg-amber-400 selection:text-neutral-950 overflow-x-hidden antialiased" suppressHydrationWarning={true}>
        {children}
        <CookieNotice />
      </body>
    </html>
  );
}
