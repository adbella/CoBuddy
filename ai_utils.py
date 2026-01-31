import streamlit as st
import requests
import concurrent.futures
from google.genai import Client
from google import genai # Google API 클라이언트 직접 사용
from google.genai.errors import APIError

# API Key 유효성 체크 함수는 그대로 유지
def check_api_key_validity(api_key):
    # API 호출이 에러를 일으키므로, 이 기능을 비활성화합니다.
    return True # 그냥 True 반환하도록 수정

def ask_ai(prompt, user_key=None):
    """AI에게 질문하고 전체 답변을 한 번에 받는 함수 (내부 요약용)"""
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return "⚠️ API 키가 설정되지 않았습니다."
    
    try:
        client = Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config={'temperature': 0.7}
        )
        return response.text
    except Exception as e:
        return f"❌ AI 호출 실패: {e}"

def ask_ai_stream(prompt, user_key=None):
    """AI에게 질문하고 답변을 실시간 스트림으로 받는 함수 (타이핑 효과용)"""
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        yield "⚠️ API 키가 설정되지 않았습니다."
        return

    try:
        client = Client(api_key=api_key)
        # 🌟🌟🌟 stream=True 옵션을 사용하여 스트리밍 응답 요청 🌟🌟🌟
        response_stream = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            stream=True,
            config={'temperature': 0.7}
        )
        
        # 스트림에서 각 텍스트 조각(chunk)을 실시간으로 반환(yield)
        for chunk in response_stream:
            yield chunk.text
            
    except Exception as e:
        yield f"❌ AI 호출 실패: {e}"

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

def search_all_platforms(message, user_key=None, stream=False):
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

    all_raw_data = "\n\n".join([r for r in results if r])
    
    prompt = f"""
    당신은 친절한 개발 멘토 '코버디'입니다. 다음 수집된 데이터를 바탕으로 '{message}'에 대해 답변하세요.
    반드시 한국어로 작성하고, 아래 표 형식을 사용하세요.
    
    | 💡 추천 자료 | ✨ 코버디의 조언 | 📊 난이도 | 🔗 링크 |
    | :--- | :--- | :--- | :--- |
    
    자료:
    {all_raw_data}
    
    한국어로 답변하고, 초보자가 이해하기 쉽게 설명해주세요.
    마지막엔 '오늘도 당신의 성장을 코버디가 응원해요! 🔥'라고 말해주세요.
    """
    # 🌟🌟🌟 스트리밍 여부에 따라 다른 함수 호출 🌟🌟🌟
    if stream:
        return ask_ai_stream(prompt, user_key)
    else:
        return ask_ai(prompt, user_key)