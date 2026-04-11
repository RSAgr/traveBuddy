"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import { useTravelPlanner } from "@/components/travel-planner/travel-planner-context";
import { tripInputSummary, tripInputToPrompt } from "@/components/travel-planner/plan-types";
import TransportSection from "@/components/travel-planner/sections/TransportSection";
import HotelSection from "@/components/travel-planner/sections/HotelSection";
import MessageThread from "@/components/travel-planner/sections/MessageThread";
import { Send } from "lucide-react";

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
    const hasInitiated = useRef(false);

    // Make proxy / backend request to start trip
    const startTrip = useCallback(async (prompt: string, address: string = "dummy") => {
        setIsPolling(true);
        setFunctionCalls(["Agent Analyzing Request..."]);
        
        try {
            const res = await fetch("/api/proxy/create_trip", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: "user123", query: prompt, user_address: address }),
            });
            const data = await res.json();
            if (data.trip_id) {
                setTripId(data.trip_id);
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
    }, [addMessage, setTripId]);

    // Polling loop
    const pollTrip = useCallback(async (currentTripId: string) => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch(`/api/proxy/status/${currentTripId}`);
                if (!res.ok) return;
                const data = await res.json();
                
                // data = { status, components, constraints, contract }
                if (data.components) {
                    // Adapt the numeric prices to our Transport/Hotel plan UI state
                    const flights = data.components.filter((c: any) => c.mode === "flight").map((c: any) => ({
                        name: "Found Flight Option",
                        price: c.price,
                        booking_link: "#",
                        departure_from_source: new Date().toISOString(),
                        arrival_at_destination: new Date(Date.now() + 3600000 * 2).toISOString(),
                        description: "Evaluated by TraveBuddy Agent"
                    }));
                    const trains = data.components.filter((c: any) => c.mode === "train").map((c: any) => ({
                        name: "Train Option",
                        price: c.price,
                        booking_link: "#",
                        departure_from_source: new Date().toISOString(),
                        arrival_at_destination: new Date(Date.now() + 3600000 * 12).toISOString(),
                        description: "Evaluated by TraveBuddy Agent"
                    }));
                    const hotels = data.components.filter((c: any) => c.type === "stay").map((c: any) => ({
                        name: "Hotel Found by Agent",
                        price: c.price,
                        booking_link: "#",
                        image_urls: [],
                        rating: 4.5,
                        description: "Recommended stay based on your constraints."
                    }));

                    setPlan(prev => ({
                        ...prev,
                        outbound: { flights, trains },
                        hotels
                    }));
                }

                if (data.status === "BOOKED") {
                    setIsPolling(false);
                    setFunctionCalls([]);
                    clearInterval(interval);
                    addMessage({ role: "assistant", text: "✅ I have executed the booking successfully via blockchain contract!" });
                }
            } catch (e) {
                console.error("Polling error", e);
            }
        }, 5000);
    }, [setPlan, addMessage]);

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

    function handleSend(text: string) {
        if (!text.trim() || isPolling) return;
        addMessage({ role: "user", text: text.trim() });
        // The backend doesn't support chat updates yet!
        // We will just echo it for now.
        addMessage({ role: "assistant", text: "I'm sorry, I cannot update the trip dynamically yet." });
        setInput("");
    }

    const hasOutbound = (plan.outbound.flights?.length ?? 0) > 0 || (plan.outbound.trains?.length ?? 0) > 0;
    const hasHotels = plan.hotels.length > 0;

    if (!ready) {
        return (
            <div className="flex items-center justify-center min-h-[60vh]">
                <div className="w-10 h-10 border-3 border-[#FF5A1F] border-t-transparent rounded-full animate-spin mx-auto" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
            <header className="border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 px-6 py-4 flex items-center justify-between">
                <div>
                    <h1 className="text-xl font-bold text-gray-800 dark:text-gray-100">Travel Planner</h1>
                    {tripInput && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                            {tripInput.startingPoint} → {tripInput.destination} · {tripInput.startDate} to {tripInput.endDate}
                        </p>
                    )}
                </div>
                <button
                    onClick={() => {
                        resetSession();
                        router.push("/travel-planner/details");
                    }}
                    className="px-4 py-2 text-xs font-semibold rounded-full border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
                >
                    &#8635; Re-plan
                </button>
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
                {hasOutbound && <TransportSection title="🛫 Evaluating Transport Options" transports={plan.outbound} />}
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
