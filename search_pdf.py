from sentence_transformers import SentenceTransformer
from google import genai
import numpy as np
import db_client
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client=genai.Client(api_key=api_key)
model=SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
#get all docs
documents=db_client.list_documents()
if not documents:
    print("no pdf found. run embedding.py first")
    raise SystemExit
print("\n AVALIABLE PDFs:")
for doc_id,doc_name in documents:
    print(f"{doc_id}:{doc_name}")

#select a pdf
try:
    selected_id=int(input("\n enter pdf id:"))
except ValueError:
    print("invalid pdf id")
    raise SystemExit
if not any(doc_id==selected_id for doc_id,name in documents):
    print("invalid pdf id")
    raise SystemExit

#get embedding of pdf
pages=db_client.get_embeddings(selected_id)
if not pages:
    print("no embedding found for this pdf")
    raise SystemExit

#question
while True:
    question=input("\n Ask a question(or type exit):").strip()
    if question.lower()=="exit":
        break
    question_embedding=model.encode(question)
    #score rows
    score_pages=[]
    for text,embedding_bytes in pages:
        if not text or not embedding_bytes:
            continue
        page_embedding=np.frombuffer(embedding_bytes,dtype=np.float32)
        #high score close meaning
        score=np.dot(question_embedding,page_embedding)/(np.linalg.norm(question_embedding)*np.linalg.norm(page_embedding))
        score_pages.append((score,text))
    score_pages.sort(reverse=True)
    top_pages=score_pages[:20]
    #join top pages into context
    context=""
    for score, text in top_pages:
        context=context+text+"\n\n"
    print("Context length:", len(context))
    print("Context preview:", context[:1000])
    prompt=(
           "Answer the user's question using only the selected "
        "document content provided below. "
        "Do not use information from any other document. "
        "Do not invent facts. If the answer is not present "
        "in the document content, say you could not find it.\n\n"
        f"Selected document content:\n{context}\n\n"
        f"Current question: {question}"
    )
    prompt=prompt+context+"\nQuestion:" + question
    response=client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt,
    )     
    print("\nBot:",response.text)
