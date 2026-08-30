import type { Metadata } from "next";
import { Space_Grotesk, Space_Mono } from "next/font/google";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { AuthProvider } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ui/use-toast";
import { Toaster } from "@/components/ui/toaster";
import { EvidenceBanner } from "@/components/EvidenceBanner";
import { RouteTransition } from "@/components/RouteTransition";
import { PointerAura } from "@/components/PointerAura";
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
            <EvidenceBanner />
            <main className="flex-1 flex flex-col relative">
              <RouteTransition>{children}</RouteTransition>
            </main>
            <Footer />
            <PointerAura />
            <Toaster />
          </ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
