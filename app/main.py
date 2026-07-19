from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router


app = FastAPI(
    title="App Store Review Analysis API",
    description=(
        "Collect and analyze public Apple App Store reviews."
    ),
    version="0.1.0",
)

app.include_router(router)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", tags=["ui"])
async def review_analysis_ui() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.get("/health", tags=["system"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
