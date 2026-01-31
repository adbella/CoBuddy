import streamlit as st
import db_manager as db
import ai_utils as ai
import rag_utils as rag
import urllib.parse
import requests

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

# 세션 상태값 초기화
if "user_id" not in st.session_state: st.session_state.user_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "show_admin" not in st.session_state: st.session_state.show_admin = False
if "uploaded_file_list" not in st.session_state: st.session_state.uploaded_file_list = []
if "processed_file_names" not in st.session_state: st.session_state.processed_file_names = set()
if "show_key_input" not in st.session_state: st.session_state.show_key_input = False
if "user_key_value" not in st.session_state: st.session_state.user_key_value = st.secrets.get("GOOGLE_API_KEY", "")


# 4. 구글 로그인 콜백 처리
if "code" in st.query_params and st.session_state.user_id is None:
    code = st.query_params["code"]
    try:
        if "google_oauth" in st.secrets:
            conf = st.secrets["google_oauth"]
            token_res = requests.post("https://oauth2.googleapis.com/token", data={
                "code": code, "client_id": conf["client_id"], "client_secret": conf["client_secret"],
                "redirect_uri": conf["redirect_uri"], "grant_type": "authorization_code"
            }).json()
            access_token = token_res.get("access_token")
            user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", 
                                     headers={"Authorization": f"Bearer {access_token}"}).json()
            if user_info.get("email"):
                success, uid = db.get_or_create_google_user(user_info["email"], user_info.get("name", ""))
                st.session_state.user_id = uid
                st.session_state.user_nick = user_info.get("name", user_info["email"].split('@')[0])
                st.query_params.clear()
                st.rerun()
    except Exception as e:
        st.error(f"로그인 처리 중 오류: {e}")


