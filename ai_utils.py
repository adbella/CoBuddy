import streamlit as st
import requests
import concurrent.futures
from langchain_google_genai import ChatGoogleGenerativeAI

def ask_ai(prompt, user_key=None):
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    
    if not api_key:
        return "⚠️ API 키가 설정되지 않았습니다."
    
    # 시도해볼 모델 리스트 (순서대로 시도)
    model_names = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    last_error = ""

    for model_name in model_names:
        try:
            llm = ChatGoogleGenerativeAI(
                model=model_name, 
                google_api_key=api_key,
                temperature=0.7
            )
            response = llm.invoke(prompt)
            return response.content
        except Exception as e:
            last_error = str(e)
            continue # 에러가 나면 다음 모델로 시도
            
    return f"❌ 모든 AI 모델 호출에 실패했습니다.\n최종 에러: {last_error}"

# 이하 get_github_data, search_all 함수는 이전과 동일하게 유지
def get_github_data(query):
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars"
        res = requests.get(url, timeout=5).json()
        items = res.get('items', [])[:2]
        if not items: return ""
        return "\n".join([f"- GitHub 추천: {i['name']} ({i['html_url']})" for i in items])
    except: return ""

def search_all(message, user_key=None):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_github_data, message)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    raw_context = "\n".join([r for r in results if r])
    prompt = f"질문: {message}\n참고 자료: {raw_context}" if raw_context else message
    return ask_ai(prompt, user_key)