import type { Metadata } from "next";
import { Space_Grotesk, Space_Mono } from "next/font/google";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { AuthProvider } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ui/use-toast";
import { Toaster } from "@/components/ui/toaster";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({ subsets: ["latin"], variable: '--font-grotesk' });
const spaceMono = Space_Mono({ subsets: ["latin"], weight: ["400", "700"], variable: '--font-mono' });

export const metadata: Metadata = {
  title: "DriftGuard-X",
  description: "Agentic RAG Reliability Platform — Trace, Detect, Recover.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${spaceGrotesk.variable} ${spaceMono.variable} font-sans min-h-screen bg-[#ECEAE2] text-[#0a0a0a] antialiased flex flex-col`}>
        <AuthProvider>
          <ToastProvider>
            <Navbar />
            <div className="mt-12 border-b border-[#b7ffe5]/10 bg-[#07110f] px-4 py-2 text-center font-mono text-[10px] font-bold uppercase tracking-[0.18em] text-[#b7ffe5]/65">
              Evidence-aware research system <span className="mx-2 text-[#7cf7d4]">◆</span> synthetic, replay, and production signals remain explicitly separated
            </div>
            <main className="flex-1 flex flex-col relative">
              {children}
            </main>
            <Footer />
            <Toaster />
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
