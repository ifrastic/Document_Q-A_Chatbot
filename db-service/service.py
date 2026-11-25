import os, hashlib, hmac, base64
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from cryptography.exceptions import InvalidTag

from crypto_utils import encrypt, decrypt as _decrypt
from db import get_connection, create_tables
from sql import (SAVE_CHAT, GET_RECENT_CHATS, DELETE_OLD_CHATS,
                 INSERT_DOC, GET_DOC, DELETE_DOC, INSERT_EMBEDDING,
                 GET_DOCUMENTS, GET_EMBEDDINGS,SAVE_FEEDBACK)

app = FastAPI()
create_tables()

TOKEN_SECRET_KEY = os.environ["TOKEN_SECRET_KEY"]
TOKEN_ALGORITHM = os.getenv("TOKEN_ALGORITHM", "HS256")
TOKEN_EXPIRE_HOURS = int(os.getenv("TOKEN_EXPIRE_HOURS", "2"))
API_KEY_HASH = os.environ["SECURITY_API_KEY_HASH"]


class Payload(BaseModel):
    data: str


def decrypt(text: str):
    try:
        return _decrypt(text)
    except (InvalidTag, ValueError):
        raise HTTPException(400, "Invalid encrypted data")


def verify(authorization: str):
    try:
        token = authorization.replace("Bearer ", "")
        jwt.decode(token, TOKEN_SECRET_KEY, algorithms=[TOKEN_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


@app.post("/token")
def get_token(x_api_key: str = Header(...)):
    given = hashlib.sha256(x_api_key.encode()).hexdigest()
    if not hmac.compare_digest(given, API_KEY_HASH):
        raise HTTPException(401, "Invalid API key")
    payload = {
        "sub": "chatbot",
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return {"token": jwt.encode(payload, TOKEN_SECRET_KEY, algorithm=TOKEN_ALGORITHM)}


@app.post("/history/get")
def history_get(p: Payload, authorization: str = Header(...)):
    verify(authorization)
    req = decrypt(p.data)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(GET_DOC, (req["doc_name"],))
        row = cur.fetchone()
        chats = []
        if row:
            cur.execute(GET_RECENT_CHATS, (row[0],))
            chats = [[q, a] for q, a in cur.fetchall()]
    finally:
        conn.close()
    return {"data": encrypt({"chats": chats})}


@app.post("/history/save")
def history_save(p: Payload, authorization: str = Header(...)):
    verify(authorization)
    req = decrypt(p.data)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(GET_DOC, (req["doc_name"],))
        row = cur.fetchone()
        if row:
            doc_id = row[0]
            cur.execute(SAVE_CHAT, (doc_id, req["question"], req["answer"]))
            cur.execute(DELETE_OLD_CHATS, (doc_id, doc_id))
            conn.commit()
    finally:
        conn.close()
    return {"data": encrypt({"saved": True})}


@app.post("/documents/register")
def documents_register(p: Payload, authorization: str = Header(...)):
    verify(authorization)
    req = decrypt(p.data)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(INSERT_DOC, (req["doc_name"],))
        cur.execute(GET_DOC, (req["doc_name"],))
        doc_id = cur.fetchone()[0]
        cur.execute(DELETE_DOC, (doc_id,))
        for page in req["pages"]:
            emb = base64.b64decode(page["embedding"])
            cur.execute(INSERT_EMBEDDING, (doc_id, page["text"], emb))
        conn.commit()
    finally:
        conn.close()
    return {"data": encrypt({"saved": True, "pages": len(req["pages"])})}


@app.post("/documents/list")
def documents_list(p: Payload, authorization: str = Header(...)):
    verify(authorization)
    decrypt(p.data)
    conn = get_connection()
    try:
        rows = conn.execute(GET_DOCUMENTS).fetchall()
    finally:
        conn.close()
    return {"data": encrypt({"documents": [[i, n] for i, n in rows]})}


@app.post("/documents/embeddings")
def documents_embeddings(p: Payload, authorization: str = Header(...)):
    verify(authorization)
    req = decrypt(p.data)
    conn = get_connection()
    try:
        rows = conn.execute(GET_EMBEDDINGS, (int(req["doc_id"]),)).fetchall()
    finally:
        conn.close()
    pages = [{"text": t, "embedding": base64.b64encode(e).decode()}
             for t, e in rows if t and e]
    return {"data": encrypt({"pages": pages})}
@app.post("/feedback/save")
def feedback_save(p: Payload, authorization: str = Header(...)):
    verify(authorization)
    req = decrypt(p.data)

    rating = int(req["rating"])
    if rating not in (1, -1):
        raise HTTPException(400, "Invalid rating")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(GET_DOC, (req["doc_name"],))
        row = cur.fetchone()
        doc_id = row[0] if row else None
        cur.execute(
            SAVE_FEEDBACK,
            (doc_id, req["question"], req["answer"], rating, req.get("comment", "")),
        )
        conn.commit()
    finally:
        conn.close()
    return {"data": encrypt({"saved": True})}