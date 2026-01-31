import streamlit as st
import tempfile
import os

# 임포트 에러를 방지하기 위해 함수 내부가 아닌 상단에 배치
try:
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_community.vectorstores import FAISS
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError as e:
    st.error(f"라이브러리 로드 실패: {e}. requirements.txt를 확인해주세요.")

def process_pdf(uploaded_file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.getvalue())
        path = tmp.name
    
    try:
        loader = PyPDFLoader(path)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        splits = splitter.split_documents(docs)
        
        # 로컬 모델 사용
        embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        vector_db = FAISS.from_documents(splits, embeddings)
        return vector_db.as_retriever()
    
    except Exception as e:
        st.error(f"PDF 분석 중 에러: {e}")
        return None
    finally:
        if os.path.exists(path):