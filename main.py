import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

if not load_dotenv(".env"):
    print("Error loading .env")
    exit(-1)

import api.users.endpoints as ue
import api.auth.endpoints as ae
import api.house.endpoints as he
import api.rooms.endpoints as re
import api.devices.endpoints as de
import api.automations.endpoints as auto_e
import api.energy.endpoints as energy_e
import api.notifications.endpoints as notif_e
from api.automations.scheduler import is_scheduler_enabled, scheduler

from database.database import engine, Base, ensure_schema_upgrades

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:5175", "http://localhost:5176"],
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


@app.on_event("startup")
async def startup_db_upgrade() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_upgrades()
    if is_scheduler_enabled():
        await scheduler.start()


@app.on_event("shutdown")
async def shutdown_background_services() -> None:
    await scheduler.stop()

@app.get("/")
async def root() -> str:
    return "OK"

if __name__ == "__main__":
    Base.metadata.create_all(bind = engine)
    ensure_schema_upgrades()

    uvicorn.run("main:app", reload = True)