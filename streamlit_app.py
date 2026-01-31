# --- [3] 로그인 후 사이드바 전체 코드] ---
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
        if "show_key_input" not in st.session_state:
            st.session_state.show_key_input = False
        if "user_key_value" not in st.session_state:
            st.session_state.user_key_value = default_key
            
        effective_key = st.session_state.user_key_value

        # 1. 키 입력창 노출 조건 및 마스킹
        if st.session_state.show_key_input or not effective_key:
            
            masked_key = "********" if effective_key else ""
            
            user_input_key = st.text_input(
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

        # user_key 변수 업데이트 (메인 로직에서 사용할 키)
        user_key = effective_key
        
        st.divider()

        # PDF 업로드 영역 (UI 개선)
        st.markdown("### 📚 스마트 PDF 학습")
        st.info("여기에 공부할 PDF 파일을 올려주세요. 모든 파일이 누적되어 분석됩니다.")
        
        # 세션 상태에 파일 리스트 초기화
        if "uploaded_file_list" not in st.session_state:
            st.session_state.uploaded_file_list = []
            st.session_state.processed_file_names = set()

        new_uploaded_files = st.file_uploader(
            "파일 업로드 (PDF 전용)", 
            type=["pdf"], 
            key="pdf_uploader",
            accept_multiple_files=True,
            label_visibility="collapsed"
        )
        
        # 파일 처리 로직
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
                
                # 🌟🌟🌟 들여쓰기 오류 수정 부분 🌟🌟🌟
                with st.expander("학습 문서 목록 보기"):
                    for file in file_names:
                        st.write(f"- {file.name}")
                        
        st.divider()

        # 관리자 메뉴
        is_admin = st.session_state.user_nick in ["안종호"] 
        if is_admin:
            st.markdown("### 👑 관리자 메뉴")
            if "show_admin" not in st.session_state:
                st.session_state.show_admin = False
                
            st.session_state.show_admin = st.checkbox("관리자 대시보드 보기", key="admin_chk")

        st.divider()
        
        # 로그아웃 버튼
        if st.button("🚪 로그아웃", key="sidebar_logout_btn", use_container_width=True): 
            st.session_state.clear()
            st.rerun()

# --- [메인 화면 영역 수정] ---
if st.session_state.get("show_admin"):
    # ... (관리자 대시보드 출력 코드) ...
    st.title("📊 관리자 대시보드")
    u_cnt, s_cnt, u_list, s_list = db.get_admin_stats()
    
    col1, col2 = st.columns(2)
    col1.metric("총 가입자 수", f"{u_cnt}명")
    col2.metric("총 등록 스킬", f"{s_cnt}개")
    
    st.write("### 👥 사용자 목록 (구글 로그인 정보 포함)")
    st.dataframe(u_list, use_container_width=True)
    
    st.write("### 🛠️ 전체 사용자 스킬 현황")
    st.dataframe(s_list, use_container_width=True)
    
    if st.button("채팅으로 돌아가기", key="close_admin_chat_btn"):
        st.session_state.show_admin = False
        st.rerun()
    
    st.stop() # 관리자 화면이 켜지면 여기서 앱 실행을 멈춤

# --- 메인 채팅창 ---
if not st.session_state.messages:
    # 온보딩 가이드
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
    with st.chat_message("user"): st.markdown(prompt)

    with st.chat_message("assistant"):
        # 1. 스킬 목록
        if prompt in ["목록", "조회", "스킬", "내 스킬"]:
            res = db.get_my_skills(st.session_state.user_id)
        # 2. 스킬 저장
        elif len(prompt.split()) == 2 and prompt.split()[1].isdigit():
            s, l = prompt.split()
            db.save_skill(st.session_state.user_id, s, int(l))
            res = f"✅ **{s}** (Level {l}) 저장 완료! 성장하는 모습이 보기 좋아요."
        # 3. 실시간 추천/검색
        elif any(w in prompt for w in ["추천", "검색", "찾아줘", "자료"]):
            with st.status("🌐 여러 플랫폼에서 최신 정보를 수집하는 중...") as status:
                res = ai.search_all_platforms(prompt, user_key)
                status.update(label="✅ 검색 및 분석 완료!", state="complete")
        # 4. PDF 답변
        elif "retriever" in st.session_state and st.session_state.retriever:
            with st.spinner("문서에서 정답을 찾는 중..."):
                docs = st.session_state.retriever.invoke(prompt)
                ctx = "\n".join([d.page_content for d in docs])
                res = ai.ask_ai(f"문서 내용:\n{ctx}\n\n질문: {prompt}", user_key)
        # 5. 일반 질문
        else:
            res = ai.ask_ai(prompt, user_key)
            
        st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})