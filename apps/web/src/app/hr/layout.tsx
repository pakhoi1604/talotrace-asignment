import type { Metadata } from "next";

// All HR routes are internal: no indexing, and titles read "… · HR".
export const metadata: Metadata = {
  title: { template: "%s · HR", default: "HR" },
  robots: { index: false, follow: false },
};

export default function HrLayout({ children }: LayoutProps<"/hr">) {
  return children;
}
