import type { Metadata } from "next";
import { Suspense } from "react";

import { JobsScreen } from "@/components/hr/jobs/jobs-screen";

export const metadata: Metadata = { title: "Scoring jobs" };

export default function JobsPage() {
  return (
    // useSearchParams in the client root needs a Suspense boundary under cacheComponents.
    <Suspense>
      <JobsScreen />
    </Suspense>
  );
}
