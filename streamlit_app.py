import streamlit as st
import db_manager as db
import ai_utils as ai
import rag_utils as rag
import urllib.parse
import requests
from languages import TRANS # 🌟 languages.py에서 TRANS 가져오기

# 1. 페이지 설정
st.set_page_config(
    page_title="CoBuddy", 
    page_icon="🐣", 
    layout="wide"
)

# 2. 언어 설정 함수
if "language" not in st.session_state:
    st.session_state.language = "KR"

def t(key):
    """현재 언어에 맞는 텍스트 반환"""
    return TRANS[st.session_state.language].get(key, "Key Error")

# 3. 커스텀 CSS
st.markdown("""
    <style>
    .main { background-color: #f9f9fb; }
    .stButton>button { border-radius: 8px; }
    .stTextInput>div>div>input { border-radius: 8px; }
    .stChatMessage { border-radius: 15px; margin-bottom: 10px; }
    .stChatMessage[data-testid="stChatMessageUser"] { background-color: #e3f2fd; }
    .stChatMessage[data-testid="stChatMessageAssistant"] { background-color: #ffffff; border: 1px solid #eee; }
    </style>
""", unsafe_allow_html=True)

# 4. DB 및 세션 초기화
db.init_db()

if "user_id" not in st.session_state: st.session_state.user_id = None
if "messages" not in st.session_state: st.session_state.messages = []
if "show_admin" not in st.session_state: st.session_state.show_admin = False
if "uploaded_file_list" not in st.session_state: st.session_state.uploaded_file_list = []
if "processed_file_names" not in st.session_state: st.session_state.processed_file_names = set()
if "show_key_input" not in st.session_state: st.session_state.show_key_input = False
if "user_key_value" not in st.session_state: st.session_state.user_key_value = st.secrets.get("GOOGLE_API_KEY", "")

# 🌟 상단 언어 선택 버튼 (우측 상단) 🌟
col_main, col_lang = st.columns([8, 1])
with col_lang:
    lang_code = st.selectbox(
        "Language", ["KR", "EN"], 
        index=0 if st.session_state.language == "KR" else 1, 
        label_visibility="collapsed"
    )
    st.session_state.language = lang_code

# 5. 구글 로그인 콜백
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
    except: pass

# 6. 로그인 전 화면
if not st.session_state.user_id:
    st.markdown(f"<h1 style='text-align: center;'>{t('title')}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align: center; color: gray;'>{t('subtitle')}</p>", unsafe_allow_html=True)
    st.divider()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2, tab3 = st.tabs([t('login_tab'), t('signup_tab'), t('google_tab')])
        with tab1:
            with st.form("l_form"):
                n = st.text_input(t('nickname'))
                p = st.text_input(t('password'), type="password")
                if st.form_submit_button(t('login_btn'), use_container_width=True):
                    user = db.authenticate_user(n, p)
                    if user:
                        st.session_state.user_id = user['user_id']
                        st.session_state.user_nick = n
                        st.rerun()
                    else: st.error(t('err_info'))
        with tab2:
            with st.form("s_form"):
                nn = st.text_input(t('nickname'))
                np = st.text_input(t('password'), type="password")
                if st.form_submit_button(t('signup_btn'), use_container_width=True):
                    if len(nn) < 2 or len(np) < 6: st.warning(t('err_len'))
                    else:
                        s, m = db.create_user(nn, np)
                        if s: st.success(t('success_signup'))
                        else: st.error(m)
        with tab3:
            if "google_oauth" in st.secrets:
                conf = st.secrets["google_oauth"]
                params = {"response_type": "code", "client_id": conf["client_id"], "redirect_uri": conf["redirect_uri"], "scope": "openid email profile", "prompt": "select_account"}
                url = f"https://accounts.google.com/o/oauth2/auth?{urllib.parse.urlencode(params)}"
                st.link_button(t('google_btn'), url, use_container_width=True)
            else: st.info(t('secrets_needed'))
    st.stop()

