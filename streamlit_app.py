import streamlit as st
import db_manager as db
import ai_utils as ai
import rag_utils as rag
import urllib.parse
import requests

# 1. 페이지 설정 (반드시 코드 최상단에 위치)
st.set_page_config(page_title="코버디 🐣", layout="wide")

# 2. 데이터베이스 초기화
db.init_db()

# 3. 세션 상태 초기화
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_nick" not in st.session_state:
    st.session_state.user_nick = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# 4. 구글 로그인 콜백 처리
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
        st.error(f"구글 로그인 오류: {e}")

# 5. 로그인 전 화면
if not st.session_state.user_id:
    st.title("🐣 코버디: 초보 개발자의 성장 단짝")
    tab1, tab2, tab3 = st.tabs(["🔑 로그인", "✨ 회원가입", "🚀 구글 로그인"])
    
    with tab1:
        with st.form("login_form"):
            login_nick = st.text_input("닉네임", key="login_nick_in")
            login_pw = st.text_input("비밀번호", type="password", key="login_pw_in")
            if st.form_submit_button("로그인 🚀"):
                user = db.authenticate_user(login_nick, login_pw)
                if user:
                    st.session_state.user_id = user['user_id']
                    st.session_state.user_nick = login_nick
                    st.rerun()
                else:
                    st.error("닉네임 또는 비밀번호가 틀렸습니다.")

    with tab2:
        with st.form("signup_form"):
            new_nick = st.text_input("사용할 닉네임", key="signup_nick_in")
            new_pw = st.text_input("비밀번호 (6자 이상)", type="password", key="signup_pw_in")
            confirm_pw = st.text_input("비밀번호 확인", type="password", key="signup_confirm")
            if st.form_submit_button("회원가입 완료 ✨"):
                if len(new_nick) < 2 or len(new_pw) < 6:
                    st.warning("닉네임은 2자, 비밀번호는 6자 이상이어야 합니다.")
                elif new_pw != confirm_pw:
                    st.error("비밀번호가 서로 다릅니다.")
                else:
                    success, msg = db.create_user(new_nick, new_pw)
                    if success:
                        st.success("가입 성공! 로그인 탭에서 로그인 해주세요.")
                    else:
                        st.error(msg)

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
            st.info("💡 구글 로그인 설정이 필요합니다.")
    st.stop()
    
# 6. 로그인 후 메인 화면 (사이드바)
with st.sidebar:
    st.write(f"### 👋 {st.session_state.user_nick}님 반가워요!")
    
    # AI 설정
    st.markdown("### 🔑 AI 설정")
    user_key = st.text_input("Gemini API Key 입력", type="password", key="user_gemini_key", help="Google AI Studio에서 발급받은 키를 입력하세요.")
    if user_key:
        st.success("✅ API 키가 적용되었습니다!")
    else:
        st.info("💡 키가 없으면 기본 설정을 사용합니다.")

    st.divider()
    
    # PDF 학습 기능
    st.markdown("### 📚 스마트 문서 학습")
    st.write("학습 자료(PDF)를 올리면 코버디가 내용을 분석해 질문에 답변해 드립니다.")
    pdf_file = st.file_uploader("PDF 파일을 선택하세요", type=["pdf"], key="pdf_uploader")
    
    if pdf_file:
        if "current_pdf" not in st.session_state or st.session_state.current_pdf != pdf_file.name:
            with st.spinner("문서를 읽고 분석하는 중... 📖"):
                st.session_state.retriever = rag.process_pdf(pdf_file)
                st.session_state.current_pdf = pdf_file.name
                st.success("✅ 분석 완료! 이제 질문해 보세요.")
        else:
            st.caption(f"학습 중인 문서: {pdf_file.name}")

    st.divider()
    
    # 로그아웃
    if st.button("🚪 로그아웃", key="logout_btn", use_container_width=True):
        st.session_state.clear()
        st.rerun()

# 7. 메인 채팅 UI
st.title("💬 코버디와 대화하기")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("궁금한 것을 물어보세요!"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("생각 중... 🐣"):
            # A. 스킬 저장 (예: 파이썬 5)
            if len(prompt.split()) == 2 and prompt.split()[1].isdigit():
                skill, lv = prompt.split()
                db.save_skill(st.session_state.user_id, skill, int(lv))
                response = f"✅ **{skill}** 기술을 **{lv}단계**로 저장했습니다!"
            
            # B. 자료 추천
            elif "추천" in prompt or "찾아줘" in prompt:
                response = ai.search_all(prompt, user_key)
            
            # C. PDF 기반 답변
            elif "retriever" in st.session_state and st.session_state.retriever:
                docs = st.session_state.retriever.invoke(prompt)
                context = "\n".join([d.page_content for d in docs])
                response = ai.ask_ai(f"다음 문서 내용을 바탕으로 답변해줘:\n\n{context}\n\n질문: {prompt}", user_key)
            
            # D. 일반 대화
            else:
                response = ai.ask_ai(prompt, user_key)
                
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})