// Next 16 proxy (the former `middleware` convention). Redirects /hr/* to
// sign-in when the `hr_session` cookie is absent — presence check only; the
// API still validates the session and clients handle 401 the same way.

import { type NextRequest, NextResponse } from "next/server";

export function proxy(req: NextRequest) {
  if (req.cookies.has("hr_session")) return NextResponse.next();
  const url = new URL("/hr/sign-in", req.url);
  url.searchParams.set("next", req.nextUrl.pathname + req.nextUrl.search);
  return NextResponse.redirect(url);
}

export const config = { matcher: ["/hr", "/hr/((?!sign-in).*)"] };
