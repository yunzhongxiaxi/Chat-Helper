from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api import upload, profile, reply

app = FastAPI(title="ChatHelper API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(profile.router)
app.include_router(reply.router)

@app.get("/")
async def root():
    return {"message": "ChatHelper API is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
