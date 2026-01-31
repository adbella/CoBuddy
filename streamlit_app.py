import streamlit as st
import db_manager as db  # database 대신 db_manager를 불러옵니다.
import ai_utils as ai
import rag_utils as rag
import urllib.parse
import requests

st.set_page_config(page_title="코버디 🐣", layout="wide")

# DB 초기화
db.init_db()

# 세션 상태 초기화
if "user_id" not in st.session_state: st.session_state.user_id = None
if "messages" not in st.session_state: st.session_state.messages = []

# --- [1] 구글 OAuth 콜백 처리 ---
if "code" in st.query_params and st.session_state.user_id is None:
    code = st.query_params["code"]
    try:
        conf = st.secrets["google_oauth"]
        token_res = requests.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": conf["client_id"],
            "client_secret": conf["client_secret"],
            "redirect_uri": conf["redirect_uri"],
            "grant_type": "authorization_code",
        }).json()
        
        access_token = token_res.get("access_token")
        user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", 
                                 headers={"Authorization": f"Bearer {access_token}"}).json()
        
        email = user_info.get("email")
        name = user_info.get("name")
        
        if email:
            success, uid = db.get_or_create_google_user(email, name)
            st.session_state.user_id = uid
            st.session_state.user_nick = name if name else email.split('@')[0]
            st.query_params.clear()
            st.rerun()
    except Exception as e:
        st.error(f"구글 로그인 처리 중 오류: {e}")

# --- [2] 로그인 전 화면 ---
if not st.session_state.user_id:
    st.title("🐣 코버디: 초보 개발자의 성장 단짝")
    tab1, tab2, tab3 = st.tabs(["🔑 로그인", "✨ 회원가입", "🚀 구글 로그인"])
    
    with tab1:
        with st.form("login_form"):
            login_nick = st.text_input("닉네임", key="login_nick_input")
            login_pw = st.text_input("비밀번호", type="password", key="login_pw_input")
            if st.form_submit_button("로그인 🚀"):
                user = db.authenticate_user(login_nick, login_pw)
                if user:
                    st.session_state.user_id = user['user_id']
                    st.session_state.user_nick = login_nick
                    st.rerun()
                else: st.error("로그인 정보를 확인하세요.")

    with tab2:
        with st.form("signup_form"):
            new_nick = st.text_input("새 닉네임", key="signup_nick_input")
            new_pw = st.text_input("새 비밀번호", type="password", key="signup_pw_input")
            confirm_pw = st.text_input("비밀번호 확인", type="password", key="signup_confirm_pw")
            if st.form_submit_button("회원가입 ✨"):
                if len(new_nick) < 3 or len(new_pw) < 6:
                    st.warning("닉네임 3자, 비밀번호 6자 이상 필요")
                elif new_pw != confirm_pw:
                    st.error("비밀번호 불일치")
                else:
                    success, msg = db.create_user(new_nick, new_pw)
                    if success: st.success("가입 완료! 로그인 해주세요.")
                    else: st.error(msg)

    with tab3:
        if "google_oauth" in st.secrets:
            conf = st.secrets["google_oauth"]
            params = {
                "response_type": "code",
                "client_id": conf["client_id"],
                "redirect_uri": conf["redirect_uri"],
                "scope": "openid email profile",
                "prompt": "select_account"
            }
            auth_url = f"https://accounts.google.com/o/oauth2/auth?{urllib.parse.urlencode(params)}"
            st.link_button("🔵 구글 계정으로 로그인", auth_url, use_container_width=True)
        else:
            st.info("Secrets 설정을 확인해주세요.")
    st.stop()

# --- [3] 로그인 후 메인 화면 ---
with st.sidebar:
    st.write(f"### 👋 {st.session_state.user_nick}님")
    user_key = st.text_input("Gemini API Key (선택)", type="password", key="user_gemini_key")
    
    st.divider()
    pdf_file = st.file_uploader("PDF 학습 자료", type="pdf", key="pdf_uploader")
    if pdf_file and "retriever" not in st.session_state:
        with st.spinner("PDF 분석 중..."):
            st.session_state.retriever = rag.process_pdf(pdf_file)
            st.success("PDF 준비 완료!")

    st.divider()
    if st.button("🚪 로그아웃", key="logout_btn", use_container_width=True):
        st.session_state.clear()
        st.rerun()

st.title("💬 코버디와 대화하기")

# 채팅 표시
for m in st.session_state.messages:
    with st.chat_message(m["role"]): st.markdown(m["content"])

if prompt := st.chat_input("질문을 입력하세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # 로직 구분
        if len(prompt.split()) == 2 and prompt.split()[1].isdigit():
            skill, lv = prompt.split()
            db.save_skill(st.session_state.user_id, skill, int(lv))
            response = f"✅ {skill} {lv}단계를 저장했습니다!"
        elif "추천" in prompt or "찾아줘" in prompt:
            response = ai.search_all(prompt, user_key)
        elif "retriever" in st.session_state:
            docs = st.session_state.retriever.invoke(prompt)
            context = "\n".join([d.page_content for d in docs])
            response = ai.ask_ai(f"문서 내용:\n{context}\n\n질문: {prompt}", user_key)
        else:
            response = ai.ask_ai(prompt, user_key)
            
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})