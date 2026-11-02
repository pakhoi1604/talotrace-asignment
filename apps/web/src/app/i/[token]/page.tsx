import type { Metadata } from "next";
import { Suspense } from "react";

import { InterviewMessageCard } from "@/components/interview/interview-message-card";
import { InterviewScreen } from "@/components/interview/interview-screen";

export const metadata: Metadata = {
  title: "Your interview",
  robots: { index: false, follow: false },
};

export default function InterviewPage() {
  return (
    // useParams in a client component needs a Suspense boundary under cacheComponents.
    <Suspense
      fallback={
        <div className="flex flex-1 flex-col bg-background">
          <main className="mx-auto flex w-full max-w-interview flex-1 items-center px-6 py-16">
            <InterviewMessageCard title="Loading your interview…">
              <p>One moment.</p>
            </InterviewMessageCard>
          </main>
        </div>
      }
    >
      <InterviewScreen />
    </Suspense>
  );
}
