import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "DriftGuard-X Web Console",
  description: "Agentic RAG Reliability Investigation Console",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} min-h-screen bg-black text-slate-200 antialiased`}>
        {children}
      </body>
    </html>
  );
}
