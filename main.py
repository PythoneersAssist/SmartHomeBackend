import uvicorn
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root() -> str:
    return "OK"

if __name__ == "__main__":
    uvicorn.run("main:app", reload=True)