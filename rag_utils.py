import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tempfile
import os

def process_pdf(uploaded_file):
    api_key = st.secrets.get("GOOGLE_API_KEY")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getvalue())
        path = tmp.name
    
    loader = PyPDFLoader(path)
    docs = loader.load()
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    splits = splitter.split_documents(docs)
    
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
    vector_db = FAISS.from_documents(splits, embeddings)
    os.unlink(path)
    return vector_db.as_retriever()