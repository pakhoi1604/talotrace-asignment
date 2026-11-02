import type { Metadata } from "next";
import { Suspense } from "react";

import { RoleCandidatesScreen } from "@/components/hr/role/role-candidates-screen";

export const metadata: Metadata = { title: "Candidates" };

export default function RoleCandidatesPage() {
  return (
    // useParams in the client root needs a Suspense boundary under cacheComponents.
    <Suspense>
      <RoleCandidatesScreen />
    </Suspense>
  );
}
