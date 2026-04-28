import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Swing Trading Screener",
  description: "Screener swing trading multi-critères",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="h-full" suppressHydrationWarning>
      <body className="min-h-full" style={{ background: "#0a0a0f", color: "#e2e8f0" }} suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
