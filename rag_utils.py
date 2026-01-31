import streamlit as st
import tempfile
import os

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

# 🌟🌟🌟 임베딩 모델 로드는 @st.cache_resource로 유지 🌟🌟🌟
@st.cache_resource
def get_embedding_model():
    """임베딩 모델을 캐시하여 앱 실행 중 한 번만 로드하도록 설정"""
    try:
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
    except Exception as e:
        st.error(f"임베딩 모델 로드 실패: {e}")
        return None

# 🌟🌟🌟 다중 파일 처리를 위한 함수로 변경 🌟🌟🌟
def process_multiple_pdfs(uploaded_files):
    """업로드된 여러 PDF 파일을 처리하여 통합 검색기를 반환하는 함수"""
    
    if not uploaded_files:
        return None
    
    all_splits = []
    temp_paths = []
    
    try:
        embeddings = get_embedding_model()
        if not embeddings: return None

        # 1. 모든 파일을 순회하며 텍스트 추출 및 분할
        for uploaded_file in uploaded_files:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                path = tmp.name
                temp_paths.append(path)
                
            # PDF 로드 및 분할
            loader = PyPDFLoader(path)
            docs = loader.load()
            splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
            all_splits.extend(splitter.split_documents(docs))
        
        # 2. 모든 조각을 통합하여 하나의 벡터 DB 생성
        vector_db = FAISS.from_documents(all_splits, embeddings)
        st.session_state.current_pdf_list = [f.name for f in uploaded_files]
        return vector_db.as_retriever(search_kwargs={"k": 5}) # 검색 개수 5개로 늘림
    
    except Exception as e:
        st.error(f"다중 PDF 분석 중 에러가 발생했습니다: {e}")
        return None
        
    finally:
        # 3. 모든 임시 파일 삭제
        for path in temp_paths:
            if os.path.exists(path):
                os.remove(path)