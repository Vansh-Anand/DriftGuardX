"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

export function AnimatedSection({ 
  children, 
  className = "", 
  delay = 0 
}: { 
  children: ReactNode, 
  className?: string, 
  delay?: number 
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.8, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
