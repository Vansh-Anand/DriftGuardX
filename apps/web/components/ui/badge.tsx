import * as React from "react"
import { cn } from "@/lib/utils"

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "secondary" | "destructive" | "outline" | "measured" | "inferred" | "synthetic" | "certified" | "uncertified" | "unavailable";
}

function Badge({ className, variant = "default", ...props }: BadgeProps) {
  const variants: Record<string, string> = {
    default: "border-transparent bg-blue-600 text-white hover:bg-blue-700",
    secondary: "border-transparent bg-zinc-800 text-zinc-100 hover:bg-zinc-700",
    destructive: "border-transparent bg-red-900 text-red-100 hover:bg-red-800",
    outline: "text-zinc-300 border-zinc-700",
    
    // Truthful UI States
    measured: "border-green-500/50 bg-green-500/10 text-green-400",
    inferred: "border-yellow-500/50 bg-yellow-500/10 text-yellow-400",
    synthetic: "border-purple-500/50 bg-purple-500/10 text-purple-400",
    certified: "border-blue-500/50 bg-blue-500/10 text-blue-400",
    uncertified: "border-orange-500/50 bg-orange-500/10 text-orange-400 border-dashed",
    unavailable: "border-zinc-500/50 bg-zinc-500/10 text-zinc-400 opacity-70"
  };

  return (
    <div
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2",
        variants[variant] || variants.default,
        className
      )}
      {...props}
    />
  )
}

export { Badge }
