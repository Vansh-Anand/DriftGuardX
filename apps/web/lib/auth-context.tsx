"use client";

import React, { createContext, useContext, useEffect, useState, ReactNode } from "react";

interface AuthenticatedUser {
  name: string;
  email: string;
  role: "admin";
  avatarUrl?: string;
}

interface AuthContextType {
  user: AuthenticatedUser | null;
  login: (email?: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const demoMode =
    process.env.NEXT_PUBLIC_DEMO_MODE === "true" ||
    (process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_DEMO_MODE !== "false");

  useEffect(() => {
    const email = window.localStorage.getItem("dgx_demo_email");
    const token = window.localStorage.getItem("dgx_access_token");
    if (demoMode && email && token === "mock-admin-token") {
      setUser({ name: email.split("@")[0] || "Demo User", email, role: "admin" });
    }
    setIsLoading(false);
  }, [demoMode]);

  const login = async (email = "demo@local.invalid") => {
    if (!demoMode) {
      throw new Error("Interactive OIDC login must be configured for non-demo deployments.");
    }
    window.localStorage.setItem("dgx_access_token", "mock-admin-token");
    window.localStorage.setItem("dgx_demo_email", email);
    setUser({ name: email.split("@")[0] || "Demo User", email, role: "admin" });
  };
  const logout = () => {
    window.localStorage.removeItem("dgx_access_token");
    window.localStorage.removeItem("dgx_demo_email");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
