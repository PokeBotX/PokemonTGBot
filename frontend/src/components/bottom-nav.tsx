"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Heart, House, Store } from "lucide-react";
import { cn } from "@/lib/utils";

type NavVariant = "default" | "minimal";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const navItems: NavItem[] = [
  { href: "/", label: "Главная", icon: House },
  { href: "/favorites", label: "Залоченные", icon: Heart },
  { href: "/shop", label: "Магазин", icon: Store },
];

type BottomNavProps = {
  variant?: NavVariant;
};

export function BottomNav({ variant = "default" }: BottomNavProps) {
  const pathname = usePathname();
  const isMinimal = variant === "minimal";

  return (
    <nav
      className={cn(
        "fixed bottom-0 left-0 right-0 z-30",
        isMinimal
          ? "border-t border-slate-700 bg-slate-900"
          : "border-t border-slate-800 bg-slate-950/95 backdrop-blur"
      )}
    >
      <div
        className={cn(
          "mx-auto flex max-w-md items-center justify-around px-4",
          isMinimal ? "py-4" : "py-3"
        )}
      >
        {navItems.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              aria-label={item.label}
              className={cn(
                "flex min-w-16 items-center justify-center rounded-xl transition",
                isMinimal
                  ? "px-3 py-1.5"
                  : "flex-col gap-1 px-3 py-2 text-xs",
                isMinimal
                  ? isActive
                    ? "text-slate-100"
                    : "text-slate-500 hover:text-slate-300"
                  : isActive
                    ? "bg-yellow-400 text-slate-950"
                    : "text-slate-400 hover:text-white"
              )}
            >
              <Icon className={cn(isMinimal ? "h-6 w-6" : "h-5 w-5")} />
              {!isMinimal && <span>{item.label}</span>}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
