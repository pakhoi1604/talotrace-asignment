import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";

interface InterviewHeaderProps {
  role: string;
  firstName: string;
  savedCount: number;
}

export function InterviewHeader({
  role,
  firstName,
  savedCount,
}: InterviewHeaderProps) {
  return (
    <header className="border-b bg-card">
      <div className="mx-auto flex max-w-interview flex-wrap items-center justify-between gap-3 px-6 py-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-sm bg-primary">
            <Check
              className="size-4.5 text-primary-foreground"
              strokeWidth={2.4}
              aria-hidden
            />
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-body">{role} interview</span>
            <span className="text-meta text-muted-foreground">
              Hi {firstName} — your progress saves automatically
            </span>
          </div>
        </div>
        {savedCount > 0 && (
          <Badge variant="success">
            <Check aria-hidden />
            {savedCount} {savedCount === 1 ? "answer" : "answers"} saved
          </Badge>
        )}
      </div>
    </header>
  );
}
