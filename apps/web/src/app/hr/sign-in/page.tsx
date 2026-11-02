import type { Metadata } from "next";
import { Suspense } from "react";

import { SignInScreen } from "@/components/hr/sign-in/sign-in-screen";

export const metadata: Metadata = { title: "Sign in" };

export default function SignInPage() {
  return (
    // useSearchParams (the `next` target) needs a Suspense boundary under cacheComponents.
    <Suspense>
      <SignInScreen />
    </Suspense>
  );
}
