import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

import users.endpoints as ue
import auth.endpoints as ae
from database.database import engine, Base

if not load_dotenv(".env"):
    print("Error loading .env")

app = FastAPI()

app.include_router(ue.router)
app.include_router(ae.router)

@app.get("/")
async def root() -> str:
    return "OK"

if __name__ == "__main__":
    Base.metadata.create_all(bind = engine)

    uvicorn.run("main:app", reload=True)