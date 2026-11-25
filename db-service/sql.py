MASTER="""
CREATE TABLE IF NOT EXISTS doc_master(
   doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
   doc_name TEXT UNIQUE
   );
   """
DOC="""
CREATE TABLE IF NOT EXISTS document(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER,
    text TEXT,
    embedding BLOB,
    FOREIGN KEY(doc_id)
         REFERENCES doc_master(doc_id)
);"""
INSERT_DOC="""
INSERT OR IGNORE INTO doc_master(doc_name)
VALUES(?);
"""
GET_DOC="""
SELECT doc_id FROM doc_master
WHERE doc_name=?;
"""
GET_DOCUMENTS="""
SELECT doc_id,doc_name FROM doc_master
"""
DELETE_DOC="""
DELETE FROM document
WHERE doc_id=?;
"""
INSERT_EMBEDDING="""
INSERT INTO document(doc_id,text,embedding)
VALUES(?,?,?);
"""
GET_EMBEDDINGS="""
SELECT text,embedding 
FROM document
WHERE doc_id=?;
"""

CHAT_HISTORY = """
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES doc_master(doc_id)
);
"""

SAVE_CHAT = """
INSERT INTO chat_history (doc_id, question, answer)
VALUES (?, ?, ?);
"""

GET_RECENT_CHATS = """
SELECT question, answer
FROM chat_history
WHERE doc_id = ?
ORDER BY id DESC
LIMIT 6;
"""

DELETE_OLD_CHATS = """
DELETE FROM chat_history
WHERE doc_id = ?
AND id NOT IN (
    SELECT id FROM chat_history
    WHERE doc_id = ?
    ORDER BY id DESC
    LIMIT 6
);
"""
FEEDBACK = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(doc_id) REFERENCES doc_master(doc_id)
);
"""

SAVE_FEEDBACK = """
INSERT INTO feedback (doc_id, question, answer, rating, comment)
VALUES (?, ?, ?, ?, ?);
"""

GET_FEEDBACK = """
SELECT id, question, answer, rating, comment, created_at
FROM feedback
ORDER BY id DESC;
"""