# 5. 로그인 전 화면 (가장 먼저 실행)
if not st.session_state.user_id:
    st.markdown("<h1 style='text-align: center;'>🐣 코버디</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>코딩 공부가 막막할 때, 당신의 곁을 지키는 성장 단짝</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2, tab3 = st.tabs(["🔒 로그인", "✨ 회원가입", "🚀 구글로 시작"])
        
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
            else:
                st.info("Secrets 설정이 필요합니다.")
    st.stop()


# 6. 로그인 후 로직 (사이드바 + 메인 화면)
if st.session_state.user_id:
    
    # ---------------------------------------------------------
    # [사이드바] 모든 사이드바 요소는 이 블록 안에 있어야 함
    # ---------------------------------------------------------
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state.user_nick}님 반가워요!")
        
        # --- A. API 키 설정 ---
        st.markdown("### 🔑 API 설정")
        st.markdown("**:red[키가 없으신가요?]** [**여기**](https://aistudio.google.com/app/apikey)서 만드세요. 👈")
        
        effective_key = st.session_state.user_key_value
        
        # 키 입력창 표시 조건: 키가 없거나, 수정 모드일 때
        if st.session_state.show_key_input or not effective_key:
            masked_key = "********" if effective_key else ""
            user_input_key = st.text_input(
                "Gemini API Key 입력", 
                type="password", 
                value=masked_key, 
                key="user_gemini_key_input", 
                help="여기에 키를 입력하거나 수정하세요."
            )
            
            # 새 키 저장
            if user_input_key and user_input_key != masked_key:
                st.session_state.user_key_value = user_input_key 
                st.session_state.show_key_input = False
                st.rerun()
            
            # 취소 버튼 (기존 키가 있을 때만)
            if effective_key:
                if st.button("입력 취소", key="cancel_key_input"):
                    st.session_state.show_key_input = False
                    st.rerun()
        else:
            # 키가 잘 적용된 상태
            st.success("✅ API 키 적용 완료. (AI 기능 사용 가능)")
            st.caption("키는 보안을 위해 숨김 처리되었습니다.")
            if st.button("키 수정/변경", key="modify_key_btn"):
                st.session_state.show_key_input = True
                st.rerun()
        
        # 메인 로직에서 사용할 최종 키
        user_key = effective_key
        
        st.divider()

        # --- B. PDF 업로드 ---
        st.markdown("### 📚 스마트 PDF 학습")
        st.info("여기에 공부할 PDF 파일을 올려주세요. 모든 파일이 누적되어 분석됩니다.")
        
        new_uploaded_files = st.file_uploader(
            "파일 업로드 (PDF 전용)", 
            type=["pdf"], 
            key="pdf_uploader", 
            accept_multiple_files=True, 
            label_visibility="collapsed"
        )
        
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

        # --- C. 관리자 메뉴 ---
        # 본인의 닉네임으로 정확히 수정하세요
        is_admin = st.session_state.user_nick in ["안종호", "관리자"] 
        if is_admin:
            st.markdown("### 👑 관리자 메뉴")
            st.session_state.show_admin = st.checkbox("관리자 대시보드 보기", key="admin_chk", value=st.session_state.show_admin)

        st.divider()
        
        # --- D. 로그아웃 ---
        if st.button("🚪 로그아웃", key="sidebar_logout_btn", use_container_width=True): 
            st.session_state.clear()
            st.rerun()


    # ---------------------------------------------------------
    # [메인 화면 1] 관리자 대시보드 (켜져 있을 때만 표시)
    # ---------------------------------------------------------
    if st.session_state.get("show_admin"):
        st.title("📊 관리자 대시보드")
        
        # DB에서 통계 가져오기
        u_cnt, s_cnt, u_list, s_list = db.get_admin_stats()
        
        col1, col2 = st.columns(2)
        with col1: st.metric("총 가입자 수", f"{u_cnt}명")
        with col2: st.metric("총 등록 스킬", f"{s_cnt}개")
        
        st.write("### 👥 사용자 목록 (구글 로그인 정보 포함)")
        if u_list.empty:
            st.info("데이터가 없습니다.")
        else:
            st.dataframe(u_list, use_container_width=True, hide_index=True)

        st.write("### 🛠️ 전체 사용자 스킬 현황")
        if s_list.empty:
            st.info("등록된 스킬이 없습니다.")
        else:
            st.dataframe(s_list, use_container_width=True, hide_index=True)
        
        if st.button("채팅으로 돌아가기", key="close_admin_chat_btn"):
            st.session_state.show_admin = False
            st.rerun()
        
        # 관리자 화면일 때는 채팅창 숨김
        st.stop() 


    # ---------------------------------------------------------
    # [메인 화면 2] 채팅 UI (관리자 화면이 아닐 때만 표시)
    # ---------------------------------------------------------
    if not st.session_state.messages:
        # 온보딩 가이드
        st.markdown("""
            ### 👋 반가워요! 코버디와 이렇게 대화해보세요.
            1. **스킬 관리**: `파이썬 5`라고 입력하면 실력을 저장해드려요. `목록`이라고 치면 확인 가능해요!
            2. **실시간 추천**: `자바 프로젝트 추천해줘`라고 하면 GitHub, Reddit 등을 뒤져서 알려드려요.
            3. **문서 학습**: 왼쪽에서 PDF를 올리면 그 내용으로 시험 공부나 질문을 할 수 있어요.
        """)    
        st.info("💡 팁: 아래 채팅창에 질문을 입력하거나 '파이썬 5'를 입력해 보세요.")

    # 대화 기록 표시
    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("무엇이든 물어보세요!"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("코버디가 생각 중... 🐣"):
                res = "" 
                
                # 입력값이 문자열인지 안전 확인
                if isinstance(prompt, str):
                    # 1. 스킬 목록 (DB)
                    if prompt in ["목록", "조회", "스킬", "내 스킬"]:
                        res = db.get_my_skills(st.session_state.user_id)
                    
                    # 2. 스킬 저장 (DB)
                    elif len(prompt.split()) == 2 and prompt.split()[1].isdigit():
                        s, l = prompt.split()
                        db.save_skill(st.session_state.user_id, s, int(l))
                        res = f"✅ **{s}** (Level {l}) 저장 완료! 성장하는 모습이 보기 좋아요."
                    
                    # 3. AI 답변 (RAG, 검색, 일반 대화)
                    else:
                        # (A) 검색/추천
                        if any(w in prompt for w in ["추천", "검색", "찾아줘", "자료"]):
                            res = ai.search_all_platforms(prompt, user_key)
                        
                        # (B) PDF 질문
                        elif "retriever" in st.session_state and st.session_state.retriever:
                            docs = st.session_state.retriever.invoke(prompt)
                            ctx = "\n".join([d.page_content for d in docs])
                            res = ai.ask_ai(f"문서 내용:\n{ctx}\n\n질문: {prompt}", user_key)
                        
                        # (C) 일반 대화
                        else:
                            res = ai.ask_ai(prompt, user_key)
                else:
                    res = "⚠️ 잘못된 입력입니다. 다시 시도해 주세요."

                st.markdown(res)
                st.session_state.messages.append({"role": "assistant", "content": res})