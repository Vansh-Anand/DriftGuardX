'use client';

import { useToast } from './use-toast';
import { X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-full max-w-sm">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            initial={{ opacity: 0, y: 50, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
            className={cn(
              "relative flex flex-col p-4 pr-8 rounded-lg border shadow-lg overflow-hidden",
              toast.variant === 'destructive' ? 'bg-red-950 border-red-900 text-red-50' : 
              toast.variant === 'success' ? 'bg-emerald-950 border-emerald-900 text-emerald-50' :
              'bg-zinc-900 border-zinc-800 text-zinc-50'
            )}
          >
            <div className="font-semibold text-sm mb-1">{toast.title}</div>
            {toast.description && (
              <div className="text-sm opacity-90">{toast.description}</div>
            )}
            <button
              onClick={() => dismiss(toast.id)}
              className="absolute right-2 top-2 p-1 rounded-md opacity-70 hover:opacity-100 transition-opacity"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
