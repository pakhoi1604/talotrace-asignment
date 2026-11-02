"use client";

// Title row: "Open roles · N" eyebrow, role title, role switcher, Refresh.
// The mockup's "Load data pack answers" button is dropped — no endpoint.

import { useRouter } from "next/navigation";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { RoleRef, RoleSummary } from "@/lib/api-types";

interface RoleHeaderProps {
  role: RoleRef;
  roles?: RoleSummary[];
  openRoles?: number;
  refresh: React.ReactNode;
}

export function RoleHeader({
  role,
  roles,
  openRoles,
  refresh,
}: RoleHeaderProps) {
  const router = useRouter();

  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex flex-col gap-1.5">
        <span className="font-medium text-meta text-muted-foreground">
          Open roles{openRoles !== undefined && ` · ${openRoles}`}
        </span>
        <h1 className="font-bold text-display-md">{role.title}</h1>
      </div>
      <div className="flex flex-wrap items-center gap-2.5">
        {roles && roles.length > 0 && (
          <Select
            value={String(role.id)}
            onValueChange={(id) => router.push(`/hr/roles/${id}`)}
          >
            <SelectTrigger
              aria-label="Role"
              className="h-11 rounded-md border-input bg-card px-3.5 text-body-sm text-foreground"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {roles.map((r) => (
                <SelectItem key={r.id} value={String(r.id)}>
                  {r.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        {refresh}
      </div>
    </div>
  );
}
