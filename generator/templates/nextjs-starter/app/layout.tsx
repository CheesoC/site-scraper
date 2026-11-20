import type { Metadata } from "next";
import type { ReactNode } from "react";
import Footer from "@/components/layout/Footer";
import Header from "@/components/layout/Header";
import { getSiteLang, getSiteName } from "@/lib/content";
import "./globals.css";

export function generateMetadata(): Metadata {
  const name = getSiteName();
  return {
    title: { default: name, template: `%s` },
    robots: { index: false, follow: false }, // prototype: keep it out of search engines
  };
}

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang={getSiteLang()}>
      <body className="flex min-h-screen flex-col">
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-surface focus:px-3 focus:py-2">
          Zum Inhalt springen
        </a>
        <Header />
        <main id="main" className="flex-1">
          {children}
        </main>
        <Footer />
      </body>
    </html>
  );
}
