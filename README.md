# Document AI Chatbot

Upload your documents (PDF, TXT, DOCX) and ask questions about them in plain language.
The answers come from **Google Gemini**, using only the document you choose.

- Upload documents on the **Documents** page, then pick one on the **Chat** page and ask
- Remembers the last 6 questions and answers for each document ("what did I ask before?")
- 👍 / 👎 feedback on every answer, with an optional comment
- Chat history, embeddings and feedback are kept in a **separate database service**, reached
  only with a login token, and every message to it is **AES-256 encrypted**
- Runs with **Docker Compose** (two containers)
- Checked with **195 automated tests**

---

## How it works

```
Browser ──► app (FastAPI, port 8000) ──► Google Gemini
                 │
                 │  JWT token + AES-256-GCM encrypted data
                 ▼
            db-service (FastAPI, port 8001, not open to the outside)
                 │
                 ▼
            SQLite: documents, page embeddings, chat history, feedback
```

1. **Upload:** the app checks the file (PDF, TXT or DOCX, up to 20 MB), saves it and extracts the
   text. For PDFs, every page is also turned into an embedding with `all-MiniLM-L6-v2`
   (Sentence Transformers) and stored in db-service.
2. **Ask:** the text of the chosen document and the recent conversation about it are sent to
   Gemini (`gemini-flash-lite-latest`) with instructions to answer only from the document.
   Questions about the conversation itself ("what did I ask before?") are answered directly
   from the saved history.
3. **Save:** each question and answer is stored in db-service, which keeps the last 6 per
   document, so the history is still there after a restart.

`search_pdf.py` is a command-line version that uses the embeddings for retrieval (RAG): it picks
the 20 pages most similar to the question (cosine similarity) and sends only those to Gemini.

### Security

- **API key → token:** the app sends its `SECURITY_API_KEY` to db-service once. db-service stores
  only the **SHA-256 hash** of that key, compares it in constant time, and returns a **JWT token**
  (HS256) that expires after 2 hours. The app renews it every hour.
- **Encryption:** all data sent between the app and db-service is encrypted with
  **AES-256-GCM**, so wrong or changed data is rejected.
- **SQL injection:** all database queries use placeholders (`?`), never pasted-in text.
- **Not reachable:** in Docker, db-service has no open port; only the app can talk to it.
- **No secrets in git:** keys live in `.env` files, which are never uploaded (see `.gitignore`).

---

## Project files

| File / folder | What it does |
|---|---|
| `app.py` | Web server: pages, upload, chat, history and feedback API |
| `embedding.py` | Turns each PDF page into an embedding and registers it in db-service |
| `search_pdf.py` | Command-line chat that finds the most relevant pages with embeddings (RAG) |
| `db_client.py` | Talks to db-service: gets the token, encrypts requests, decrypts replies |
| `crypto_utils.py` | AES-256-GCM encrypt / decrypt (same file in both services) |
| `templates/` | `index.html` (Chat page), `documents.html` (Documents page) |
| `static/` | `chat.js`, `app.js` (page logic), `style.css` |
| `run_tests.py` | Automatic tester (see below) |
| `Dockerfile`, `docker-compose.yml` | Run both services with Docker |
| `.env.example` | Which keys the app needs (copy to `.env`) |
| **`db-service/`** | **The database service** |
| `db-service/service.py` | API: `/token`, `/history/get`, `/history/save`, `/documents/register`, `/documents/list`, `/documents/embeddings`, `/feedback/save` |
| `db-service/db.py`, `db-service/sql.py` | SQLite connection, tables and queries |
| `db-service/.env.example` | Which keys db-service needs (copy to `db-service/.env`) |

---

## Setup

### 1. Keys

Make two `.env` files from the examples:

| File | Key | What to put |
|---|---|---|
| `.env` | `GEMINI_API_KEY` | Your key from Google AI Studio |
| `.env` | `SECURITY_API_KEY` | Any long random string |
| `.env` and `db-service/.env` | `ENCRYPTION_KEY` | 32 random bytes in base64, **the same in both** |
| `db-service/.env` | `SECURITY_API_KEY_HASH` | The SHA-256 hash of `SECURITY_API_KEY` |
| `db-service/.env` | `TOKEN_SECRET_KEY` | Another random string |

Commands to make these values:

```
python -c "import secrets; print(secrets.token_urlsafe(32))"
python -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
python -c "import hashlib; print(hashlib.sha256(b'YOUR_SECURITY_API_KEY').hexdigest())"
python -c "import secrets; print(secrets.token_hex(32))"
```

(1: security API key, 2: encryption key, 3: hash of the security API key, 4: token secret)

### 2. Run with Docker (recommended)

Create an empty document list once (Docker needs the file to exist):

```
python -c "open('documents.json', 'w').write('[]')"
```

Then:

```
docker compose up -d --build
```

Open **http://localhost:8000**. Stop with `docker compose down`.

### 3. Run without Docker

Two terminals:

```
cd db-service
pip install -r requirements.txt
uvicorn service:app --port 8001
```

```
pip install -r requirements.txt
uvicorn app:app --port 8000
```

Open **http://localhost:8000**.

---

## Tests

`run_tests.py` asks the running chatbot 195 questions on four test documents (Python basics,
the Solar System, a company handbook, healthy living) and checks every answer automatically.
Put the four PDFs in a `test_pdfs/` folder next to `run_tests.py` (they are not included here).

```
python run_tests.py                    # all tests
python run_tests.py --only security    # one category
python run_tests.py --regrade          # re-check saved results without asking again
```

| Category | Tests | What is checked | Result |
|---|---|---|---|
| Direct facts | 120 | The right fact from the right document | 120 / 120 |
| Not in the document | 15 | Says "not in the document" instead of guessing | 15 / 15 |
| Wrong document | 10 | Does not answer from another document | 10 / 10 |
| Calculations | 10 | Simple sums with numbers from the document | 10 / 10 |
| Summaries and lists | 8 | Complete lists (+ 3 summaries read by hand) | 5 / 5 + 3 reviewed |
| Typos and Roman Urdu | 7 | "hu created pyton?", "Annual leave kitni milti hai?" | 7 / 7 |
| Conversation history | 5 | "What did I ask before?", "and what did you answer?" | 5 / 5 |
| Security | 10 | SQL injection, prompt injection, asking for keys: no crash, no secret leaked | 10 / 10 |
| Edge cases | 10 | Empty question, no document, emoji, Urdu script, wrong file type | 10 / 10 |
| **Total** | **195** | | **192 / 192 automatic + 3 reviewed** |

---

## Notes

- Answers come from an AI model, so check important answers against the document.
- Uploaded files, `documents.json` and the database stay on your computer and are not part of
  this repository.
