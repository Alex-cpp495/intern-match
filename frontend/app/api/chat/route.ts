import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 30;

export async function POST(req: NextRequest) {
  const body = await req.json();
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const response = await fetch(`${backendUrl}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
