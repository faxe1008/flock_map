import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.FLOCKMAP_API_BASE_URL ?? "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ speciesId: string }> },
) {
  const { speciesId } = await params;
  const targetUrl = `${API_BASE_URL}/species/${speciesId}/image`;

  try {
    const response = await fetch(targetUrl, { cache: "no-store" });

    if (!response.ok) {
      return new NextResponse("Image not found", { status: 404 });
    }

    const buffer = await response.arrayBuffer();
    const contentType = response.headers.get("Content-Type") ?? "image/jpeg";

    return new NextResponse(buffer, {
      status: 200,
      headers: {
        "Content-Type": contentType,
        "Cache-Control": "public, max-age=3600",
      },
    });
  } catch {
    return new NextResponse("Unable to load image", { status: 502 });
  }
}
