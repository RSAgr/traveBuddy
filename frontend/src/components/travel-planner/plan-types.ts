/* ── Schema types matching output-schema.txt ── */

export interface TransportDetails {
    name: string;
    booking_link: string;
    /** Should be in INR */
    price: string;
    /** ISO 8601 */
    departure_from_source: string;
    /** ISO 8601 */
    arrival_at_destination: string;
    description: string;
}

export interface HotelDetails {
    name: string;
    booking_link: string;
    /** Should be in INR */
    price: string;
    /** Photos from get_hotel_details tool */
    image_urls: string[];
    rating: number;
    /** Markdown string */
    description: string;
}

export interface Activity {
    /** Location name etc. (Don't mention Day number.) */
    title: string;
    google_map_url?: string | null;
    /** Markdown string explaining the plan for the day */
    plan: string;
}

export interface Transports {
    cabs?: TransportDetails[] | null;
    trains?: TransportDetails[] | null;
}

export interface PlanOutputSchema {
    outbound: Transports;
    inbound: Transports;
    hotels?: HotelDetails[] | null;
    itinerary?: Activity[] | null;
    message: string;
}

/* ── Trip input from the wizard form ── */

export interface TripInput {
    startingPoint: string;
    destination: string;
    startDate: string;
    endDate: string;
    adults: number;
    children: number;
    budget: string;
    bookingTiming: "balanced" | "early" | "postpone";
    preferences: string;
}

/* ── Accumulated plan state (sections start empty) ── */

export interface PlanState {
    outbound: Transports;
    inbound: Transports;
    hotels: HotelDetails[];
    itinerary: Activity[];
}

export function emptyPlanState(): PlanState {
    return {
        outbound: { cabs: [], trains: [] },
        inbound: { cabs: [], trains: [] },
        hotels: [],
        itinerary: [],
    };
}

/* ── Chat message ── */

export interface ChatMessage {
    role: "user" | "assistant";
    text: string;
}

/* ── Merge logic ──
 * For each field in the incoming response:
 *   - null / undefined → keep the old value
 *   - non-null → replace with the new value
 * The `message` field is NOT handled here — it's appended as a ChatMessage separately.
 */
export function mergePlan(
    current: PlanState,
    incoming: Partial<PlanOutputSchema>
): PlanState {
    const merged = { ...current };

    // Outbound
    if (incoming.outbound != null) {
        merged.outbound = {
            cabs:
                incoming.outbound.cabs != null
                    ? incoming.outbound.cabs
                    : current.outbound.cabs,
            trains:
                incoming.outbound.trains != null
                    ? incoming.outbound.trains
                    : current.outbound.trains,
        };
    }

    // Inbound
    if (incoming.inbound != null) {
        merged.inbound = {
            cabs:
                incoming.inbound.cabs != null
                    ? incoming.inbound.cabs
                    : current.inbound.cabs,
            trains:
                incoming.inbound.trains != null
                    ? incoming.inbound.trains
                    : current.inbound.trains,
        };
    }

    // Hotels
    if (incoming.hotels != null) {
        merged.hotels = incoming.hotels;
    }

    // Itinerary
    if (incoming.itinerary != null) {
        merged.itinerary = incoming.itinerary;
    }

    return merged;
}

/**
 * Build the initial prompt text from TripInput.
 */
export function tripInputToPrompt(input: TripInput): string {
    const parts = [
        `Plan a trip from ${input.startingPoint} to ${input.destination}.`,
        `Dates: ${input.startDate} to ${input.endDate}.`,
        `Travellers: ${input.adults} adult, ${input.children} child.`,
        `Budget: ₹${Number(input.budget).toLocaleString("en-IN")}.`,
    ];
    if (input.bookingTiming === "postpone") {
        parts.push(
            "Booking timing preference: postpone booking as long as safely possible. Use price monitoring and only book when the deadline is close or ML predicts a meaningful price/availability risk.",
            "Auto-booking policy: enabled; strategy=latest_safe; price_rise_threshold_percent=12; minimum_confidence=0.6; tracked_component_types=transport,stay."
        );
    } else if (input.bookingTiming === "early") {
        parts.push(
            "Booking timing preference: book early once a good in-budget complete itinerary is found.",
            "Auto-booking policy: disabled unless human approval is requested."
        );
    } else {
        parts.push("Booking timing preference: balanced between price savings and booking certainty.");
    }
    if (input.preferences.trim()) {
        parts.push(`Preferences/Notes: ${input.preferences.trim()}`);
    }
    return parts.join("\n");
}

/**
 * Build a user-facing summary of the trip input (for the first chat bubble).
 */
export function tripInputSummary(input: TripInput): string {
    const lines = [
        `Route: **${input.startingPoint}** → **${input.destination}**`,
        `Dates: ${input.startDate} to ${input.endDate}`,
        `Travellers: ${input.adults} adult(s)${input.children > 0 ? `, ${input.children} child(ren)` : ""}`,
        `Budget: ₹${Number(input.budget).toLocaleString("en-IN")}`,
        `Booking timing: ${
            input.bookingTiming === "postpone"
                ? "Postpone as long as safely possible"
                : input.bookingTiming === "early"
                  ? "Book early when a good option appears"
                  : "Balanced"
        }`,
    ];
    if (input.preferences.trim()) {
        lines.push(`Preferences: ${input.preferences.trim()}`);
    }
    return lines.join("  \n");
}
