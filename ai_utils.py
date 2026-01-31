import streamlit as st
import requests
import json
import concurrent.futures

def get_best_available_model(api_key):
    """
    API 키를 사용하여 현재 사용 가능한 모델 목록을 조회하고,
    가장 성능이 좋은 모델(Flash > Pro 순)을 자동으로 선택합니다.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            
            # 'generateContent' 기능을 지원하는 모델만 필터링
            chat_models = [
                m['name'].replace('models/', '') 
                for m in models 
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            
            if not chat_models:
                return "gemini-pro" # 검색 실패 시 기본값
            
            # 우선순위: 1.5-flash > 1.5-pro > 1.0-pro > 그 외
            for m in chat_models:
                if '1.5-flash' in m: return m
            for m in chat_models:
                if '1.5-pro' in m: return m
            for m in chat_models:
                if '1.0-pro' in m: return m
                
            return chat_models[0] # 아무거나 되는 거 반환
            
    except Exception as e:
        print(f"모델 조회 실패: {e}")
    
    return "gemini-pro" # 에러 발생 시 최후의 수단

def ask_ai(prompt, user_key=None):
    """REST API 직접 호출 (자동 모델 선택)"""
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return "⚠️ API 키가 설정되지 않았습니다."

    # 1. 사용 가능한 최적의 모델 찾기
    model_name = get_best_available_model(api_key)
    
    # 2. API 호출
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            try:
                return result['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError):
                return "❌ AI 응답 해석 실패. (빈 응답)"
        else:
            # 에러 상세 정보 파싱
            err_msg = response.text
            try:
                err_json = response.json()
                err_msg = err_json.get('error', {}).get('message', err_msg)
            except: pass
            return f"❌ AI 호출 에러 ({model_name}): {err_msg}"

    except Exception as e:
        return f"❌ 시스템 오류: {str(e)}"

# --- 플랫폼별 데이터 수집 함수들 (기존 유지) ---
def get_github_data(query):
    try:
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&limit=3"
        res = requests.get(url, timeout=5).json()
        items = res.get('items', [])[:2]
        return "=== GitHub 추천 ===\n" + "\n".join([f"- {i['name']}: {i['html_url']}" for i in items])
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
    if not query: query = "programming"

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