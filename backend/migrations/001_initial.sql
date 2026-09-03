CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY, user_id TEXT NOT NULL, source TEXT, destination TEXT,
    departure_at TIMESTAMPTZ, budget NUMERIC, preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    itinerary JSONB, status TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS price_snapshots (
    id BIGSERIAL PRIMARY KEY, trip_id TEXT, route TEXT NOT NULL, source TEXT, destination TEXT,
    transport_type TEXT NOT NULL, current_price NUMERIC NOT NULL, observed_at TIMESTAMPTZ NOT NULL,
    days_to_departure NUMERIC, demand_index NUMERIC, seasonality_index NUMERIC,
    features JSONB NOT NULL DEFAULT '{}'::jsonb, components JSONB NOT NULL DEFAULT '[]'::jsonb
);
CREATE INDEX IF NOT EXISTS price_snapshots_trip_observed_idx ON price_snapshots (trip_id, observed_at);
CREATE INDEX IF NOT EXISTS price_snapshots_route_type_observed_idx ON price_snapshots (route, transport_type, observed_at);
CREATE TABLE IF NOT EXISTS booking_decisions (
    id BIGSERIAL PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id), predicted_price NUMERIC,
    decision TEXT NOT NULL CHECK (decision IN ('WAIT', 'BOOK')), confidence NUMERIC, trend TEXT,
    reasoning TEXT, metadata JSONB NOT NULL DEFAULT '{}'::jsonb, decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS blockchain_deployments (
    id BIGSERIAL PRIMARY KEY, trip_id TEXT NOT NULL REFERENCES trips(id), algorand_app_id TEXT,
    transaction_id TEXT, status TEXT NOT NULL, metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
