from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class LPRequest(BaseModel):
    request_id: str
    drive_folder_id: str
    search_term: str
    intent: str | None = None
    audience_persona: str | None = None
    audience_segment: str | None = None
    primary_cta: str | None = None
    offer: str | None = None

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/generate")
def generate(req: LPRequest):
    return {
        "status": "received",
        "request_id": req.request_id,
        "search_term": req.search_term
    }
