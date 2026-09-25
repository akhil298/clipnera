import type { Metadata } from "next";
import "./globals.css";
import Script from "next/script";

export const metadata: Metadata = {
  title: "Clipnera — AI Video Editing & Shorts Creator",
  description: "Transform raw videos into stunning shorts and long-form content with AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning={true}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800;900&family=Syne:wght@700;800;900&family=JetBrains+Mono:wght@500;700&display=swap"
          rel="stylesheet"
        />
        {/* Caption faces, mirroring the files bundled in backend/static/fonts for burn-in. */}
        <link
          href="https://fonts.googleapis.com/css2?family=Anton&family=Archivo+Black&family=Bangers&family=Bebas+Neue&family=DM+Serif+Display&family=Luckiest+Guy&family=Permanent+Marker&display=swap"
          rel="stylesheet"
        />
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
      </body>
    </html>
  );
}
