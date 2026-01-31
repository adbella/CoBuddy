import streamlit as st
import requests
import concurrent.futures
from langchain_google_genai import ChatGoogleGenerativeAI

def ask_ai(prompt, user_key=None):
    # 1. API 키 설정 (사용자 입력 키 -> Secrets 키 순서)
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    
    if not api_key:
        return "⚠️ API 키가 설정되지 않았습니다. 사이드바에서 키를 입력하거나 관리자 설정을 확인하세요."
    
    try:
        # 2. 모델 설정 (gemini-1.5-flash 사용)
        # 에러가 계속나면 "gemini-1.5-flash-latest"로 이름을 바꿔보세요.
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", 
            google_api_key=api_key,
            temperature=0.7,
            convert_system_message_to_human=True # 시스템 메시지 호환성 설정
        )
        
        # 3. 답변 생성
        response = llm.invoke(prompt)
        return response.content
        
    except Exception as e:
        # 상세 에러 메시지 출력 (디버깅용)
        return f"❌ AI 에러 발생: {str(e)}"

def get_github_data(query):
    """GitHub에서 관련 프로젝트 검색 (원본 로직 유지)"""
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars"
        res = requests.get(url, timeout=5).json()
        items = res.get('items', [])[:2]
        if not items:
            return ""
        return "\n".join([f"- GitHub 추천: {i['name']} ({i['html_url']})\n  설명: {i['description']}" for i in items])
    except:
        return ""

def search_all(message, user_key=None):
    """멀티 플랫폼 검색 및 AI 요약"""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # 현재는 GitHub만 포함되어 있지만, 필요시 다른 함수도 추가 가능
        futures = [executor.submit(get_github_data, message)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    raw_context = "\n".join([r for r in results if r])
    
    if not raw_context:
        prompt = f"다음 질문에 대해 친절하게 답변해줘: {message}"
    else:
        prompt = f"다음 검색 데이터를 바탕으로 초보 개발자에게 프로젝트를 추천해줘:\n{raw_context}\n\n질문: {message}"
        
    return ask_ai(prompt, user_key)