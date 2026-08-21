'use client';

import Link from "next/link";
import { LogOut, User as UserIcon } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useToast } from "@/components/ui/use-toast";
import { Spinner } from "@/components/ui/spinner";

function LiveClock({ label, offset }: { label: string; offset: number }) {
  const [time, setTime] = useState('');
  useEffect(() => {
    const update = () => {
      const d = new Date();
      const utc = d.getTime() + d.getTimezoneOffset() * 60000;
      const local = new Date(utc + 3600000 * offset);
      setTime(local.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }));
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [offset]);

  return (
    <span className="font-mono text-xs tracking-widest text-[#0a0a0a]">
      {label} {time}
    </span>
  );
}

export function Navbar() {
  const { user, login, logout, isLoading } = useAuth();
  const { toast } = useToast();
  const [loginOpen, setLoginOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setIsLoggingIn(true);
    await login(email);
    setIsLoggingIn(false);
    setLoginOpen(false);
    toast({
      title: 'Logged in successfully',
      description: `Welcome back, ${email.split('@')[0]}!`,
      variant: 'success'
    });
  };

  const handleLogout = () => {
    logout();
    toast({ title: 'Logged out', description: 'You have been successfully logged out.' });
  };

  return (
    <>
      {/* 2xA Style flat top bar */}
      <header className="fixed top-0 left-0 w-full z-50 bg-[#ECEAE2] border-b border-[#0a0a0a]">
        <div className="flex items-center justify-between h-12 px-6">
          {/* Left: Logo */}
          <Link href="/" className="font-mono text-xs font-bold tracking-[0.15em] uppercase text-[#0a0a0a]">
            DriftGuard-X
          </Link>

          {/* Center: Live clocks like 2xA */}
          <div className="hidden md:flex items-center gap-12">
            <LiveClock label="NYC(US)" offset={-4} />
            <LiveClock label="LON(UK)" offset={1} />
            <LiveClock label="IST(IN)" offset={5.5} />
          </div>

          {/* Right: Nav links */}
          <nav className="flex items-center gap-8">
            <Link href="/dashboard" className="font-mono text-xs tracking-widest uppercase hover:opacity-60 transition-opacity link-underline">
              Console
            </Link>
            <Link href="/reports" className="font-mono text-xs tracking-widest uppercase hover:opacity-60 transition-opacity link-underline">
              Reports
            </Link>
            <Link href="/security" className="font-mono text-xs tracking-widest uppercase hover:opacity-60 transition-opacity link-underline">
              Security
            </Link>
            <Link href="/experiments" className="font-mono text-xs tracking-widest uppercase hover:opacity-60 transition-opacity link-underline">
              Experiments
            </Link>

            {isLoading ? (
              <Spinner className="w-3 h-3" />
            ) : user ? (
              <DropdownMenu>
                <DropdownMenuTrigger className="outline-none">
                  <Avatar className="w-7 h-7 border border-[#0a0a0a]">
                    <AvatarImage src={user.avatarUrl} />
                    <AvatarFallback className="bg-[#0a0a0a] text-[#ECEAE2] text-[10px] font-mono">
                      {user.name.substring(0, 2).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48 bg-[#0a0a0a] border-[#333] text-[#ECEAE2] font-mono text-xs">
                  <DropdownMenuLabel className="font-mono text-xs">{user.email}</DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-[#333]" />
                  <DropdownMenuItem asChild className="focus:bg-[#222] cursor-pointer">
                    <Link href="/dashboard"><UserIcon className="mr-2 h-3 w-3" /> Dashboard</Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-[#333]" />
                  <DropdownMenuItem onClick={handleLogout} className="focus:bg-[#222] cursor-pointer text-red-400">
                    <LogOut className="mr-2 h-3 w-3" /> Log out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <button
                onClick={() => setLoginOpen(true)}
                className="font-mono text-xs tracking-widest uppercase border border-[#0a0a0a] px-4 py-1.5 hover:bg-[#0a0a0a] hover:text-[#ECEAE2] transition-colors"
              >
                Sign In
              </button>
            )}
          </nav>
        </div>
      </header>

      <Dialog open={loginOpen} onOpenChange={setLoginOpen}>
        <DialogContent className="sm:max-w-md bg-[#ECEAE2] border border-[#0a0a0a] text-[#0a0a0a] font-mono">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm tracking-widest uppercase">Sign in to DriftGuard-X</DialogTitle>
            <DialogDescription className="font-mono text-xs text-[#888]">
              Enter your email to access the platform.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleLogin} className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <label htmlFor="email" className="font-mono text-xs uppercase tracking-widest">Email address</label>
              <input
                id="email"
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-10 w-full border border-[#0a0a0a] bg-transparent px-3 py-2 text-sm font-mono text-[#0a0a0a] placeholder:text-[#888] focus:outline-none focus:ring-1 focus:ring-[#0a0a0a]"
                required
              />
            </div>
            <button
              type="submit"
              disabled={isLoggingIn}
              className="flex h-10 w-full items-center justify-center border border-[#0a0a0a] bg-[#0a0a0a] text-[#ECEAE2] font-mono text-xs tracking-widest uppercase hover:bg-[#333] transition-colors disabled:opacity-50"
            >
              {isLoggingIn ? <Spinner className="w-4 h-4 mr-2" /> : null}
              Access Platform
            </button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
