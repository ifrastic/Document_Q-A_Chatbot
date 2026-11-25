import os, time, base64
import requests
from dotenv import load_dotenv
load_dotenv()

from crypto_utils import encrypt, decrypt

SERVICE_URL = os.getenv("SERVICE_URL", "http://127.0.0.1:8001")
API_KEY = os.environ["SECURITY_API_KEY"]

_token = None
_token_time = 0
TOKEN_REFRESH_SECONDS = 60 * 60  # token 2 ghante ka hai, hum 1 ghante baad naya le lete hain


def _get_token(force=False):
    global _token, _token_time
    if force or not _token or time.time() - _token_time > TOKEN_REFRESH_SECONDS:
        r = requests.post(f"{SERVICE_URL}/token",
                          headers={"X-API-Key": API_KEY}, timeout=10)
        r.raise_for_status()
        _token = r.json()["token"]
        _token_time = time.time()
    return _token


def _call(path, payload, timeout=10):
    body = {"data": encrypt(payload)}
    for attempt in range(2):
        r = requests.post(
            f"{SERVICE_URL}{path}", json=body,
            headers={"Authorization": f"Bearer {_get_token(force=attempt == 1)}"},
            timeout=timeout,
        )
        if r.status_code != 401:
            break
    r.raise_for_status()
    return decrypt(r.json()["data"])


def get_history(doc_name: str):
    result = _call("/history/get", {"doc_name": doc_name})
    return [(q, a) for q, a in result["chats"]]


def save_chat(doc_name: str, question: str, answer: str):
    _call("/history/save",
          {"doc_name": doc_name, "question": question, "answer": answer})


def register_document(doc_name: str, pages: list):
    return _call("/documents/register",
                 {"doc_name": doc_name, "pages": pages}, timeout=120)


def list_documents():
    return [(i, n) for i, n in _call("/documents/list", {})["documents"]]


def get_embeddings(doc_id: int):
    pages = _call("/documents/embeddings", {"doc_id": doc_id}, timeout=60)["pages"]
    return [(p["text"], base64.b64decode(p["embedding"])) for p in pages]
def save_feedback(doc_name: str, question: str, answer: str, rating: int, comment: str = ""):
    _call("/feedback/save", {
        "doc_name": doc_name,
        "question": question,
        "answer": answer,
        "rating": rating,
        "comment": comment,
    })