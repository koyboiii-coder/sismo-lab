from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter()


class StrokePoint(BaseModel):
    x: float
    y: float
    p: float = 0.5
    t: float = 0.0


class Stroke(BaseModel):
    points: list[StrokePoint] = Field(min_length=2)
    width: float = 3.0


class NoteIn(BaseModel):
    strokes: list[Stroke] = Field(min_length=1)


def _serialize(row) -> dict:
    return {
        "id": row["id"],
        "created_at": row["created_at"].isoformat().replace("+00:00", "Z"),
        "strokes": row["strokes"],
    }


@router.get("/notes")
async def list_notes(request: Request, limit: int = Query(20, ge=1, le=100)):
    pool = request.app.state.db.pool
    rows = await pool.fetch(
        "SELECT id, created_at, strokes FROM notes ORDER BY created_at DESC LIMIT $1", limit
    )
    return [_serialize(r) for r in rows]


@router.post("/notes", status_code=201)
async def create_note(note: NoteIn, request: Request):
    pool = request.app.state.db.pool
    # Objeto Python nativo, sin json.dumps manual: api/db.py registra un
    # codec jsonb (encoder=json.dumps) sobre esta conexión -- serializar acá
    # también encimaría una segunda vuelta de encoding sobre el string
    # resultante. El "::jsonb" solo asegura que asyncpg reconozca el tipo
    # del parámetro y dispare ese codec.
    strokes = [s.model_dump() for s in note.strokes]
    row = await pool.fetchrow(
        "INSERT INTO notes (strokes) VALUES ($1::jsonb) RETURNING id, created_at, strokes",
        strokes,
    )
    return _serialize(row)


@router.delete("/notes/{note_id}", status_code=204)
async def delete_note(note_id: int, request: Request):
    pool = request.app.state.db.pool
    result = await pool.execute("DELETE FROM notes WHERE id = $1", note_id)
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="note not found")
