import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NewsFinance",
  description:
    "Market-impact intelligence: trasforma eventi in ipotesi verificabili sui mercati.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
