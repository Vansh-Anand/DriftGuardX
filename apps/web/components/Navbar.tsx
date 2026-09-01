'use client';

import Link from "next/link";
import { LogOut, User as UserIcon } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useToast } from "@/components/ui/use-toast";
import { Spinner } from "@/components/ui/spinner";
import { usePathname } from "next/navigation";

export function Navbar() {
  const pathname = usePathname();
  const { user, login, logout, isLoading } = useAuth();
  const { toast } = useToast();
  const [loginOpen, setLoginOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setIsLoggingIn(true);
    try {
      await login(email);
      setLoginOpen(false);
      toast({
        title: 'Logged in successfully',
        description: `Welcome back, ${email.split('@')[0]}!`,
        variant: 'success'
      });
    } catch (error) {
      toast({
        title: 'Login unavailable',
        description: error instanceof Error ? error.message : 'Authentication failed.',
        variant: 'destructive'
      });
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    logout();
    toast({ title: 'Logged out', description: 'You have been successfully logged out.' });
  };

  return (
    <>
      <header className="fixed top-0 left-0 w-full z-50 bg-background text-foreground border-b border-foreground/20">
        <div className="flex items-center justify-between h-14 w-full">
          {/* Left: Logo (Cube icon mimicking industrial design) */}
          <Link href="/" className="flex items-center gap-3 px-6 h-full border-r border-foreground/20 group">
            <svg viewBox="0 0 24 24" className="w-6 h-6 fill-none stroke-foreground stroke-[1.5]" strokeLinecap="round" strokeLinejoin="round">
               <polygon points="12 2 2 7 12 12 22 7 12 2" />
               <polyline points="2 17 12 22 22 17" />
               <polyline points="2 12 12 17 22 12" />
            </svg>
            <span className="font-bold tracking-tighter text-xl uppercase">DRIFTGUARDX</span>
          </Link>

          {/* Center: Nav links */}
          <nav className="hidden md:flex items-center h-full flex-1">
            <Link href="/dashboard" className="mono px-6 h-full flex items-center border-r border-foreground/20 hover:bg-foreground/5 transition-colors">
              CONSOLE
            </Link>
            <Link href="/reports" className="mono px-6 h-full flex items-center border-r border-foreground/20 hover:bg-foreground/5 transition-colors">
              REPORTS
            </Link>
            <Link href="/security" className="mono px-6 h-full flex items-center border-r border-foreground/20 hover:bg-foreground/5 transition-colors">
              SECURITY
            </Link>
            <Link href="/experiments" className="mono px-6 h-full flex items-center border-r border-foreground/20 hover:bg-foreground/5 transition-colors">
              EXPERIMENTS
            </Link>
          </nav>

          {/* Right: Auth / Contact */}
          <div className="flex items-center h-full">
            {isLoading ? (
              <div className="px-6 h-full flex items-center">
                <Spinner className="w-3 h-3" />
              </div>
            ) : user ? (
              <DropdownMenu>
                <DropdownMenuTrigger className="outline-none h-full px-6 flex items-center border-l border-foreground/20 hover:bg-foreground/5">
                  <Avatar className="w-8 h-8 rounded-none border border-foreground">
                    <AvatarImage src={user.avatarUrl} />
                    <AvatarFallback className="bg-foreground text-background text-xs font-mono rounded-none">
                      {user.name.substring(0, 2).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48 bg-background border-foreground text-foreground font-mono text-xs rounded-none">
                  <DropdownMenuLabel className="font-mono text-xs">{user.email}</DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-foreground/20" />
                  <DropdownMenuItem asChild className="focus:bg-foreground/10 rounded-none cursor-pointer">
                    <Link href="/dashboard"><UserIcon className="mr-2 h-3 w-3" /> DASHBOARD</Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-foreground/20" />
                  <DropdownMenuItem onClick={handleLogout} className="focus:bg-foreground/10 rounded-none cursor-pointer text-accent">
                    <LogOut className="mr-2 h-3 w-3" /> LOG OUT
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <button
                onClick={() => setLoginOpen(true)}
                className="h-full px-6 flex items-center border-l border-foreground/20 mono text-accent font-bold hover:bg-accent hover:text-background transition-colors"
              >
                SIGN IN →
              </button>
            )}
          </div>
        </div>
      </header>

      <Dialog open={loginOpen} onOpenChange={setLoginOpen}>
        <DialogContent className="sm:max-w-md bg-background border border-foreground text-foreground font-mono rounded-none">
          <DialogHeader>
            <DialogTitle className="font-mono text-sm tracking-widest uppercase">SIGN IN TO DRIFTGUARDX</DialogTitle>
            <DialogDescription className="font-mono text-xs text-muted">
              ENTER YOUR EMAIL TO ACCESS THE PLATFORM.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleLogin} className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <label htmlFor="email" className="font-mono text-xs uppercase tracking-widest">EMAIL ADDRESS</label>
              <input
                id="email"
                type="email"
                placeholder="NAME@EXAMPLE.COM"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-10 w-full border border-foreground bg-transparent px-3 py-2 text-sm font-mono text-foreground placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-foreground rounded-none"
                required
              />
            </div>
            <button
              type="submit"
              disabled={isLoggingIn}
              className="flex h-10 w-full items-center justify-center border border-foreground bg-foreground text-background font-mono text-xs tracking-widest uppercase hover:bg-foreground/90 transition-colors disabled:opacity-50 rounded-none"
            >
              {isLoggingIn ? <Spinner className="w-4 h-4 mr-2 text-background" /> : null}
              ACCESS PLATFORM
            </button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
