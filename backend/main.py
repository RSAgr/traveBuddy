from contextlib import asynccontextmanager
from fastapi import FastAPI
from routes.trip import router
from store.db import DATABASE


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pool is opened lazily on the first durable write; close it cleanly on shutdown.
    yield
    DATABASE.close()

app = FastAPI(lifespan=lifespan)
app.include_router(router)
