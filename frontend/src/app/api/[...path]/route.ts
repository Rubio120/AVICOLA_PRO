import { NextRequest, NextResponse } from "next/server";

import { getServerEnv } from "@/lib/env";

const allowedPrefixes = ["v1/auth/", "v1/company-profile", "v1/tax-rates", "v1/parties/", "v1/catalog/", "v1/inventory/", "v1/production/", "v1/purchasing/", "v1/sales/"];

function isAllowedPath(path: string) {
  return allowedPrefixes.some((prefix) => path.startsWith(prefix));
}

export async function handler(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const backendPath = path.join("/");
  if (!isAllowedPath(backendPath)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }

  const environment = getServerEnv();
  const headers = new Headers();
  for (const name of ["content-type", "cookie", "user-agent", "x-correlation-id", "x-csrf-token"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }

  const response = await fetch(`${environment.BACKEND_INTERNAL_URL}/api/${backendPath}`, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
    redirect: "manual",
  });
  const result = new NextResponse(response.body, { status: response.status });
  const contentType = response.headers.get("content-type");
  const csrfToken = response.headers.get("x-csrf-token");
  const setCookie = response.headers.get("set-cookie");
  if (contentType) result.headers.set("content-type", contentType);
  if (csrfToken) result.headers.set("x-csrf-token", csrfToken);
  if (setCookie) result.headers.set("set-cookie", setCookie);
  return result;
}

export const GET = handler;
export const POST = handler;
