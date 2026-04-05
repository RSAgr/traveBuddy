from fastapi import FastAPI
from routes.trip import router

app = FastAPI()
app.include_router(router)