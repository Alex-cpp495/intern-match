import { NextResponse } from "next/server";

export const maxDuration = 30;

export async function GET() {
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const response = await fetch(`${backendUrl}/api/chat/greeting`);
  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
