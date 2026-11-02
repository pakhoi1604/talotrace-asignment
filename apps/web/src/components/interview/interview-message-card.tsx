import type { ReactNode } from "react";

interface InterviewMessageCardProps {
  title: string;
  children: ReactNode;
}

/** Shared card for terminal states: invalid link, load error, completed. */
export function InterviewMessageCard({
  title,
  children,
}: InterviewMessageCardProps) {
  return (
    <section className="flex w-full flex-col gap-4 rounded-3xl border bg-card p-6 shadow-card sm:p-8">
      <h1 className="font-bold text-heading">{title}</h1>
      <div className="flex flex-col gap-4 text-body text-foreground-body">
        {children}
      </div>
    </section>
  );
}
