import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AI Assistant",
  description: "A ChatGPT-like AI assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      {/* h-full (not min-h-full) + overflow-hidden pins the body to exactly the viewport height,
          so a long chat can never grow the page itself - every route already manages its own
          overflow-y-auto region (the chat message list, the sidebar's conversation list, the
          shared-page transcript), and without this cap the body would grow past the viewport
          and the whole page - sidebar included - would scroll together as one unit. */}
      <body className="h-full flex flex-col overflow-hidden">
        {/* Blocking script (runs before paint) so the stored theme applies immediately -
            without this, the page would flash the default light theme before React hydrates
            and ThemeProvider's effect runs. suppressHydrationWarning above because this script
            intentionally mutates <html>'s class before React can compare it to the server render. */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              "(function(){try{var t=localStorage.getItem('theme');var d=t==='dark'||(t!=='light'&&window.matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.classList.toggle('dark',d);}catch(e){}})();",
          }}
        />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
