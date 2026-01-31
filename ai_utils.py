import streamlit as st
import google.generativeai as genai
import requests
import concurrent.futures

def check_api_key_validity(api_key):
    """API 키 유효성 확인"""
    if not api_key: return False
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("test")
        return True
    except Exception:
        return False

def ask_ai(prompt, user_key=None):
    """AI에게 질문하기 (표준 라이브러리 사용)"""
    # 키 우선순위: 유저 입력 키 > Secrets 키
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    
    if not api_key:
        return "⚠️ API 키가 설정되지 않았습니다."
    
    try:
        # 라이브러리 설정
        genai.configure(api_key=api_key)
        
        # 모델 설정 (가장 안정적인 gemini-1.5-flash 사용)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 답변 생성
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"❌ AI 호출 실패: {str(e)}"

# --- 플랫폼별 데이터 수집 함수들 (기존 코드 유지) ---

def get_github_data(query):
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc"
        res = requests.get(url, timeout=5).json()
        items = res.get('items', [])[:3]
        return "=== GitHub 추천 ===\n" + "\n".join([f"- {i['name']}: {i['html_url']}\n  ({i['description']})" for i in items])
    except: return ""

def get_hf_data(query):
    try:
        url = f"https://huggingface.co/api/models?search={query}&sort=downloads&direction=-1&limit=3"
        res = requests.get(url, timeout=5).json()
        return "=== HuggingFace 인기 모델 ===\n" + "\n".join([f"- {m['modelId']}: https://huggingface.co/{m['modelId']}" for m in res])
    except: return ""

def get_reddit_data(query):
    try:
        headers = {'User-Agent': 'CoBuddy/1.0'}
        url = f"https://www.reddit.com/r/learnprogramming/search.json?q={query}&sort=relevance&t=month&limit=3"
        res = requests.get(url, headers=headers, timeout=5).json()
        posts = res.get('data', {}).get('children', [])
        return "=== Reddit 토론 ===\n" + "\n".join([f"- {p['data']['title']}: https://reddit.com{p['data']['permalink']}" for p in posts])
    except: return ""

def get_devto_data(query):
    try:
        url = f"https://dev.to/api/articles?tag={query}&per_page=3&top=7"
        res = requests.get(url, timeout=5).json()
        return "=== Dev.to 기술 아티클 ===\n" + "\n".join([f"- {a['title']}: {a['url']}" for a in res])
    except: return ""

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
    
    return ask_ai(prompt, user_key)