# 7. 로그인 후 로직
if st.session_state.user_id:
    with st.sidebar:
        st.markdown(f"### {t('welcome')} {st.session_state.user_nick}!")
        
        # A. API 설정
        with st.expander(t('api_setup'), expanded=False):
            st.markdown(f"**:red[{t('api_no_key')}]** [Link](https://aistudio.google.com/app/apikey) {t('api_make_here')}")
            effective_key = st.session_state.user_key_value
            if st.session_state.show_key_input or not effective_key:
                masked_key = "********" if effective_key else ""
                user_input_key = st.text_input(t('api_placeholder'), type="password", value=masked_key, key="user_gemini_key_input")
                if user_input_key and user_input_key != masked_key:
                    st.session_state.user_key_value = user_input_key 
                    st.session_state.show_key_input = False
                    st.rerun()
                if effective_key and st.button("Cancel", key="cancel_key_input"):
                    st.session_state.show_key_input = False
                    st.rerun()
            else:
                st.success(t('api_success'))
                if st.button("Change", key="modify_key_btn"):
                    st.session_state.show_key_input = True
                    st.rerun()
        
        user_key = effective_key
        st.divider()

        # B. PDF 업로드
        st.markdown(f"### {t('pdf_title')}")
        st.info(t('pdf_info'))
        new_uploaded_files = st.file_uploader(t('pdf_upload_label'), type=["pdf"], key="pdf_uploader", accept_multiple_files=True, label_visibility="collapsed")
        if new_uploaded_files: 
            newly_added = [f for f in new_uploaded_files if f.name not in st.session_state.processed_file_names]
            if newly_added:
                st.session_state.uploaded_file_list.extend(newly_added)
                for f in newly_added: st.session_state.processed_file_names.add(f.name)
                with st.spinner(t('pdf_analyzing')):
                    st.session_state.retriever = rag.process_multiple_pdfs(st.session_state.uploaded_file_list)
                    st.success(t('pdf_done'))
            if st.session_state.uploaded_file_list:
                st.caption(f"📍 Docs: {len(st.session_state.uploaded_file_list)}")
                with st.expander(t('pdf_list')):
                    for file in st.session_state.uploaded_file_list: st.write(f"- {file.name}")

        st.divider()

        # C. 관리자
        is_admin = st.session_state.user_nick in ["안종호", "관리자", "adbella"] 
        if is_admin:
            st.markdown(f"### {t('admin_menu')}")
            st.session_state.show_admin = st.checkbox(t('admin_view'), key="admin_chk", value=st.session_state.show_admin)

        st.divider()
        if st.button(t('logout'), key="sidebar_logout_btn", use_container_width=True): 
            st.session_state.clear()
            st.rerun()

    # [메인 화면 1] 관리자 대시보드
    if st.session_state.get("show_admin"):
        st.title("📊 Admin Dashboard")
        u_cnt, s_cnt, u_list, s_list = db.get_admin_stats()
        col1, col2 = st.columns(2)
        with col1: st.metric("Users", f"{u_cnt}")
        with col2: st.metric("Skills", f"{s_cnt}")
        st.subheader("👥 User List"); st.dataframe(u_list, use_container_width=True, hide_index=True)
        st.subheader("🛠️ Skills"); st.dataframe(s_list, use_container_width=True, hide_index=True)
        if st.button("Close", key="close_admin_chat_btn"):
            st.session_state.show_admin = False
            st.rerun()
        st.stop()

    # [메인 화면 2] 채팅 UI
    if not st.session_state.messages:
        st.markdown(f"### {t('chat_guide_title')} {st.session_state.user_nick}!\n{t('chat_guide_desc')}")
        c1, c2, c3 = st.columns(3)
        with c1: st.info(t('guide_skill'))
        with c2: st.success(t('guide_search'))
        with c3: st.warning(t('guide_doc'))

    for m in st.session_state.messages:
        with st.chat_message(m["role"], avatar="🧑‍💻" if m["role"] == "user" else "🐣"): st.markdown(m["content"])

    if prompt := st.chat_input(t('chat_placeholder')):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍💻"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🐣"):
            # 🌟 [추가] 가장 먼저 사용자의 요청을 확인 중이라는 메시지를 띄웁니다.
            status_placeholder = st.empty()
            status_placeholder.caption(t('status_thinking'))
            
            lang_instruction = f"\n\n(Please answer in {t('prompt_lang')}. Use clear markdown tables if needed.)"
            final_prompt = prompt + lang_instruction
            
            # 1. 스킬 목록 조회 (DB)
            if prompt in ["목록", "조회", "스킬", "내 스킬", "list", "skill", "skills"]:
                status_placeholder.caption(t('status_db_checking')) # 🌟 DB 확인 문구로 변경
                res = db.get_my_skills(st.session_state.user_id)
                status_placeholder.empty() # 문구 제거
                st.markdown(res)
                st.session_state.messages.append({"role": "assistant", "content": res})
            
            # 2. 스킬 저장 (DB)
            elif len(prompt.split()) == 2 and prompt.split()[1].isdigit():
                status_placeholder.caption(t('status_skill_saving')) # 🌟 저장 중 문구로 변경
                s, l = prompt.split()
                db.save_skill(st.session_state.user_id, s, int(l))
                res = t('save_skill').format(s=s, l=l)
                status_placeholder.empty() # 문구 제거
                st.markdown(res)
                st.session_state.messages.append({"role": "assistant", "content": res})
            
            # 3. AI 답변 (검색 / PDF / 일반)
            else:
                status_placeholder.empty() # 상단 문구 제거 (st.status나 st.spinner가 대신 함)
                
                if any(w in prompt.lower() for w in ["추천", "검색", "찾아줘", "자료", "recommend", "search", "find"]):
                    with st.status(t('ai_searching')) as status:
                        stream_generator = ai.search_all_platforms(final_prompt, user_key)
                        status.update(label="Done!", state="complete", expanded=False)
                
                elif "retriever" in st.session_state and st.session_state.retriever:
                    with st.spinner(t('ai_reading')):
                        docs = st.session_state.retriever.invoke(prompt)
                        ctx = "\n".join([d.page_content for d in docs])
                        stream_generator = ai.ask_ai_stream(f"Context:\n{ctx}\n\nQuestion: {final_prompt}", user_key)
                
                else:
                    with st.spinner(t('status_ai_calling')): # 🌟 AI 호출 문구 적용
                        stream_generator = ai.ask_ai_stream(final_prompt, user_key)
                
                if stream_generator:
                    full_response = st.write_stream(stream_generator)
                    st.session_state.messages.append({"role": "assistant", "content": full_response})