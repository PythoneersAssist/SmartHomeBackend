import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

import api.users.endpoints as ue
import api.auth.endpoints as ae
import api.house.endpoints as he
import api.rooms.endpoints as re
import api.devices.endpoints as de

from database.database import engine, Base

if not load_dotenv(".env"):
    print("Error loading .env")
    exit(-1)

app = FastAPI()

app.include_router(ue.router)
app.include_router(ae.router)
app.include_router(he.router)
app.include_router(re.router)
app.include_router(de.router)

@app.get("/")
async def root() -> str:
    return "OK"

if __name__ == "__main__":
    Base.metadata.create_all(bind = engine)

    uvicorn.run("main:app", reload = True)