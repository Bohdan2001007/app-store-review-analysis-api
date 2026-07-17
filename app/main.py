from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="App Store Review Analysis API",
    description=(
        "Collect and analyze public Apple App Store reviews."
    ),
    version="0.1.0",
)

app.include_router(router)


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}