import streamlit as st
import requests
import concurrent.futures
from langchain_google_genai import ChatGoogleGenerativeAI

def ask_ai(prompt, user_key=None):
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return "⚠️ API 키가 필요합니다."
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=api_key)
        return llm.invoke(prompt).content
    except Exception as e:
        return f"AI 에러: {str(e)}"

def get_github_data(query):
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&limit=3"
        res = requests.get(url, timeout=5).json()
        items = res.get('items', [])[:2]
        return "\n".join([f"- GitHub: {i['name']} ({i['html_url']})" for i in items])
    except: return ""

def search_all(message, user_key=None):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(get_github_data, message)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    raw_context = "\n".join(results)
    prompt = f"다음 데이터를 바탕으로 개발자에게 친절하게 추천해줘:\n{raw_context}\n질문: {message}"
    return ask_ai(prompt, user_key)