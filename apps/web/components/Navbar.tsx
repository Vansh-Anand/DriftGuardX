'use client';

import Link from "next/link";
import { Activity, ChevronDown, LogOut, User as UserIcon } from "lucide-react";
import { useAuth } from "@/lib/auth-context";
import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useToast } from "@/components/ui/use-toast";
import { Spinner } from "@/components/ui/spinner";

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
    toast({
      title: 'Logged out',
      description: 'You have been successfully logged out.',
    });
  };

  return (
    <>
      <div className="fixed top-8 left-0 w-full flex justify-center z-40 px-4 pointer-events-none">
        <nav className="bg-[#1a1a1a] text-white rounded-full px-6 h-[60px] flex items-center justify-between gap-8 shadow-2xl border border-[#333] pointer-events-auto">
          <Link href="/" className="flex items-center gap-2 pr-4 border-r border-[#333]">
            <Activity className="h-5 w-5 text-white" />
            <span className="font-medium text-lg tracking-tight">
              DriftGuard-X
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-6 text-sm font-medium">
            <Link href="/dashboard" className="flex items-center gap-1 hover:text-[#dcf6cc] transition-colors">
              ABOUT <ChevronDown className="w-4 h-4 opacity-70" />
            </Link>
            <Link href="/experiments" className="flex items-center gap-1 hover:text-[#dcf6cc] transition-colors">
              ECOSYSTEM <ChevronDown className="w-4 h-4 opacity-70" />
            </Link>
            <Link href="/dashboard" className="flex items-center gap-1 hover:text-[#dcf6cc] transition-colors">
              BUILD <ChevronDown className="w-4 h-4 opacity-70" />
            </Link>
          </div>

          <div className="ml-4 flex items-center">
            {isLoading ? (
              <div className="w-10 h-10 flex items-center justify-center">
                 <Spinner className="w-4 h-4" />
              </div>
            ) : user ? (
              <DropdownMenu>
                <DropdownMenuTrigger className="outline-none">
                  <Avatar className="w-9 h-9 border border-zinc-700 hover:border-zinc-500 transition-colors">
                    <AvatarImage src={user.avatarUrl} />
                    <AvatarFallback className="bg-zinc-800 text-xs">
                      {user.name.substring(0, 2).toUpperCase()}
                    </AvatarFallback>
                  </Avatar>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56 bg-[#1a1a1a] border-[#333] text-white">
                  <DropdownMenuLabel className="font-normal">
                    <div className="flex flex-col space-y-1">
                      <p className="text-sm font-medium leading-none">{user.name}</p>
                      <p className="text-xs leading-none text-zinc-400">{user.email}</p>
                    </div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator className="bg-[#333]" />
                  <DropdownMenuItem asChild className="focus:bg-[#333] focus:text-white cursor-pointer">
                    <Link href="/dashboard">
                      <UserIcon className="mr-2 h-4 w-4" />
                      <span>Dashboard</span>
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator className="bg-[#333]" />
                  <DropdownMenuItem onClick={handleLogout} className="focus:bg-[#333] focus:text-white cursor-pointer text-red-400">
                    <LogOut className="mr-2 h-4 w-4" />
                    <span>Log out</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <button 
                onClick={() => setLoginOpen(true)}
                className="px-6 py-2 rounded-full bg-white text-black font-bold text-sm hover:bg-[#dcf6cc] transition-colors uppercase tracking-wide"
              >
                Get Started
              </button>
            )}
          </div>
        </nav>
      </div>

      <Dialog open={loginOpen} onOpenChange={setLoginOpen}>
        <DialogContent className="sm:max-w-md bg-[#1a1a1a] border-[#333] text-white">
          <DialogHeader>
            <DialogTitle>Sign in to DriftGuard-X</DialogTitle>
            <DialogDescription className="text-zinc-400">
              Enter your email below to access the platform.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleLogin} className="flex flex-col gap-4 py-4">
            <div className="flex flex-col gap-2">
              <label htmlFor="email" className="text-sm font-medium text-zinc-300">
                Email address
              </label>
              <input
                id="email"
                type="email"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex h-10 w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-[#dcf6cc] disabled:cursor-not-allowed disabled:opacity-50"
                required
              />
            </div>
            <button
              type="submit"
              disabled={isLoggingIn}
              className="mt-2 flex h-10 w-full items-center justify-center rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-[#dcf6cc] focus:outline-none disabled:opacity-50"
            >
              {isLoggingIn ? <Spinner className="w-4 h-4 mr-2" /> : null}
              Sign In
            </button>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
