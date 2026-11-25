from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
import db_client
import base64
model = SentenceTransformer("all-MiniLM-L6-v2")
def process_pdf(pdf_path):
    reader=PdfReader(pdf_path)
    print('num of pages:',len(reader.pages))
    pages=[]
    for page_number,page in enumerate(reader.pages,start=1):
              text=page.extract_text()
              if text:
                  embedding=model.encode(text)
                  embedding_bytes=embedding.tobytes()
                  print("PAGE",page_number)
                  print("extracted text",repr(text[:300]))
                  print("text length",len(text))
                  print("Embedding size:",len(embedding))
                  pages.append({
                       "text":text,
                       "embedding":base64.b64encode(embedding_bytes).decode(),})
              else:
                  print("PAGE",page_number)
                  print("No text found on this page.")
    db_client.register_document(pdf_path,pages)
    print("PDF embeddings saved successfully")
