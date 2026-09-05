"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useTravelPlanner } from "@/components/travel-planner/travel-planner-context";
import { tripInputSummary, tripInputToPrompt } from "@/components/travel-planner/plan-types";
import TransportSection from "@/components/travel-planner/sections/TransportSection";
import HotelSection from "@/components/travel-planner/sections/HotelSection";
import MessageThread from "@/components/travel-planner/sections/MessageThread";
import { CheckCircle2, Send } from "lucide-react";

// Call FastAPI directly. The former Next.js rewrite intermittently reset the
// upstream socket while an x402-paid price lookup was in progress.
const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://127.0.0.1:8000";

type DecisionSummary = {
    decision: string;
    reason: string;
    confidence: number;
    cost?: number;
    itinerary?: {
        route: string;
        start_date: string;
        checkout_date: string;
        nights: number;
        estimated_total: number;
        timeline: Array<{
            title: string;
            date: string;
            time: string;
            details: string[];
            booking_required: boolean;
        }>;
        bookable_public_places: Array<{
            name: string;
            booking_option?: string;
            price?: number;
            estimated_cost?: number;
        }>;
    };
    selected_components?: Array<{
        type: string;
        mode: string;
        name?: string;
        price: number;
        operator?: string;
    }>;
};

export default function Dashboard() {
    const router = useRouter();
    const {
        ready,
        tripId,
        setTripId,
        tripInput,
        plan,
        setPlan,
        messages,
        addMessage,
        saveSession,
        resetSession,
    } = useTravelPlanner();

    const [input, setInput] = useState("");
    const [isPolling, setIsPolling] = useState(false);
    const [functionCalls, setFunctionCalls] = useState<string[]>([]);
    const [decisionSummary, setDecisionSummary] = useState<DecisionSummary | null>(null);
    const [copiedTripId, setCopiedTripId] = useState(false);
    const hasInitiated = useRef(false);
    const alreadyBookedRef = useRef(false);
    const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);

    // Polling loop
    const pollTrip = useCallback(async (currentTripId: string) => {
        if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
        }
        pollingIntervalRef.current = setInterval(async () => {
            try {
                const res = await fetch(`${backendUrl}/status/${currentTripId}`);
                if (res.status === 404) {
                    setIsPolling(false);
                    setFunctionCalls([]);
                    setTripId(null);
                    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
                    addMessage({ role: "assistant", text: "That trip session expired after the backend restarted. Please use Re-plan to start a fresh trip." });
                    return;
                }
                if (!res.ok) return;
                const data = await res.json();

                if (data.last_decision) {
                    const confidence = Math.round((data.last_decision.confidence ?? 0) * 100);
                    setDecisionSummary(data.last_decision);
                    setFunctionCalls([
                        `${data.last_decision.decision}: ${data.last_decision.reason} (${confidence}% confidence)`
                    ]);
                }
                
                // data = { status, components, constraints, contract }
                if (data.components) {
                    // Adapt the numeric prices to our Transport/Hotel plan UI state
                    const cabs = data.components.filter((c: any) => ["flight", "bus", "cab"].includes(c.mode)).map((c: any) => ({
                        name: c.name ?? `${c.mode === "flight" ? "Flight" : c.mode === "bus" ? "Bus" : "Cab"} Option`,
                        price: c.price,
                        booking_link: "#",
                        departure_from_source: new Date().toISOString(),
                        arrival_at_destination: new Date(Date.now() + 3600000 * 2).toISOString(),
                        description: `${c.operator ?? "Mock provider"} · ${c.route ?? "Ranchi to Puri"} · ${c.duration ?? "Timing available in mock catalog"}`
                    }));
                    const trains = data.components.filter((c: any) => c.mode === "train").map((c: any) => ({
                        name: c.name ?? "Train Option",
                        price: c.price,
                        booking_link: "#",
                        departure_from_source: new Date().toISOString(),
                        arrival_at_destination: new Date(Date.now() + 3600000 * 12).toISOString(),
                        description: `${c.train_number ?? ""} ${c.operator ?? "Indian Railways"} · ${c.route ?? "Ranchi to Puri"} · ${c.duration ?? ""}`
                    }));
                    const hotels = data.components.filter((c: any) => c.type === "stay").map((c: any) => ({
                        name: c.name ?? "Hotel Found by Agent",
                        price: c.price,
                        booking_link: "#",
                        image_urls: [],
                        rating: c.rating ?? 4.5,
                        description: `${c.area ?? "Puri"} · ${(c.amenities ?? []).join(", ") || "Recommended stay based on your constraints."}`
                    }));

                    setPlan(prev => ({
                        ...prev,
                        outbound: { cabs, trains },
                        hotels
                    }));
                }

                if (data.status === "NEEDS_CLARIFICATION") {
                    setIsPolling(false);
                    setFunctionCalls([]);
                    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
                    addMessage({ role: "assistant", text: data.clarification_question ?? "I need a little more detail before searching." });
                } else if (data.status === "AWAITING_HUMAN_APPROVAL") {
                    setIsPolling(false);
                    setFunctionCalls([]);
                    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
                    addMessage({ role: "assistant", text: data.human_approval_request?.reason ?? "Please approve before I book this option." });
                } else if (data.status === "FAILED") {
                    setIsPolling(false);
                    setFunctionCalls([]);
                    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
                    addMessage({ role: "assistant", text: `Trip monitoring failed: ${data.error ?? "Unknown backend error"}` });
                } else if (data.status === "BOOKED" && !alreadyBookedRef.current) {
                    alreadyBookedRef.current = true;
                    setIsPolling(false);
                    setFunctionCalls([]);
                    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
                    
                    let componentsStr = "";
                    if (data.booking && data.booking.components) {
                        const formatted = data.booking.components.map((c: any) => 
                            `${c.mode === 'hotel' ? 'Hotel' : c.mode === 'cab' ? 'Cab' : 'Train'}: ₹${c.price}`
                        ).join(", ");
                        
                        let txDetails = "";
                        if (data.contract) {
                            txDetails = `\n**App ID**: ${data.contract.app_id}\n**Transaction ID**: ${data.contract.create_tx_id}`;
                        }
                        
                        componentsStr = `\n\n**Booked Details**: ${formatted}${txDetails}`;
                    }

                    addMessage({ role: "assistant", text: `I have executed the booking successfully via blockchain contract!${componentsStr}` });
                } else if (data.status === "BOOKED") {
                    setIsPolling(false);
                    setFunctionCalls([]);
                    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
                }
            } catch (e) {
                console.error("Polling error", e);
            }
        }, 5000);
    }, [setPlan, addMessage, setTripId]);

    // Make proxy / backend request to start trip
    const startTrip = useCallback(async (prompt: string, address: string = "dummy") => {
        setIsPolling(true);
        setFunctionCalls(["Agent Analyzing Request..."]);
        alreadyBookedRef.current = false;

        try {
            const res = await fetch(`${backendUrl}/create_trip`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "user123", query: prompt, user_address: address }),
            });
            if (!res.ok) {
                const message = await res.text();
                addMessage({ role: "assistant", text: `Failed to initialize trip: ${message}` });
                setIsPolling(false);
                setFunctionCalls([]);
                return;
            }
            const data = await res.json();
            if (data.trip_id) {
                setTripId(data.trip_id);
                if (data.clarification_question) {
                    addMessage({ role: "assistant", text: data.clarification_question });
                    setIsPolling(false);
                    setFunctionCalls([]);
                    return;
                }
                setFunctionCalls(["Evaluating Flight/Hotel Options..."]);
                pollTrip(data.trip_id);
            } else {
                addMessage({ role: "assistant", text: "Failed to initialize trip with agent." });
                setIsPolling(false);
                setFunctionCalls([]);
            }
        } catch (e) {
            console.error(e);
            setIsPolling(false);
            setFunctionCalls([]);
        }
    }, [addMessage, setTripId, pollTrip]);

    /* ── Initial prompt on mount ── */
    useEffect(() => {
        if (!ready || !tripInput || hasInitiated.current) return;
        hasInitiated.current = true;

        if (messages.length > 0) {
            // Already started (e.g refreshed), resume polling if we have tripId
            if (tripId) pollTrip(tripId);
            return;
        }

        addMessage({ role: "user", text: tripInputSummary(tripInput) });
        const prompt = tripInputToPrompt(tripInput);
        startTrip(prompt);
    }, [ready, tripInput, addMessage, messages.length, startTrip, tripId, pollTrip]);

    /* ── Redirect or load saved session ── */
    useEffect(() => {
        if (ready && !tripInput && !hasInitiated.current && !tripId) {
            router.replace("/travel-planner/details");
        }
    }, [ready, tripInput, router, tripId]);

    /* ── Save session when done ── */
    useEffect(() => {
        if (!isPolling && ready && tripInput && hasInitiated.current) {
            saveSession();
        }
    }, [isPolling, ready, tripInput, saveSession]);

    async function handleSend(text: string) {
        if (!text.trim() || isPolling) return;
        const message = text.trim();
        addMessage({ role: "user", text: message });
        setInput("");
        if (!tripId) {
            addMessage({ role: "assistant", text: "Please start a trip first." });
            return;
        }

        setIsPolling(true);
        setFunctionCalls(["Updating trip constraints..."]);
        try {
            const res = await fetch(`${backendUrl}/trip/${tripId}/message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message,
                    approved: /\b(yes|approve|book|confirm|go ahead)\b/i.test(message),
                }),
            });
            if (!res.ok) {
                const error = await res.text();
                addMessage({ role: "assistant", text: `I could not update the trip: ${error}` });
                setIsPolling(false);
                setFunctionCalls([]);
                return;
            }
            const data = await res.json();
            if (data.clarification_question) {
                addMessage({ role: "assistant", text: data.clarification_question });
                setIsPolling(false);
                setFunctionCalls([]);
                return;
            }
            if (data.human_approval_request) {
                addMessage({ role: "assistant", text: data.human_approval_request.reason });
                setIsPolling(false);
                setFunctionCalls([]);
                return;
            }
            pollTrip(tripId);
        } catch (e) {
            console.error(e);
            addMessage({ role: "assistant", text: "I could not update the trip. Please try again." });
            setIsPolling(false);
            setFunctionCalls([]);
        }
    }

    const hasOutbound = (plan.outbound.cabs?.length ?? 0) > 0 || (plan.outbound.trains?.length ?? 0) > 0;
    const hasHotels = plan.hotels.length > 0;
    const shortTripId = tripId ? `${tripId.slice(0, 8)}…${tripId.slice(-4)}` : null;

    async function copyTripId() {
        if (!tripId) return;
        await navigator.clipboard.writeText(tripId);
        setCopiedTripId(true);
        setTimeout(() => setCopiedTripId(false), 1500);
    }

    if (!ready) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="w-10 h-10 border-3 border-[#FF5A1F] border-t-transparent rounded-full animate-spin mx-auto" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
            <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 px-6 py-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">Travel Planner</h1>
                    {tripInput && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                            {tripInput.startingPoint} → {tripInput.destination} · {tripInput.startDate} to {tripInput.endDate}
                        </p>
                    )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                    {tripId && (
                        <button
                            type="button"
                            onClick={copyTripId}
                            title={tripId}
                            className="px-4 py-2 text-xs font-semibold rounded-full border border-[#FF5A1F]/30 bg-[#FF5A1F]/10 text-[#FF5A1F] hover:bg-[#FF5A1F]/15 transition"
                        >
                            Trip ID: {copiedTripId ? "Copied!" : shortTripId}
                        </button>
                    )}
                    <button
                        onClick={() => {
                            resetSession();
                            router.push("/travel-planner/details");
                        }}
                        className="px-4 py-2 text-xs font-semibold rounded-full border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
                    >
                        &#8635; Re-plan
                    </button>
                </div>
            </header>

            {isPolling && functionCalls.length > 0 && (
                <div className="sticky top-[65px] z-20 flex flex-wrap gap-2 px-6 py-3 bg-gray-50/90 dark:bg-gray-950/90 backdrop-blur-md">
                    {functionCalls.map((call, i) => (
                        <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-[#FF5A1F]/10 text-[#FF5A1F] animate-pulse">
                            <span className="w-1.5 h-1.5 rounded-full bg-current" />
                            {call}
                        </span>
                    ))}
                </div>
            )}

            <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-8">
                <MessageThread messages={messages} isStreaming={isPolling} />
                {decisionSummary && (
                    <section className="tp-section border border-gray-200 dark:border-gray-800 rounded-xl p-4 bg-white dark:bg-gray-900">
                        <div className="flex items-start gap-3">
                            <CheckCircle2 className="w-5 h-5 text-[#FF5A1F] mt-0.5" />
                            <div className="min-w-0">
                                <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
                                    Decision Engine Recommendation
                                </h2>
                                <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                                    {decisionSummary.decision === "BOOK" ? "Selected combo ready for booking" : "Still evaluating options"} · {Math.round((decisionSummary.confidence ?? 0) * 100)}% confidence
                                </p>
                                {decisionSummary.cost != null && (
                                    <p className="text-sm font-semibold text-[#FF5A1F] mt-2">
                                        Selected total: ₹{Number(decisionSummary.cost).toLocaleString("en-IN")}
                                    </p>
                                )}
                                {decisionSummary.itinerary && (
                                    <div className="mt-4 space-y-4">
                                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                            <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3">
                                                <p className="text-xs text-gray-500 dark:text-gray-400">Route</p>
                                                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{decisionSummary.itinerary.route}</p>
                                            </div>
                                            <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3">
                                                <p className="text-xs text-gray-500 dark:text-gray-400">Stay</p>
                                                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{decisionSummary.itinerary.nights} night(s)</p>
                                            </div>
                                            <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3">
                                                <p className="text-xs text-gray-500 dark:text-gray-400">Checkout</p>
                                                <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{decisionSummary.itinerary.checkout_date}</p>
                                            </div>
                                        </div>
                                        <div>
                                            <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Booking Timeline</h3>
                                            <div className="space-y-2">
                                                {decisionSummary.itinerary.timeline.map((item, index) => (
                                                    <div key={index} className="rounded-lg border border-gray-100 dark:border-gray-800 p-3">
                                                        <div className="flex flex-wrap items-center justify-between gap-2">
                                                            <p className="text-sm font-semibold text-gray-900 dark:text-gray-100">{item.title}</p>
                                                            <span className="text-xs text-gray-500 dark:text-gray-400">{item.date} · {item.time}</span>
                                                        </div>
                                                        <ul className="mt-2 space-y-1">
                                                            {item.details.map((detail, detailIndex) => (
                                                                <li key={detailIndex} className="text-xs text-gray-600 dark:text-gray-300">{detail}</li>
                                                            ))}
                                                        </ul>
                                                        {item.booking_required && (
                                                            <span className="inline-flex mt-2 px-2 py-1 rounded-full text-xs bg-[#FF5A1F]/10 text-[#FF5A1F]">Booking slot needed</span>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                        {decisionSummary.itinerary.bookable_public_places.length > 0 && (
                                            <div>
                                                <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Public Place Booking Options</h3>
                                                <div className="flex flex-wrap gap-2">
                                                    {decisionSummary.itinerary.bookable_public_places.map((place, index) => (
                                                        <span key={index} className="px-3 py-1 rounded-full text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200">
                                                            {place.name}: {place.booking_option ?? "Reservation available"}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}
                                {decisionSummary.selected_components && (
                                    <div className="flex flex-wrap gap-2 mt-3">
                                        {decisionSummary.selected_components.map((component, index) => (
                                            <span key={index} className="px-3 py-1 rounded-full text-xs bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200">
                                                {component.type === "stay" ? "Hotel" : component.mode}: {component.name ?? component.operator ?? "Selected option"} · ₹{Number(component.price).toLocaleString("en-IN")}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-3">
                                    The lists below are candidates. Only this selected combo is used when booking executes.
                                </p>
                            </div>
                        </div>
                    </section>
                )}
                {hasOutbound && <TransportSection title="Transport Candidates" transports={plan.outbound} />}
                {hasHotels && <HotelSection hotels={plan.hotels} />}
            </div>

            <div className="fixed bottom-0 left-0 right-0 z-40 p-4 md:p-6 pointer-events-none">
                <div className="max-w-3xl mx-auto pointer-events-auto">
                    <form
                        onSubmit={(e) => { e.preventDefault(); handleSend(input); }}
                        className="flex gap-2 bg-white/80 dark:bg-gray-900/80 backdrop-blur-lg p-2 rounded-full border border-gray-200 dark:border-gray-800 shadow-2xl"
                    >
                        <input
                            className="flex-1 bg-transparent px-5 py-3 text-sm outline-none placeholder:text-gray-400 dark:text-gray-100"
                            placeholder={isPolling ? "Waiting for booking execution…" : "Ask for changes or details…"}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            disabled={isPolling}
                        />
                        <button type="submit" disabled={isPolling || !input.trim()} className="px-5 py-3 rounded-full bg-[#FF5A1F] text-white font-semibold text-sm hover:bg-[#e14f1c] disabled:opacity-30 transition">
                            <Send className="w-4 h-4" />
                        </button>
                    </form>
                </div>
            </div>
        </div>
    );
}
