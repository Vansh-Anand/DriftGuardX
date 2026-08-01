import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import { Navbar } from "@/components/Navbar";
import { Footer } from "@/components/Footer";
import { AuthProvider } from "@/lib/auth-context";
import { ToastProvider } from "@/components/ui/use-toast";
import { Toaster } from "@/components/ui/toaster";
import "./globals.css";

const outfit = Outfit({ subsets: ["latin"], variable: '--font-outfit' });

export const metadata: Metadata = {
  title: "DriftGuard-X",
  description: "Agentic RAG Reliability Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${outfit.variable} font-sans min-h-screen bg-background text-foreground antialiased flex flex-col selection:bg-primary selection:text-white`}>
        <AuthProvider>
          <ToastProvider>
            <Navbar />
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
