import streamlit as st
import db_manager as db
import ai_utils as ai
import rag_utils as rag
import urllib.parse
import requests
from google.genai.errors import APIError

# 1. 페이지 설정
st.set_page_config(
    page_title="코버디: 초보 개발자의 성장 단짝", 
    page_icon="🐣", 
    layout="wide"
)

# 2. 커스텀 CSS (부드러운 디자인)
st.markdown("""
    <style>
    .main { background-color: #f9f9fb; }
    .stButton>button { border-radius: 8px; }
    .stTextInput>div>div>input { border-radius: 8px; }
    .skill-card { 
        padding: 10px; border-radius: 10px; background-color: white; 
        border: 1px solid #eee; margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# 3. DB 및 세션 초기화
db.init_db()
if "user_id" not in st.session_state: st.session_state.user_id = None
if "messages" not in st.session_state: st.session_state.messages = []


# 4. 구글 로그인 콜백
if "code" in st.query_params and st.session_state.user_id is None:
    code = st.query_params["code"]
    try:
        # ... (구글 로그인 처리 로직 유지) ...
        conf = st.secrets["google_oauth"]
        token_res = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": conf["client_id"], "client_secret": conf["client_secret"],
            "redirect_uri": conf["redirect_uri"], "grant_type": "authorization_code"
        }).json()
        access_token = token_res.get("access_token")
        user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"}).json()
        if user_info.get("email"):
            success, uid = db.get_or_create_google_user(user_info["email"], user_info.get("name", ""))
            st.session_state.user_id = uid
            st.session_state.user_nick = user_info.get("name", user_info["email"].split('@')[0])
            st.query_params.clear()
            st.rerun()
    except: pass


# 5. 로그인 전 화면 (가장 먼저 실행)
if not st.session_state.user_id:
    st.markdown("<h1 style='text-align: center;'>🐣 코버디</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>코딩 공부가 막막할 때, 당신의 곁을 지키는 성장 단짝</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2, tab3 = st.tabs(["🔒 로그인", "✨ 회원가입", "🚀 구글로 시작"])
        # ... (로그인/회원가입/구글 탭 로직 유지) ...
        with tab1:
            with st.form("l_form"):
                n = st.text_input("닉네임")
                p = st.text_input("비밀번호", type="password")
                if st.form_submit_button("로그인", use_container_width=True):
                    user = db.authenticate_user(n, p)
                    if user:
                        st.session_state.user_id = user['user_id']
                        st.session_state.user_nick = n
                        st.rerun()
                    else: st.error("정보가 일치하지 않아요.")
        with tab2:
            with st.form("s_form"):
                nn = st.text_input("새 닉네임")
                np = st.text_input("비밀번호 (6자 이상)", type="password")
                if st.form_submit_button("가입하기", use_container_width=True):
                    if len(nn) < 2 or len(np) < 6: st.warning("길이가 부족해요.")
                    else:
                        s, m = db.create_user(nn, np)
                        if s: st.success("가입 완료! 로그인 탭으로 가주세요.")
                        else: st.error(m)
        with tab3:
            if "google_oauth" in st.secrets:
                conf = st.secrets["google_oauth"]
                params = {"response_type": "code", "client_id": conf["client_id"], "redirect_uri": conf["redirect_uri"], "scope": "openid email profile", "prompt": "select_account"}
                url = f"https://accounts.google.com/o/oauth2/auth?{urllib.parse.urlencode(params)}"
                st.link_button("🔵 Google 계정으로 로그인", url, use_container_width=True)
    st.stop()

    # 6. 로그인 후 (전체 사이드바 및 메인 로직)
if st.session_state.user_id: # 로그인 성공 후
    
    # 🌟🌟🌟 사이드바 전체를 하나의 with st.sidebar로 묶습니다. 🌟🌟🌟
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state.user_nick}님 반가워요!")
        
        # AI 설정
        st.markdown("### 🔑 API 설정")
        st.markdown("**:red[키가 없으신가요?]** [**여기**](https://aistudio.google.com/app/apikey)서 만드세요. 👈")
        
        # Secrets의 키를 기본값으로 사용
        default_key = st.secrets.get("GOOGLE_API_KEY", "")
        
        # 세션 상태 초기화 및 키 값 설정
        if "show_key_input" not in st.session_state: st.session_state.show_key_input = False
        if "user_key_value" not in st.session_state: st.session_state.user_key_value = default_key
            
        effective_key = st.session_state.user_key_value
        user_input_key = None # 🌟🌟🌟 NameError 방지용 초기값 설정 🌟🌟🌟

        # 1. 키 입력창 노출 조건 및 마스킹
        if st.session_state.show_key_input or not effective_key:
            
            masked_key = "********" if effective_key else ""
            
            user_input_key = st.text_input( # 👈 여기서 user_input_key가 정의됨
                "Gemini API Key 입력", 
                type="password", 
                value=masked_key, 
                key="user_gemini_key_input",
                help="여기에 키를 입력하거나 수정하세요."
            )

            # 새 키를 입력했을 때 처리
            if user_input_key and user_input_key != masked_key:
                st.session_state.user_key_value = user_input_key 
                st.session_state.show_key_input = False
                st.rerun()
                
            if effective_key: # 키를 숨길 때 사용할 '취소' 버튼
                if st.button("입력 취소", key="cancel_key_input"):
                    st.session_state.show_key_input = False
                    st.rerun()
        
        # 2. 키가 유효할 때의 표시 및 수정 버튼
        else: 
            st.success("✅ API 키 적용 완료. (AI 기능 사용 가능)")
            st.caption("키는 보안을 위해 숨김 처리되었습니다.")
            
            if st.button("키 수정/변경", key="modify_key_btn"):
                st.session_state.show_key_input = True
                st.rerun()

        # user_key 변수 업데이트 (메인 로직에서 사용할 최종 키)
        if st.session_state.show_key_input and user_input_key and user_input_key != "********":
             user_key = user_input_key # 사용자가 입력 중인 새 키
        else:
             user_key = effective_key # 세션에 저장된 키
        
        st.divider()

        # PDF 업로드 영역 (UI 개선)
        st.markdown("### 📚 스마트 PDF 학습")
        st.info("여기에 공부할 PDF 파일을 올려주세요. 모든 파일이 누적되어 분석됩니다.")
        
        # 세션 상태에 파일 리스트 초기화 및 업로더 로직 (생략: 기존과 동일)
        if "uploaded_file_list" not in st.session_state:
            st.session_state.uploaded_file_list = []
            st.session_state.processed_file_names = set()

        new_uploaded_files = st.file_uploader(
            "파일 업로드 (PDF 전용)", type=["pdf"], key="pdf_uploader", accept_multiple_files=True, label_visibility="collapsed")
        
        if new_uploaded_files: 
            newly_added = []
            for file in new_uploaded_files:
                if file.name not in st.session_state.processed_file_names:
                    newly_added.append(file)
                    st.session_state.processed_file_names.add(file.name)

            if newly_added:
                st.session_state.uploaded_file_list.extend(newly_added)
                with st.spinner(f"코버디가 {len(st.session_state.uploaded_file_list)}개 문서를 통합 분석 중... 📖"):
                    st.session_state.retriever = rag.process_multiple_pdfs(st.session_state.uploaded_file_list)
                    st.success(f"✅ 총 {len(st.session_state.uploaded_file_list)}개 문서 통합 학습 완료!")
                    
            if st.session_state.uploaded_file_list:
                file_names = st.session_state.uploaded_file_list
                st.caption(f"📍 현재 학습 중인 문서: {len(file_names)}개")
                
                with st.expander("학습 문서 목록 보기"):
                    for file in file_names:
                        st.write(f"- {file.name}")

        st.divider()

        # 관리자 메뉴
        is_admin = st.session_state.user_nick in ["안종호"] 
        if is_admin:
            st.markdown("### 👑 관리자 메뉴")
            if "show_admin" not in st.session_state: st.session_state.show_admin = False
            st.session_state.show_admin = st.checkbox("관리자 대시보드 보기", key="admin_chk")

        st.divider()
        
        # 로그아웃 버튼
        if st.button("🚪 로그아웃", key="sidebar_logout_btn", use_container_width=True): 
            st.session_state.clear()
            st.rerun()

# --- [메인 화면 영역 수정] ---
if st.session_state.get("show_admin"):
    # 관리자 대시보드 출력 시작
    st.title("📊 관리자 대시보드")
    u_cnt, s_cnt, u_list, s_list = db.get_admin_stats()
    
    col1, col2 = st.columns(2)
    with col1: st.metric("총 가입자 수", f"{u_cnt}명")
    with col2: st.metric("총 등록 스킬", f"{s_cnt}개")
    
    st.write("### 👥 사용자 목록 (구글 로그인 정보 포함)")
    
    # 🌟🌟🌟🌟🌟 사용자 목록 출력 우회 로직 🌟🌟🌟🌟🌟
    if u_list.empty:
        st.info("데이터가 없습니다. 새 사용자를 등록해주세요.")
    else:
        st.dataframe(u_list, use_container_width=True, hide_index=True)

    st.write("### 🛠️ 전체 사용자 스킬 현황")
    
    # 🌟🌟🌟🌟🌟 스킬 현황 출력 우회 로직 🌟🌟🌟🌟🌟
    if s_list.empty:
        st.info("등록된 스킬 데이터가 없습니다. 사용자들이 스킬을 등록하도록 안내해주세요.")
    else:
        st.dataframe(s_list, use_container_width=True, hide_index=True)
    
    if st.button("채팅으로 돌아가기", key="close_admin_chat_btn"):
        st.session_state.show_admin = False
        st.rerun()
    
    st.stop()
# 8. 채팅 UI
if not st.session_state.get("show_admin"):
    
    # 온보딩 가이드 (이 부분이 if 블록 안으로 들어갑니다)
    if not st.session_state.messages:
        st.markdown("""
            ### 👋 반가워요! 코버디와 이렇게 대화해보세요.
            1. **스킬 관리**: `파이썬 5`라고 입력하면 실력을 저장해드려요. `목록`이라고 치면 확인 가능해요!
            2. **실시간 추천**: `자바 프로젝트 추천해줘`라고 하면 GitHub, Reddit 등을 뒤져서 알려드려요.
            3. **문서 학습**: 왼쪽에서 PDF를 올리면 그 내용으로 시험 공부나 질문을 할 수 있어요.
        """)    
    
    st.info("💡 팁: 아래 채팅창에 질문을 입력하거나 '파이썬 5'를 입력해 보세요.")
    
    # 대화 출력
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 입력 처리
    if prompt := st.chat_input("무엇이든 물어보세요!"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # 1. 스킬 목록 (스트리밍 불필요)
            if prompt in ["목록", "조회", "스킬", "내 스킬"]:
                res = db.get_my_skills(st.session_state.user_id)
                st.markdown(res)
                st.session_state.messages.append({"role": "assistant", "content": res})
            # 2. 스킬 저장 (스트리밍 불필요)
            elif len(prompt.split()) == 2 and prompt.split()[1].isdigit():
                s, l = prompt.split()
                db.save_skill(st.session_state.user_id, s, int(l))
                res = f"✅ **{s}** (Level {l}) 저장 완료! 성장하는 모습이 보기 좋아요."
                st.markdown(res)
                st.session_state.messages.append({"role": "assistant", "content": res})
            
            # 3. AI 답변이 필요한 모든 경우 (스트리밍 적용)
            else:
                with st.spinner("코버디가 생각 중... 🐣"):
                    # 추천 검색이든 일반 질문이든 모두 스트리밍으로 처리
                    if any(w in prompt for w in ["추천", "검색", "찾아줘", "자료"]):
                        stream = ai.search_all_platforms(prompt, user_key, stream=True)
                    elif "retriever" in st.session_state and st.session_state.retriever:
                        docs = st.session_state.retriever.invoke(prompt)
                        ctx = "\n".join([d.page_content for d in docs])
                        stream = ai.ask_ai_stream(f"문서 내용:\n{ctx}\n\n질문: {prompt}", user_key)
                    else:
                        stream = ai.ask_ai_stream(prompt, user_key)
                    
                    full_response = st.write_stream(stream)
                    
                    # 전체 응답을 세션에 저장
                    st.session_state.messages.append({"role": "assistant", "content": full_response})