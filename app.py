from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from google import genai
from pypdf import PdfReader
from docx import Document
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from embedding import process_pdf
import json
import os
from dotenv import load_dotenv
load_dotenv()
import db_client
app = FastAPI()
# Project folders
BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
UPLOAD_DIR = BASE_DIR / "uploads"
MANIFEST_FILE = BASE_DIR / "documents.json"

UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

app.mount(
    "/static",
    StaticFiles(directory=str(STATIC_DIR)),
    name="static"
)
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
# Read and save document records
def read_document_list():
    if not MANIFEST_FILE.exists():
        return []

    try:
        return json.loads(
            MANIFEST_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return []


def save_document_list(documents):
    MANIFEST_FILE.write_text(
        json.dumps(documents, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
# Extract text from documents
def extract_text(file_path: Path) -> str:
    extension = file_path.suffix.lower()

    if extension == ".pdf":
        reader = PdfReader(str(file_path))
        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    if extension == ".txt":
        return file_path.read_text(
            encoding="utf-8",
            errors="replace"
        )

    if extension == ".docx":
        document = Document(str(file_path))
        return "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

    return ""
# Homepage

@app.get("/", response_class=HTMLResponse)
def home():
    index_file = TEMPLATE_DIR / "index.html"

    if not index_file.exists():
        raise HTTPException(
            status_code=500,
            detail="index.html was not found."
        )

    return index_file.read_text(encoding="utf-8")

@app.get("/documents", response_class=HTMLResponse)
def documents_page():
    page = TEMPLATE_DIR / "documents.html"
    if not page.exists():
        raise HTTPException(
            status_code=500,
            detail="documents.html was not found."
        )

    return page.read_text(encoding="utf-8")
# Get uploaded documents

@app.get("/api/documents")
def get_documents():
    documents = read_document_list()

    # Return only information needed by the frontend.
    return {
        "documents": [
            {
                "id": doc["id"],
                "filename": doc["filename"],
                "size_bytes": doc["size_bytes"],
                "uploaded_at": doc["uploaded_at"]
            }
            for doc in documents
        ]
    }
# Upload documents

@app.post("/api/upload")
async def upload_documents(files: list[UploadFile] = File(...)):
    if not files:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one file."
        )

    documents = read_document_list()
    uploaded = []

    for file in files:
        original_name = Path(file.filename or "").name
        extension = Path(original_name).suffix.lower()

        if not original_name or extension not in ALLOWED_EXTENSIONS:
            await file.close()
            raise HTTPException(
                status_code=400,
                detail="Only PDF, TXT and DOCX files are allowed."
            )

        content = await file.read()
        await file.close()

        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"{original_name} exceeds the 20 MB limit."
            )

        if not content:
            raise HTTPException(
                status_code=400,
                detail=f"{original_name} is empty."
            )

        stored_name = f"{uuid4().hex}{extension}"
        text_name = f"{uuid4().hex}.extracted.txt"

        destination = UPLOAD_DIR / stored_name
        text_destination = UPLOAD_DIR / text_name

        try:
            destination.write_bytes(content)

            extracted_text = extract_text(destination)

            text_destination.write_text(
                extracted_text,
                encoding="utf-8"
            )
            if extension == ".pdf":
                process_pdf(str(destination))

        except Exception as e:
            print("UPLOAD ERROR:", repr(e))
            destination.unlink(missing_ok=True)
            text_destination.unlink(missing_ok=True)

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Could not read {original_name}:{e} "
                    "Check that the file is valid."
                )
            )

        document_info = {
            "id": uuid4().hex,
            "filename": original_name,
            "size_bytes": len(content),
            "uploaded_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "stored_name": stored_name,
            "text_name": text_name
        }

        documents.append(document_info)

        uploaded.append({
            "id": document_info["id"],
            "filename": original_name,
            "size_bytes": len(content),
            "uploaded_at": document_info["uploaded_at"]
        })

    save_document_list(documents)

    return {
        "message": "Documents uploaded successfully!",
        "files": uploaded
    }
# Chat request structure

class ChatRequest(BaseModel):
    question: str
    selected_document_ids: list[str]
class FeedbackRequest(BaseModel):
    document_id: str
    question: str
    answer: str
    rating: int
    comment: str = ""


@app.post("/api/feedback")
def save_feedback(request: FeedbackRequest):
    if request.rating not in (1, -1):
        raise HTTPException(status_code=400, detail="Invalid rating.")

    documents = read_document_list()
    doc = next((d for d in documents if d["id"] == request.document_id), None)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    db_client.save_feedback(
        str(UPLOAD_DIR / doc["stored_name"]),
        request.question.strip(),
        request.answer,
        request.rating,
        request.comment.strip()[:500],
    )
    return {"message": "Thanks for your feedback!"}


