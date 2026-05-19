import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kogni — Cognitive Health Monitor",
  description: "Passive cognitive health infrastructure",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Nunito:wght@400;700;900&family=VT323&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ margin: 0, padding: 0 }}>{children}</body>
    </html>
  );
}
