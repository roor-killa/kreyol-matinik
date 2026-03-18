/**
 * Proxy admin → FastAPI (conservé pour compatibilité SSR).
 * Transfère la requête à FastAPI en relayant le token JWT Bearer.
 * Les appels client-side passent désormais directement par FastAPI.
 */
import { NextRequest, NextResponse } from "next/server";

const FASTAPI =
  process.env.FASTAPI_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_FASTAPI_URL ??
  "http://localhost:8000/api/v1";

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const authHeader = req.headers.get("Authorization");
  if (!authHeader) {
    return NextResponse.json({ message: "Authentification requise" }, { status: 401 });
  }

  const { path } = await params;
  const url      = new URL(req.url);
  const target   = `${FASTAPI}/admin/${path.join("/")}${url.search}`;

  const body =
    req.method !== "GET" && req.method !== "DELETE"
      ? await req.text()
      : undefined;

  const res = await fetch(target, {
    method:  req.method,
    headers: {
      "Content-Type":  "application/json",
      "Authorization": authHeader,
    },
    body:  body ?? undefined,
    cache: "no-store",
  });

  if (res.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}

export const GET    = handler;
export const PUT    = handler;
export const DELETE = handler;
export const POST   = handler;
