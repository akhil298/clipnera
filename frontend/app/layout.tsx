import type { Metadata } from "next";
import "./globals.css";

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
      </head>
      <body className="bg-neutral-950 text-neutral-100 font-['Plus_Jakarta_Sans',sans-serif] selection:bg-amber-400 selection:text-neutral-950 overflow-x-hidden antialiased">
        {children}
      </body>
    </html>
  );
}
