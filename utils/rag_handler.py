import os
import json
from typing import Dict, Any, List
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import groq

class LiteratureRAGHandler:
    def __init__(self, corpus_dir: str, groq_api_key: str = None):
        self.corpus_dir = corpus_dir
        self.api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        self.vector_store = None
        self._init_vector_store()

    def _init_vector_store(self):
        """Builds in-memory FAISS index from corpus files."""
        if not os.path.exists(self.corpus_dir):
            return
        
        loader = DirectoryLoader(self.corpus_dir, glob="**/*.txt", loader_cls=TextLoader)
        docs = loader.load()
        if not docs:
            return

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = text_splitter.split_documents(docs)

        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        self.vector_store = FAISS.from_documents(splits, embeddings)

    def analyze_compound(self, compound_id: str) -> Dict[str, Any]:
        """Queries RAG system for compound contextual literature."""
        default_payload = {
            "compound_id": compound_id,
            "medical_uses": "No natural product literature hit found.",
            "dosage_safety": "Unspecified.",
            "antiviral_findings": "No specific evidence recorded in database."
        }

        if not self.vector_store or not self.api_key:
            return default_payload

        docs = self.vector_store.similarity_search(compound_id, k=3)
        if not docs:
            return default_payload

        context = "\n---\n".join([d.page_content for d in docs])
        
        client = groq.Groq(api_key=self.api_key)
        prompt = f"""
        You are an expert computational chemist. Analyze the following context for compound {compound_id}.
        
        Context:
        {context}

        Return ONLY a JSON object with key fields:
        "medical_uses", "dosage_safety", "antiviral_findings".
        """
        
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(response.choices[0].message.content)
            data["compound_id"] = compound_id
            return data
        except Exception:
            return default_payload