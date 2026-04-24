import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";

import { QueryProvider } from "@/providers/query-provider";

export const metadata: Metadata = {
  title: "PokéCollect",
  description: "Telegram Mini App for PokéCollect",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
