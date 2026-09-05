from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.trip import router
from routes.price_api import router as price_router
from store.db import DATABASE
from services.x402_algorand import configure_price_payment


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pool is opened lazily on the first durable write; close it cleanly on shutdown.
    yield
    DATABASE.close()

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
app.include_router(router)

# Start separately with `uvicorn main:price_api --port 4021`: this makes the
# agent cross an HTTP x402 boundary rather than bypassing it in-process.
price_api = FastAPI(title="TraveBuddy Paid Price API")
price_api.include_router(price_router)
configure_price_payment(price_api)
