import type { Metadata } from "next";
import { GeistMono } from "geist/font/mono";
import { Doto, Inter, VT323 } from "next/font/google";
import { AppShell } from "@/components/layout/AppShell";
import { Providers } from "@/components/layout/Providers";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const doto = Doto({ variable: "--font-doto", subsets: ["latin"], weight: ["700"] });
const vt323 = VT323({ variable: "--font-vt323", subsets: ["latin"], weight: "400" });

export const metadata: Metadata = {
  title: "TRINETRA",
  description: "Evidence-backed threat report analysis mapped to MITRE ATT&CK",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} ${GeistMono.variable} ${doto.variable} ${vt323.variable} font-sans antialiased`}
      >
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
