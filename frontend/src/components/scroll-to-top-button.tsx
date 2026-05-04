"use client";

import { useEffect, useState } from "react";
import { ChevronUp } from "lucide-react";

import { cn } from "@/lib/utils";

type ScrollToTopButtonProps = {
  className?: string;
};

export function ScrollToTopButton({ className }: ScrollToTopButtonProps) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsVisible(window.scrollY > 240);
    };

    handleScroll();
    window.addEventListener("scroll", handleScroll, { passive: true });

    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  if (!isVisible) {
    return null;
  }

  return (
    <button
      type="button"
      aria-label="Наверх"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
      className={cn(
        "fixed right-4 bottom-24 z-40 rounded-full border border-slate-700 bg-slate-900/95 p-3 text-slate-100 shadow-[0_8px_24px_rgba(0,0,0,0.35)] transition hover:border-slate-500 hover:bg-slate-800",
        className,
      )}
    >
      <ChevronUp className="h-5 w-5" />
    </button>
  );
}
