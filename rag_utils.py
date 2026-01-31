import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings # 변경된 부분
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tempfile
import os

def process_pdf(uploaded_file):
    # PDF를 임시 파일로 저장
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getvalue())
        path = tmp.name
    
    try:
        # 1. PDF 로드 및 텍스트 분할
        loader = PyPDFLoader(path)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = splitter.split_documents(docs)
        
        # 2. 로컬 임베딩 모델 로드 (API 키 불필요, 안정적)
        # 이 모델은 약 80MB 정도로 처음 실행 시 한 번 다운로드됩니다.
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        # 3. 벡터 DB 생성
        vector_db = FAISS.from_documents(splits, embeddings)
        return vector_db.as_retriever()
    
    except Exception as e:
        st.error(f"PDF 처리 중 오류 발생: {e}")
        return None
    finally:
        if os.path.exists(path):
            os.unlink(path)