CREATE TABLE IF NOT EXISTS price_overrides (
    id BIGSERIAL PRIMARY KEY,
    route TEXT NOT NULL DEFAULT 'Puri',
    component_name TEXT NOT NULL,
    component_type TEXT,
    mode TEXT,
    price NUMERIC,
    price_multiplier NUMERIC,
    active BOOLEAN NOT NULL DEFAULT true,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (route, component_name)
);

CREATE INDEX IF NOT EXISTS price_overrides_active_route_idx
    ON price_overrides (active, route);
