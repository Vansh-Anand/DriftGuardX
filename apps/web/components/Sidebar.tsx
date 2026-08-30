'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  Activity, List, Share2, Clock, GitMerge, FileText, 
  ShieldCheck, ShieldAlert, Key, TestTube, HeartPulse 
} from 'lucide-react'
import { cn } from '@/lib/utils'
import buildMetadata from '@/src/generated/build-metadata.json'

const navItems = [
  { name: 'Overview', href: '/', icon: Activity },
  { name: 'Runs', href: '/runs', icon: List },
  { name: 'Trace Detail', href: '/timeline', icon: Clock },
  { name: 'Causal Graph', href: '/graph', icon: Share2 },
  { name: 'Replay Lab', href: '/replay', icon: GitMerge },
  { name: 'BCRB Scheduler', href: '/scheduler', icon: TestTube },
  { name: 'Diagnosis', href: '/rationale', icon: FileText },
  { name: 'Policy', href: '/policy', icon: ShieldAlert },
  { name: 'Recovery', href: '/recovery', icon: ShieldCheck },
  { name: 'Ledger', href: '/ledger', icon: Key },
  { name: 'Security & Hardening', href: '/security', icon: ShieldAlert },
  { name: 'System Health', href: '/reports', icon: HeartPulse },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <div className="flex h-full w-64 flex-col bg-zinc-950 border-r border-zinc-800">
      <div className="flex h-14 items-center px-4 font-semibold text-blue-400 border-b border-zinc-800">
        DriftGuard-X
      </div>
      <div className="flex-1 overflow-y-auto py-4">
        <nav className="space-y-1 px-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href
            const Icon = item.icon
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  isActive ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:bg-zinc-800 hover:text-white',
                  'group flex items-center rounded-md px-2 py-2 text-sm font-medium transition-colors'
                )}
              >
                <Icon
                  className={cn(
                    isActive ? 'text-blue-400' : 'text-zinc-500 group-hover:text-blue-400',
                    'mr-3 h-5 w-5 flex-shrink-0 transition-colors'
                  )}
                  aria-hidden="true"
                />
                {item.name}
              </Link>
            )
          })}
        </nav>
      </div>
      <div className="p-4 border-t border-zinc-800 text-xs text-zinc-500">
        v{buildMetadata.version} <br/>
        <span 
          className="text-blue-500 font-semibold mt-1 inline-block cursor-pointer hover:text-blue-400 transition-colors"
          onClick={() => {
            const event = new CustomEvent('start-golden-demo');
            window.dispatchEvent(event);
          }}
        >
          Start Golden Demo
        </span>
      </div>
    </div>
  )
}
