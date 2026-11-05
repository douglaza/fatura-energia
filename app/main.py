from app.routers import ai, faturas, relatorios, upload
from fastapi import FastAPI


app = FastAPI(title="Cemig Bill API")

app.include_router(faturas.router)
app.include_router(upload.router)
app.include_router(relatorios.router)
app.include_router(ai.router)
