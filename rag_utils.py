import streamlit as st
import tempfile
import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

def process_pdf(uploaded_file):
    """업로드된 PDF를 처리하여 검색기(Retriever)를 반환하는 함수"""
    
    # 1. 임시 파일 생성
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getvalue())
        path = tmp.name
    
    try:
        # 2. PDF 로드
        loader = PyPDFLoader(path)
        docs = loader.load()
        
        # 3. 텍스트 분할
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = splitter.split_documents(docs)
        
        # 4. 로컬 임베딩 모델 설정
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        # 5. 벡터 DB 생성 및 검색기 반환
        vector_db = FAISS.from_documents(splits, embeddings)
        return vector_db.as_retriever()
    
    except Exception as e:
        st.error(f"PDF 분석 중 에러가 발생했습니다: {e}")
        return None
        
    finally:
        # 6. 사용이 끝난 임시 파일 삭제 (이 부분이 수정되었습니다)
        if os.path.exists(path):
            os.remove(path)