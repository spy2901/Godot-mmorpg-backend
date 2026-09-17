from fastapi import FastAPI

from routers import items, players, quests

app = FastAPI()

app.include_router(items.router)
app.include_router(quests.router)
app.include_router(players.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
