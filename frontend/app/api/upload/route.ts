import { handleUpload, type HandleUploadBody } from "@vercel/blob/client";
import { jwtVerify } from "jose";
import { NextResponse } from "next/server";

const encoder = new TextEncoder();

function bearerToken(request: Request): string | null {
  const auth = request.headers.get("authorization");
  if (!auth?.startsWith("Bearer ")) return null;
  return auth.slice("Bearer ".length);
}

export async function POST(request: Request): Promise<NextResponse> {
  let body: HandleUploadBody;
  try {
    body = (await request.json()) as HandleUploadBody;
  } catch {
    return NextResponse.json({ error: "Invalid request body" }, { status: 400 });
  }

  const isTokenRequest =
    typeof body?.type === "string" && body.type.includes("generate-client-token");

  if (isTokenRequest) {
    const token = bearerToken(request);
    const secret = process.env.SECRET_KEY;
    if (!token || !secret) {
      return NextResponse.json(
        { error: "Not authenticated" },
        { status: 401 },
      );
    }
    try {
      await jwtVerify(token, encoder.encode(secret), { algorithms: ["HS256"] });
    } catch {
      return NextResponse.json(
        { error: "Not authenticated" },
        { status: 401 },
      );
    }
  }

  try {
    const jsonResponse = await handleUpload({
      body,
      request,
      onBeforeGenerateToken: async () => ({
        allowedContentTypes: ["application/pdf", "application/zip"],
        addRandomSuffix: true,
      }),
      onUploadCompleted: async () => {},
    });
    return NextResponse.json(jsonResponse);
  } catch (error) {
    return NextResponse.json(
      { error: (error as Error).message },
      { status: 400 },
    );
  }
}
