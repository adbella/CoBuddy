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
            # 채팅이 가능한 모델만 필터링
            chat_models = [
                m['name'].replace('models/', '') 
                for m in models 
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            
            if not chat_models: return "gemini-pro"
            
            # 우선순위: 1.5-flash > 1.5-pro > 1.0-pro
            for m in chat_models:
                if '1.5-flash' in m: return m
            for m in chat_models:
                if '1.5-pro' in m: return m
            return chat_models[0]
    except:
        pass
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
    except Exception as e:
        return f"❌ 시스템 오류: {e}"

def ask_ai_stream(prompt, user_key=None):
    api_key = user_key if user_key else st.secrets.get("GOOGLE_API_KEY")
    if not api_key:
        yield "⚠️ API 키가 설정되지 않았습니다."
        return

    model_name = get_best_available_model(api_key)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}&alt=sse"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(url, headers=headers, json=data, stream=True)
        
        # 🌟 429 에러(할당량 초과) 감지 로직 추가
        if response.status_code == 429:
            st.session_state.api_exhausted = True # 할당량 소진 상태 기록
            yield f"❌ {st.session_state.get('language_error_msg', '할당량 초과')}" # 에러 메시지 반환
            return

        for line in response.iter_lines():
            # ... (기존 스트리밍 파싱 로직 동일) ...
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    try:
                        json_str = decoded_line[6:]
                        if json_str.strip() == '[DONE]': break
                        chunk = json.loads(json_str)
                        text_chunk = chunk['candidates'][0]['content']['parts'][0]['text']
                        yield text_chunk
                    except: continue
    except Exception as e:
        yield f"❌ 스트리밍 오류: {e}"

# --- 데이터 수집 함수 ---
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
# 🌟 중요: target_lang 파라미터 추가 🌟
def search_all_platforms(message, user_key=None, target_lang="Korean"):
    """검색은 먼저 수행하고, 결과 요약은 스트리밍으로 반환"""
    query = message.replace("추천", "").replace("찾아줘", "").replace("검색", "").strip()
    if not query: query = "programming"

    # 1. 데이터 수집 (Blocking)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [
            executor.submit(get_github_data, query),
            executor.submit(get_hf_data, query)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    all_raw_data = "\n\n".join([r for r in results if r])
    
    prompt = f"""
    [검색 데이터]
    {all_raw_data}
    
    위 데이터를 바탕으로 '{message}'에 대해 답변해줘.
    반드시 **{target_lang} (언어)**로, 표 형식을 사용하여 5개에서 최대 10개까지 관련있는 것을 정리해서 난이도별로 보여줘.
    제목과 내용을 100자 이내로 요약해서 알기쉽게 설명하고 링크는 클릭할 수 있게 해줘.
    마지막엔 '오늘도 당신의 성장을 코버디가 응원해요! 🔥'라고 말해줘.
    """
    
    # 2. 요약 결과는 스트리밍 함수 반환
    return ask_ai_stream(prompt, user_key)