import os
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
import core.src.config as config

_local_db = None

def get_vector_store():
    """Initializes and returns the in-memory FAISS vector store database from './index/'."""
    global _local_db
    if _local_db is None:
        index_dir = "index"
        if not os.path.exists(index_dir) or not os.listdir(index_dir):
            raise FileNotFoundError("Error: Compiled vector index files (index.faiss/index.pkl) not found in './index/'. Please run the builder first.")
        
        # Load local FAISS index using Google GenAI Embeddings
        embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        _local_db = FAISS.load_local(index_dir, embeddings, allow_dangerous_deserialization=True)
    return _local_db

def query_knowledge_base(query: str) -> str:
    """Queries the local FAISS database for matching context blocks."""
    db = get_vector_store()
    docs = db.similarity_search(query, k=3)
    return "\n\n".join([doc.page_content for doc in docs])
