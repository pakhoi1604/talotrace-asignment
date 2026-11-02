// Shared logo tile — extracted from interview-header so the candidate area and
// the HR area render the same mark. `sm/primary` is the header tile;
// `lg/inverse` is the white tile on the sign-in brand panel.

import { cn } from "cn";
import { Check } from "lucide-react";

interface BrandMarkProps {
  size?: "sm" | "lg";
  tone?: "primary" | "inverse";
  className?: string;
}

export function BrandMark({
  size = "sm",
  tone = "primary",
  className,
}: BrandMarkProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-center",
        size === "sm" ? "size-8 rounded-sm" : "size-10 rounded-md",
        tone === "primary" ? "bg-primary" : "bg-card",
        className,
      )}
    >
      <Check
        className={cn(
          size === "sm" ? "size-4.5" : "size-5.5",
          tone === "primary"
            ? "text-primary-foreground"
            : "text-primary-strong",
        )}
        strokeWidth={2.4}
        aria-hidden
      />
    </div>
  );
}
