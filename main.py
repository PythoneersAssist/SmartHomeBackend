import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load a local .env when present. In production (e.g. Azure App Service)
# configuration is injected as environment variables, so a missing file is fine.
load_dotenv(".env")

import api.users.endpoints as ue
import api.auth.endpoints as ae
import api.house.endpoints as he
import api.rooms.endpoints as re
import api.devices.endpoints as de
import api.automations.endpoints as auto_e
import api.energy.endpoints as energy_e
import api.notifications.endpoints as notif_e
import api.gemini.endpoints as gemini_e
import api.presets.endpoints as presets_e
from api.automations.scheduler import is_scheduler_enabled, scheduler
from api.energy.scheduler import is_energy_history_scheduler_enabled, energy_history_scheduler
from api.simulation.scheduler import is_temperature_simulation_enabled, temperature_simulation_scheduler

from database.database import engine, Base, ensure_schema_upgrades

# Environment switch: set ENVIRONMENT=production in Azure App Settings to run
# in release mode. Anything other than "production" is treated as development.
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"

# In production, hide the interactive docs and the OpenAPI schema entirely.
app = FastAPI(
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
    openapi_url=None if IS_PRODUCTION else "/openapi.json",
)

# Comma-separated list of allowed origins, configurable per environment.
_default_origins = "http://localhost:5173,http://localhost:5174,http://localhost:5175,http://localhost:5176"
cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", _default_origins).split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ue.router)
app.include_router(ae.router)
app.include_router(he.router)
app.include_router(re.router)
app.include_router(de.router)
app.include_router(auto_e.router)
app.include_router(energy_e.router)
app.include_router(notif_e.router)
app.include_router(gemini_e.router)
app.include_router(presets_e.router)


@app.on_event("startup")
async def startup_db_upgrade() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()
    if is_scheduler_enabled():
        await scheduler.start()
    if is_energy_history_scheduler_enabled():
        await energy_history_scheduler.start()
    if is_temperature_simulation_enabled():
        await temperature_simulation_scheduler.start()


@app.on_event("shutdown")
async def shutdown_background_services() -> None:
    await scheduler.stop()
    await energy_history_scheduler.stop()
    await temperature_simulation_scheduler.stop()

@app.get("/")
async def root() -> str:
    return "OK"

if __name__ == "__main__":
    Base.metadata.create_all(bind = engine)
    ensure_schema_upgrades()

    uvicorn.run("main:app", reload = True)