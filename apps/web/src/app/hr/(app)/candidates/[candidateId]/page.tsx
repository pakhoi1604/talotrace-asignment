import type { Metadata } from "next";
import { Suspense } from "react";

import { CandidateReviewScreen } from "@/components/hr/review/candidate-review-screen";

export const metadata: Metadata = { title: "Review" };

export default function CandidateReviewPage() {
  return (
    // useParams in the client root needs a Suspense boundary under cacheComponents.
    <Suspense>
      <CandidateReviewScreen />
    </Suspense>
  );
}
