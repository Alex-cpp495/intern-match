import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** 与后端 `core/security.py` 中 AUTH_COOKIE_NAME 一致 */
const AUTH_COOKIE = "auth_token";

export function middleware(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  const hasAuth = request.cookies.has(AUTH_COOKIE);

  if (pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  if (!hasAuth) {
    const login = request.nextUrl.clone();
    login.pathname = "/login";

    if (
      pathname === "/results" ||
      pathname.startsWith("/campus") ||
      pathname === "/saved" ||
      pathname === "/me"
    ) {
      const callback = pathname + (request.nextUrl.search || "");
      login.searchParams.set("callbackUrl", callback);
      return NextResponse.redirect(login);
    }

    if (pathname === "/" && searchParams.get("match") === "1") {
      login.searchParams.set("callbackUrl", "/?match=1");
      return NextResponse.redirect(login);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
