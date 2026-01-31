import streamlit as st
import requests
import concurrent.futures
from langchain_google_genai import ChatGoogleGenerativeAI

def ask_ai(prompt, user_key=None):
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return "⚠️ API 키가 설정되지 않았습니다."
    
    # 404 에러 방지를 위한 안전한 모델 경로
    try:
        llm = ChatGoogleGenerativeAI(
            model="models/gemini-1.5-flash", 
            google_api_key=api_key,
            temperature=0.7
        )
        return llm.invoke(prompt).content
    except Exception as e:
        return f"❌ AI 호출 실패: {e}"

# --- 플랫폼별 데이터 수집 함수들 ---

def get_github_data(query):
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc"
        res = requests.get(url, timeout=5).json()
        items = res.get('items', [])[:3]
        return "=== GitHub 추천 ===\n" + "\n".join([f"- {i['name']}: {i['html_url']}\n  ({i['description']})" for i in items])
    except: return ""

def get_hf_data(query):
    try:
        # 모델 라이브러리 검색
        url = f"https://huggingface.co/api/models?search={query}&sort=downloads&direction=-1&limit=3"
        res = requests.get(url, timeout=5).json()
        return "=== HuggingFace 인기 모델 ===\n" + "\n".join([f"- {m['modelId']}: https://huggingface.co/{m['modelId']}" for m in res])
    except: return ""

def get_reddit_data(query):
    try:
        # Reddit의 개발자 커뮤니티 게시글 검색
        headers = {'User-Agent': 'CoBuddy/1.0'}
        url = f"https://www.reddit.com/r/learnprogramming/search.json?q={query}&sort=relevance&t=month&limit=3"
        res = requests.get(url, headers=headers, timeout=5).json()
        posts = res.get('data', {}).get('children', [])
        return "=== Reddit 토론 ===\n" + "\n".join([f"- {p['data']['title']}: https://reddit.com{p['data']['permalink']}" for p in posts])
    except: return ""

def get_devto_data(query):
    try:
        # Dev.to 기술 블로그 검색
        url = f"https://dev.to/api/articles?tag={query}&per_page=3&top=7"
        res = requests.get(url, timeout=5).json()
        return "=== Dev.to 기술 아티클 ===\n" + "\n".join([f"- {a['title']}: {a['url']}" for a in res])
    except: return ""

# --- 통합 검색 및 요약 함수 ---

# ... (앞부분 생략)

def search_all_platforms(message, user_key=None):
    query = message.replace("추천", "").replace("찾아줘", "").replace("검색", "").strip()
    if not query: query = "new programming projects"

    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(get_github_data, query),
            executor.submit(get_hf_data, query),
            executor.submit(get_reddit_data, query),
            executor.submit(get_devto_data, query)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    raw_data = "\n\n".join([r for r in results if r])
    
    prompt = f"""
    당신은 친절한 개발 멘토 '코버디'입니다. 다음 수집된 데이터를 바탕으로 사용자의 질문 '{message}'에 대해 답변하세요.
    반드시 다음 마크다운 표 형식을 사용하여 가독성 있게 작성하세요.
    
    | 💡 추천 항목 | ✨ 상세 설명 및 멘토의 조언 | 📊 난이도 | 🔗 바로가기 |
    | :--- | :--- | :--- | :--- |
    
    데이터:
    {raw_data}
    
    한국어로 답변하고, 초보자가 이해하기 쉽게 설명해주세요.
    마지막엔 '오늘도 당신의 성장을 코버디가 응원해요! 🔥'라고 말해주세요.
    """
    return ask_ai(prompt, user_key)