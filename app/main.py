from app.routers import faturas, upload
from fastapi import FastAPI


app = FastAPI(title="Cemig Bill API")

app.include_router(faturas.router)
app.include_router(upload.router)
