import createMiddleware from "next-intl/middleware";
import { routing }       from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  matcher: [
    // Match the root
    "/",
    // Match locale-prefixed paths
    "/(fr|en|crm)/:path*",
    // Match everything except _next, _vercel, api routes, and static files
    "/((?!_next|_vercel|api|.*\\..*).*)",
  ],
};
