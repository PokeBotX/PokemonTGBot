"use client";

import { Badge } from "@/components/ui/badge";

type PokemonFormBadgeProps = {
  formBadge?: string | null;
  className?: string;
};

function getFormBadgeClassName(formBadge?: string | null): string {
  const normalized = formBadge?.trim().toLowerCase();
  switch (normalized) {
    case "shiny":
      return "border-amber-400/50 bg-amber-400/15 text-amber-200";
    case "mega":
      return "border-rose-400/50 bg-rose-400/15 text-rose-200";
    case "gigantamax":
      return "border-cyan-400/50 bg-cyan-400/15 text-cyan-200";
    default:
      return "border-slate-500/50 bg-slate-700/70 text-slate-200";
  }
}

export function PokemonFormBadge({ formBadge, className }: PokemonFormBadgeProps) {
  if (!formBadge) {
    return null;
  }

  return (
    <Badge
      variant="outline"
      className={`${getFormBadgeClassName(formBadge)} ${className ?? ""}`.trim()}
    >
      {formBadge}
    </Badge>
  );
}
