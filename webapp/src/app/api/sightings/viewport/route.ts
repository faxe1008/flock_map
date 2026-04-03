import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.FLOCKMAP_API_BASE_URL ?? "http://localhost:8000";

export async function GET(request: NextRequest) {
  const queryString = request.nextUrl.searchParams.toString();
  const targetUrl = `${API_BASE_URL}/sightings/viewport${queryString ? `?${queryString}` : ""}`;

  try {
    const response = await fetch(targetUrl, {
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    });

    const bodyText = await response.text();
    return new NextResponse(bodyText, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") ?? "application/json",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Unable to reach sightings viewport API." },
      { status: 502 },
    );
  }
}
