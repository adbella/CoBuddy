import streamlit as st
import requests
import concurrent.futures
import json

def get_best_available_model(api_key):
    """사용 가능한 최적의 모델 찾기"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get('models', [])
            chat_models = [m['name'].replace('models/', '') for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
            
            if not chat_models: return "gemini-pro"
            
            # 우선순위: Flash > 1.5 Pro > 1.0 Pro
            for m in chat_models:
                if '1.5-flash' in m: return m
            for m in chat_models:
                if '1.5-pro' in m: return m
            return chat_models[0]
    except: pass
    return "gemini-pro"

def ask_ai(prompt, user_key=None):
    """한 번에 답변 받기 (요약용)"""
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key: return "⚠️ API 키가 없습니다."
    
    model_name = get_best_available_model(api_key)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return f"❌ 오류: {response.text}"
    except Exception as e: return f"❌ 오류: {e}"

def ask_ai_stream(prompt, user_key=None):
    """🌟 실시간 타이핑 효과를 위한 스트리밍 함수 (REST API + SSE) 🌟"""
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        yield "⚠️ API 키가 설정되지 않았습니다."
        return

    model_name = get_best_available_model(api_key)
    
    # URL에 'streamGenerateContent'와 'alt=sse'를 사용하여 스트리밍 요청
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        # stream=True로 연결 유지
        response = requests.post(url, headers=headers, json=data, stream=True)
        
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                # SSE 데이터 형식인 "data: " 로 시작하는 부분만 파싱
                if decoded_line.startswith('data: '):
                    try:
                        json_str = decoded_line[6:] # "data: " 제거
                        if json_str.strip() == '[DONE]': break
                        
                        chunk = json.loads(json_str)
                        # 텍스트 조각 추출 및 반환
                        text_chunk = chunk['candidates'][0]['content']['parts'][0]['text']
                        yield text_chunk
                    except:
                        continue
    except Exception as e:
        yield f"❌ 스트리밍 오류: {e}"

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
    """검색은 먼저 하고, 결과 요약은 스트리밍으로 반환"""
    query = message.replace("추천", "").replace("찾아줘", "").replace("검색", "").strip()
    if not query: query = "programming"

    # 1. 데이터 수집 (여기는 기다려야 함 - 스피너가 돌아감)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(get_github_data, query),
            executor.submit(get_hf_data, query),
            executor.submit(get_reddit_data, query),
            executor.submit(get_devto_data, query)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    all_raw_data = "\n\n".join([r for r in results if r])
    
    자료:
    {all_raw_data}

    prompt = f"""
    당신은 친절한 개발 멘토 '코버디'입니다. 다음 수집된 데이터를 바탕으로 '{message}'에 대해 답변하세요.
    반드시 한국어로 작성하고, 아래 표 형식을 사용하세요.
    난이도는 색깔별로 표시해주고 링크는 클릭할 수 있게 해주세요.
    
    | 💡 추천 자료 | ✨ 코버디의 조언 | 📊 난이도 | 🔗 링크 |
    | :--- | :--- | :--- | :--- |

    한국어로 답변하고, 초보자가 이해하기 쉽게 설명해주세요.
    마지막엔 '오늘도 당신의 성장을 코버디가 응원해요! 🔥'라고 말해주세요.
    """

    return ask_ai_stream(prompt, user_key)