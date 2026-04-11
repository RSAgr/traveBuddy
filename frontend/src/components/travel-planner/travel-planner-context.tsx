"use client";

import {
    createContext,
    useContext,
    useEffect,
    useState,
    useCallback,
    type ReactNode,
} from "react";
import {
    type TripInput,
    type PlanState,
    type ChatMessage,
    emptyPlanState,
} from "./plan-types";

interface TravelPlannerCtx {
    ready: boolean;
    tripId: string | null;
    setTripId: (id: string | null) => void;
    tripInput: TripInput | null;
    setTripInput: (input: TripInput) => void;
    plan: PlanState;
    setPlan: React.Dispatch<React.SetStateAction<PlanState>>;
    messages: ChatMessage[];
    addMessage: (msg: ChatMessage) => void;
    saveSession: () => void;
    resetSession: () => void;
}

const Ctx = createContext<TravelPlannerCtx>(null!);

export function useTravelPlanner() {
    return useContext(Ctx);
}

export function TravelPlannerProvider({ children }: { children: ReactNode }) {
    const [ready, setReady] = useState(false);
    const [tripId, setTripId] = useState<string | null>(null);

    const [tripInput, setTripInput] = useState<TripInput | null>(null);
    const [plan, setPlan] = useState<PlanState>(emptyPlanState());
    const [messages, setMessages] = useState<ChatMessage[]>([]);

    const addMessage = useCallback((msg: ChatMessage) => {
        setMessages((prev) => [...prev, msg]);
    }, []);

    const saveSession = useCallback(() => {
        if (!tripInput) return;
        try {
            localStorage.setItem("explorify_trip_session", JSON.stringify({
                tripId,
                tripInput,
                plan,
                messages,
            }));
        } catch (e) {
            console.error("Failed to save session", e);
        }
    }, [tripId, tripInput, plan, messages]);

    const resetSession = useCallback(() => {
        localStorage.removeItem("explorify_trip_session");
        setTripId(null);
        setTripInput(null);
        setPlan(emptyPlanState());
        setMessages([]);
    }, []);

    useEffect(() => {
        // Hydrate from localStorage
        const saved = localStorage.getItem("explorify_trip_session");
        if (saved) {
            try {
                const data = JSON.parse(saved);
                setTripId(data.tripId || null);
                setTripInput(data.tripInput);
                setPlan(data.plan);
                setMessages(data.messages);
            } catch (err) {
                console.error("Failed to parse saved session", err);
            }
        }
        setReady(true);
    }, []);

    return (
        <Ctx.Provider
            value={{
                ready,
                tripId,
                setTripId,
                tripInput,
                setTripInput,
                plan,
                setPlan,
                messages,
                addMessage,
                saveSession,
                resetSession,
            }}
        >
            {children}
        </Ctx.Provider>
    );
}
