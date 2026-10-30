import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const jetbrainsMono = JetBrains_Mono({ variable: "--font-jetbrains-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TRINETRA",
  description: "Evidence-backed threat report analysis mapped to MITRE ATT&CK",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans antialiased`}>
        <header className="flex items-center gap-6 border-b border-border px-6 py-3 text-sm">
          <Link href="/" className="font-semibold tracking-widest text-primary">
            TRINETRA
          </Link>
          <Link href="/graph" className="text-muted-foreground hover:text-foreground">
            Memory graph
          </Link>
          <Link href="/eval" className="text-muted-foreground hover:text-foreground">
            Scoreboard
          </Link>
        </header>
        {children}
      </body>
    </html>
  );
}
