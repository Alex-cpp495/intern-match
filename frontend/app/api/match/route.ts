import { NextRequest, NextResponse } from "next/server";

// 允许最多 120 秒（匹配算法 + DeepSeek 解释生成）
export const maxDuration = 120;

export async function POST(req: NextRequest) {
  const body = await req.json();
  const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const response = await fetch(`${backendUrl}/api/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    // Node.js fetch 不设超时，由 maxDuration 控制
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}
