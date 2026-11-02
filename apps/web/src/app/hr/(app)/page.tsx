import { Suspense } from "react";

import { HrIndexRedirect } from "@/components/hr/shell/hr-index-redirect";

export default function HrIndexPage() {
  return (
    <Suspense>
      <HrIndexRedirect />
    </Suspense>
  );
}
