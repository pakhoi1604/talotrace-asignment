import { HrShell } from "@/components/hr/shell/hr-shell";

export default function HrAppLayout({ children }: LayoutProps<"/hr">) {
  return <HrShell>{children}</HrShell>;
}
