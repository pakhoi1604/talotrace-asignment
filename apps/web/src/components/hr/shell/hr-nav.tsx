"use client";

// HR nav: Candidates · Needs a person (count pill) · Scoring jobs.
// "Needs a person" is the jobs page filtered — the nav count is the sum of
// job_counts.needs_person across roles. Hidden when zero.

import { cn } from "cn";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useHrResource } from "@/hooks/use-hr-resource";
import { listRoles } from "@/lib/hr-api";

const LINK_BASE = "rounded-sm px-3 py-2 text-body-sm";
const LINK_IDLE = "font-medium text-foreground-body";
const LINK_ACTIVE = "bg-primary-soft font-semibold text-primary-strong";

export function HrNav() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: roles } = useHrResource(listRoles, []);

  const needsPerson =
    roles?.roles.reduce((sum, r) => sum + r.job_counts.needs_person, 0) ?? 0;

  const isCandidates =
    pathname === "/hr" ||
    pathname.startsWith("/hr/roles") ||
    pathname.startsWith("/hr/candidates");
  const isNeedsPerson =
    pathname === "/hr/jobs" && searchParams.get("status") === "needs_person";
  const isJobs = pathname === "/hr/jobs" && !isNeedsPerson;

  return (
    <nav className="flex flex-wrap gap-1">
      <Link
        href="/hr"
        aria-current={isCandidates ? "page" : undefined}
        className={cn(LINK_BASE, isCandidates ? LINK_ACTIVE : LINK_IDLE)}
      >
        Candidates
      </Link>
      <Link
        href="/hr/jobs?status=needs_person"
        aria-current={isNeedsPerson ? "page" : undefined}
        className={cn(LINK_BASE, isNeedsPerson ? LINK_ACTIVE : LINK_IDLE)}
      >
        Needs a person
        {needsPerson > 0 && (
          <span className="ml-1 rounded-full bg-warning-subtle px-[7px] py-px font-semibold text-caption text-warning-ink">
            {needsPerson}
          </span>
        )}
      </Link>
      <Link
        href="/hr/jobs"
        aria-current={isJobs ? "page" : undefined}
        className={cn(LINK_BASE, isJobs ? LINK_ACTIVE : LINK_IDLE)}
      >
        Scoring jobs
      </Link>
    </nav>
  );
}
