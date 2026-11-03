"""FastAPI review API backed by the same durable LangGraph workflow."""

import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from approval import execute

DB = Path("approvals.sqlite")
_lock = Lock()


class ReviewCreate(BaseModel):
    draft: str = Field(min_length=1, max_length=20_000)
    ticket_id: str | None = Field(default=None, max_length=100)


class Decision(BaseModel):
    decision: str
    text: str | None = Field(default=None, max_length=20_000)


def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, ticket_id TEXT, status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")


def list_rows(status: str | None = None):
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM reviews"
        args = ()
        if status:
            query += " WHERE status=?"
            args = (status,)
        query += " ORDER BY created_at DESC"
        return [dict(row) for row in conn.execute(query, args).fetchall()]


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="Approval Workflow API", version="0.2.0", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def home():
    return Path("static/index.html").read_text(encoding="utf-8")


@app.post("/reviews", status_code=201)
def create_review(request: ReviewCreate):
    with _lock:
        result = execute(DB, "start", text=request.draft)
        with sqlite3.connect(DB) as conn:
            conn.execute("INSERT INTO reviews(id,ticket_id,status) VALUES(?,?,?)", (result["id"], request.ticket_id, result["status"]))
    return {**result, "ticket_id": request.ticket_id}


@app.get("/reviews")
def reviews(status: str | None = Query(default=None, pattern="^(pending|completed)$")):
    return {"items": list_rows(status)}


@app.get("/reviews/{request_id}")
def review(request_id: str):
    try:
        result = execute(DB, "status", request_id=request_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    row = next((r for r in list_rows() if r["id"] == request_id), {})
    return {**result, "ticket_id": row.get("ticket_id")}


@app.post("/reviews/{request_id}/decision")
def decide(request_id: str, request: Decision):
    with _lock:
        try:
            current = execute(DB, "status", request_id=request_id)
            if current["status"] != "pending":
                raise HTTPException(status_code=409, detail="This review has already been completed.")
            result = execute(DB, "review", request_id=request_id, decision=request.decision, text=request.text)
            with sqlite3.connect(DB) as conn:
                conn.execute("UPDATE reviews SET status=? WHERE id=?", (result["status"], request_id))
            return result
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="127.0.0.1", port=8000)
