import { NextRequest, NextResponse } from "next/server";
import { getCachedAutocomplete, setCachedAutocomplete } from "@/lib/redis";

const LOCAL_PLACE_SUGGESTIONS = [
    "Ranchi, Jharkhand, India",
    "Puri, Odisha, India",
    "Bhubaneswar, Odisha, India",
    "Cuttack, Odisha, India",
    "Kolkata, West Bengal, India",
    "Jamshedpur, Jharkhand, India",
    "Patna, Bihar, India",
    "Varanasi, Uttar Pradesh, India",
    "New Delhi, Delhi, India",
    "Mumbai, Maharashtra, India",
    "Bengaluru, Karnataka, India",
    "Hyderabad, Telangana, India",
];

function getLocalPredictions(input: string) {
    const normalizedInput = input.trim().toLowerCase();
    return LOCAL_PLACE_SUGGESTIONS
        .filter((place) => place.toLowerCase().includes(normalizedInput))
        .slice(0, 6)
        .map((description, index) => ({
            description,
            place_id: `local-${description.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-${index}`,
        }));
}

/**
 * POST /api/places/autocomplete
 * Server-side proxy to Google Places Autocomplete.
 * Keeps the API key hidden from the client.
 *
 * Body: { input: string }
 * Returns: { predictions: { description: string; place_id: string }[] }
 */
export async function POST(req: NextRequest) {
    //const apiKey = process.env.GOOGLE_MAPS_API_KEY ?? process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY;
    const apiKey = "AIzaSyCIuM-ixp6EiCXxhmK19BLAJeqPQgGakO8"

    let body: { input?: string };
    try {
        body = await req.json();
    } catch (e) {
        return NextResponse.json({ error: `Invalid JSON body: ${e}` }, { status: 400 });
    }

    const { input } = body;
    if (!input || input.trim().length < 2) {
        return NextResponse.json({ predictions: [] });
    }

    const cachedResponse = await getCachedAutocomplete(input);
    if (cachedResponse) {
        return NextResponse.json(cachedResponse);
    }

    if (!apiKey) {
        const predictions = getLocalPredictions(input);
        await setCachedAutocomplete(input, { predictions });
        return NextResponse.json({ predictions, source: "local" });
    }

    const url = new URL(
        "https://maps.googleapis.com/maps/api/place/autocomplete/json",
    );
    url.searchParams.set("input", input);
    url.searchParams.set("key", apiKey);

    try {
        const res = await fetch(url.toString());
        const data = await res.json();

        // Surface any Google API error to the client for debugging
        if (data.status !== "OK" && data.status !== "ZERO_RESULTS") {
            console.error("[Places Autocomplete] Google API error:", JSON.stringify(data));
            const predictions = getLocalPredictions(input);
            return NextResponse.json({
                predictions,
                source: "local",
                warning: `Google Places unavailable: ${data.status}`,
            });
        }

        const predictions = (data.predictions ?? []).map(
            (p: { description: string; place_id: string }) => ({
                description: p.description,
                place_id: p.place_id,
            }),
        );

        await setCachedAutocomplete(input, { predictions });

        return NextResponse.json({ predictions });
    } catch (e) {
        console.error("[Places Autocomplete] Fetch failed:", e);
        const predictions = getLocalPredictions(input);
        return NextResponse.json({
            predictions,
            source: "local",
            warning: `Google Places fetch failed: ${e}`,
        });
    }
}
