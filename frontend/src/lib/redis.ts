import { createClient, type RedisClientType } from "redis";

type AutocompleteCacheValue = {
    predictions: { description: string; place_id: string }[];
};

const AUTOCOMPLETE_TTL_SECONDS = 60 * 60;

let redisClientPromise: Promise<RedisClientType | null> | null = null;

async function getRedisClient(): Promise<RedisClientType | null> {
    const redisUrl = process.env.REDIS_URL;
    if (!redisUrl) {
        return null;
    }

    if (!redisClientPromise) {
        redisClientPromise = (async () => {
            const client = createClient({ url: redisUrl });
            client.on("error", (error) => {
                console.error("[Redis] Client error:", error);
            });

            await client.connect();
            return client;
        })().catch((error) => {
            console.error("[Redis] Connection failed:", error);
            redisClientPromise = null;
            return null;
        });
    }

    return redisClientPromise;
}

export async function getCachedAutocomplete(input: string): Promise<AutocompleteCacheValue | null> {
    const client = await getRedisClient();
    if (!client) {
        return null;
    }

    const cachedValue = await client.get(`places:autocomplete:${input.trim().toLowerCase()}`);
    if (!cachedValue) {
        return null;
    }

    try {
        return JSON.parse(cachedValue) as AutocompleteCacheValue;
    } catch (error) {
        console.error("[Redis] Failed to parse cached autocomplete payload:", error);
        return null;
    }
}

export async function setCachedAutocomplete(
    input: string,
    value: AutocompleteCacheValue,
): Promise<void> {
    const client = await getRedisClient();
    if (!client) {
        return;
    }

    await client.set(
        `places:autocomplete:${input.trim().toLowerCase()}`,
        JSON.stringify(value),
        {
            EX: AUTOCOMPLETE_TTL_SECONDS,
        },
    );
}