@app.post("/api/chat")
async def chat_with_documents(request: ChatRequest):

    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Please enter a question."
        )

    requested_ids = set(request.selected_document_ids)

    if not requested_ids:
        raise HTTPException(
            status_code=400,
            detail="Please select at least one document."
        )

    documents = read_document_list()

    # Find only the documents selected by the user.
    selected_documents = [
        doc for doc in documents
        if doc.get("id") in requested_ids
    ]

    found_ids = {
        doc["id"] for doc in selected_documents
    }

    if found_ids != requested_ids:
        raise HTTPException(
            status_code=400,
            detail="One or more selected documents were not found."
        )

    context_parts = []

    for doc in selected_documents:
        text_path = UPLOAD_DIR / doc["text_name"]

        if not text_path.exists():
            continue

        text = text_path.read_text(encoding="utf-8")

        if text.strip():
            context_parts.append(
                f"Document: {doc['filename']}\n{text}"
            )

    context = "\n\n".join(context_parts)
    print("Selected documents:", len(selected_documents))
    print("Context length:", len(context))
    print("Context preview:", context[:1000])
    history_parts = []
    history_pairs = []

    for doc in selected_documents:
        doc_name = str(UPLOAD_DIR / doc["stored_name"])
        chats = db_client.get_history(doc_name)
        for old_question, old_answer in reversed(chats):
            history_pairs.append((old_question, old_answer))
            history_parts.append(
                f"Previous question: {old_question}\n"
                f"Previous answer: {old_answer}"
            )

    history_text = "\n".join(history_parts)
    
    question_lower = question.lower().strip()
    history_answer = None

    # Identify questions that ask about conversation history.
    history_meta_phrases = (
        "what did i ask",
        "what did i say",
        "what did you answer",
        "what did you ans",
        "and before that",
        "before that",
        "tell me all the questions",
        "list all the questions",
    )

    is_history_question = any(
        phrase in question_lower
        for phrase in history_meta_phrases
    )

    if is_history_question and history_pairs:
        # Include all questions currently available in history.
        if (
            "all the questions" in question_lower
            or "list all the questions" in question_lower
        ):
            history_answer = "Your recent questions:\n" + "\n".join(
                f"{i}. {q}"
                for i, (q, a) in enumerate(history_pairs, start=1)
            )

        else:
            # Ignore history-related questions when finding
            # the earlier topic the user is referring to.
            content_pairs = [
                (q, a) for q, a in history_pairs
                if not any(
                    phrase in q.lower()
                    for phrase in history_meta_phrases
                )
            ]

            if content_pairs:
                if (
                    "before that" in question_lower
                    or "and before that" in question_lower
                ):
                    target = content_pairs[-2] if len(content_pairs) >= 2 else None

                elif (
                    "what did you answer" in question_lower
                    or "what did you ans" in question_lower
                ):
                    target = content_pairs[-1]

                else:
                    target = content_pairs[-1]

                if target:
                    old_q, old_a = target
                    history_answer = (
                        f"Previous question: {old_q}\n"
                        f"Previous answer: {old_a}"
                    )
                else:
                    history_answer = "There is no earlier question available."
            else:
                history_answer = "There are no earlier topic questions available."


    if not context.strip():
        raise HTTPException(
            status_code=400,
            detail=(
                "No readable text found in the selected documents."
            )
        )
    prompt = (
    "You are a helpful document chatbot.\n"
    "Answer questions using the selected document and conversation history.\n"
    "Use history only when needed to understand the current question.\n"
    "Do not dump or summarize the entire conversation.\n"
    "If the user asks 'what did I ask previously', identify only "
    "the immediately previous user question and provide its matching answer.\n"
    "If the user asks 'and what did you answer', identify the answer "
    "paired with the relevant earlier question in the conversation history. "
    "Do not return an answer that merely describes the conversation. "
     "Return the original answer itself.\n"
    "Never mix up a question with an answer.\n\n"

    f"Conversation history:\n{history_text}\n\n"
    f"Selected document content:\n{context}\n\n"
    f"Current question: {question}\n\n"
    "Answer the current question directly and concisely. "
    "Never say phrases like 'based on the selected document', "
    "'according to the document' or 'the document states'. "
    "Just give the answer itself."
)

    try:
        
        if history_answer is not None:
            answer = history_answer
        else:
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
    )
            answer = response.text

        if not answer:
            answer = "The AI did not return a text answer."
        for doc in selected_documents:
            db_client.save_chat(
                str(UPLOAD_DIR / doc["stored_name"]), question, answer
            )
        return {"answer": answer}
    
    except Exception as error:
        print("Gemini error:", error)

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not get an answer from Gemini. "
                "Check your API key and server terminal."
            )
        )
@app.get("/api/history/{document_id}")
def get_chat_history(document_id: str):
    documents = read_document_list()

    doc = next(
        (d for d in documents if d["id"] == document_id),
        None
    )

    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found."
        )
    rows = db_client.get_history(str(UPLOAD_DIR / doc["stored_name"]))
    return {"history": [{"question": q, "answer": a} for q, a in reversed(rows)]}