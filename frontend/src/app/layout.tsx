import type { Metadata } from "next";
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
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
