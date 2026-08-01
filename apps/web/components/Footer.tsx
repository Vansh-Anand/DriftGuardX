import Link from "next/link";
import { Activity } from "lucide-react";

export function Footer() {
  return (
    <footer className="w-full bg-[#111111] text-white pt-24 pb-12 border-t border-[#333]">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex flex-col lg:flex-row justify-between gap-16 mb-24">
          <div className="lg:w-1/3">
            <Link href="/" className="flex items-center gap-2 mb-8">
              <Activity className="h-6 w-6 text-white" />
              <span className="font-medium text-2xl tracking-tight">
                DriftGuard-X
              </span>
            </Link>
            <div className="text-sm font-medium mb-4 uppercase tracking-wider text-[#888]">Newsletter</div>
            <p className="text-2xl font-medium leading-snug mb-8">
              Subscribe to our mailing list to receive the latest updates.
            </p>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-3 gap-12 lg:w-2/3">
            <div className="flex flex-col gap-4">
              <h4 className="text-[#888] font-bold text-xs uppercase tracking-wider mb-2">Build on DriftGuard-X</h4>
              <Link href="/dashboard" className="text-sm hover:text-[#dcf6cc] transition-colors">Dev Docs ↗</Link>
              <a href="https://github.com/example/driftguardx" className="text-sm hover:text-[#dcf6cc] transition-colors">GitHub ↗</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Grants</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Bug Bounty ↗</a>
            </div>
            
            <div className="flex flex-col gap-4">
              <h4 className="text-[#888] font-bold text-xs uppercase tracking-wider mb-2">Ecosystem & Community</h4>
              <Link href="/experiments" className="text-sm hover:text-[#dcf6cc] transition-colors">Ecosystem Directory</Link>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Events</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Local Communities ↗</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Governance ↗</a>
            </div>
            
            <div className="flex flex-col gap-4">
              <h4 className="text-[#888] font-bold text-xs uppercase tracking-wider mb-2">About & Resources</h4>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Foundation</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Whitepaper</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Security</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Use Cases</a>
              <a href="#" className="text-sm hover:text-[#dcf6cc] transition-colors">Careers</a>
            </div>
          </div>
        </div>
        
        <div className="flex flex-col md:flex-row justify-between items-center pt-8 border-t border-[#333] text-xs text-[#888] font-medium tracking-wide">
          <div className="flex gap-6 mb-4 md:mb-0">
            <span>© 2026 DRIFTGUARD-X NETWORK</span>
            <a href="#" className="hover:text-white transition-colors">PRIVACY POLICY</a>
            <a href="#" className="hover:text-white transition-colors">TERMS OF SERVICE</a>
          </div>
          <div className="flex gap-6">
            <a href="#" className="hover:text-white transition-colors text-lg">𝕏</a>
            <a href="#" className="hover:text-white transition-colors text-lg">in</a>
            <a href="#" className="hover:text-white transition-colors text-lg">yt</a>
            <a href="#" className="hover:text-white transition-colors text-lg">gh</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
