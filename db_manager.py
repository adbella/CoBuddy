import sqlite3
import pymysql
import streamlit as st
import bcrypt
import uuid
import pandas as pd

def get_db_connection():
    # 1. Streamlit Secrets에 MySQL 정보가 있으면 우선 연결
    try:
        if "db" in st.secrets:
            return pymysql.connect(
                host=st.secrets["db"]["host"],
                user=st.secrets["db"]["user"],
                password=st.secrets["db"]["password"],
                db=st.secrets["db"]["name"],
                port=int(st.secrets["db"].get("port", 3306)),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
    except Exception as e:
        pass
   
    # 2. 없으면 로컬 SQLite 사용
    conn = sqlite3.connect('cobuddy.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_users_for_admin():
    conn = get_db_connection()
    try:
        # 비밀번호 해시는 제외하고 이메일, 닉네임, 가입일만 조회
        query = "SELECT user_id, nickname, last_login FROM users"
        if isinstance(conn, sqlite3.Connection):
            import pandas as pd
            return pd.read_sql(query, conn)
        else: # MySQL일 경우
            import pandas as pd
            return pd.read_sql(query, conn)
    finally:
        conn.close()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    queries = [
        "CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, nickname TEXT UNIQUE, password_hash TEXT, last_login TEXT)",
        "CREATE TABLE IF NOT EXISTS my_skills (user_id TEXT, skill_name TEXT, level INTEGER, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (user_id, skill_name))"
    ]
    for q in queries:
        cursor.execute(q)
    if hasattr(conn, 'commit'): conn.commit()
    conn.close()

def create_user(nickname, password):
    """일반 회원가입"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 중복 확인
        q_check = "SELECT nickname FROM users WHERE nickname = %s" if "db" in st.secrets else "SELECT nickname FROM users WHERE nickname = ?"
        cursor.execute(q_check, (nickname,))
        if cursor.fetchone(): return False, "이미 존재하는 닉네임입니다."
        
        user_id = str(uuid.uuid4())[:16]
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        q_ins = "INSERT INTO users (user_id, nickname, password_hash) VALUES (%s, %s, %s)" if "db" in st.secrets else "INSERT INTO users (user_id, nickname, password_hash) VALUES (?, ?, ?)"
        cursor.execute(q_ins, (user_id, nickname, pw_hash))
        conn.commit()
        return True, user_id
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_or_create_google_user(email, name):
    """구글 로그인 사용자 처리"""
    conn = get_db_connection()
    cursor = conn.cursor()
    nickname = email.split('@')[0]
    
    q_find = "SELECT * FROM users WHERE nickname = %s" if "db" in st.secrets else "SELECT * FROM users WHERE nickname = ?"
    cursor.execute(q_find, (nickname,))
    user = cursor.fetchone()
    
    if user:
        conn.close()
        return True, user['user_id']
    
    # 신규 생성
    user_id = str(uuid.uuid4())[:16]
    q_ins = "INSERT INTO users (user_id, nickname, password_hash) VALUES (%s, %s, %s)" if "db" in st.secrets else "INSERT INTO users (user_id, nickname, password_hash) VALUES (?, ?, ?)"
    cursor.execute(q_ins, (user_id, nickname, "GOOGLE_OAUTH"))
    conn.commit()
    conn.close()
    return True, user_id

def get_my_skills(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        q = "SELECT skill_name, level FROM my_skills WHERE user_id = %s" if "db" in st.secrets else "SELECT skill_name, level FROM my_skills WHERE user_id = ?"
        cursor.execute(q, (user_id,))
        rows = cursor.fetchall()
        if not rows:
            return "🐣 아직 등록된 스킬이 없어요. '**파이썬 5**' 처럼 입력해서 첫 스킬을 등록해보세요!"
        
        res = "### 📋 현재 당신의 기술 스택\n\n"
        for r in rows:
            lv = r['level']
            gauge = "🔥" * lv + "⚪" * (10-lv)
            res += f"**{r['skill_name']}** (Lv.{lv})  \n{gauge}\n\n"
        return res
    except Exception as e: return f"조회 에러: {e}"
    finally: conn.close()

def delete_skill(user_id, skill_name):
    """특정 스킬 삭제"""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        query = "DELETE FROM my_skills WHERE user_id = %s AND skill_name = %s" if "db" in st.secrets else "DELETE FROM my_skills WHERE user_id = ? AND skill_name = ?"
        cursor.execute(query, (user_id, skill_name))
        conn.commit()
        return True
    except: return False
    finally: conn.close()    

def get_admin_stats():
    """관리자용: 전체 통계 데이터 가져오기"""
    conn = get_db_connection()
    try:
        # 사용자 수, 등록된 총 스킬 수 조회
        if isinstance(conn, sqlite3.Connection):
            u_count = pd.read_sql("SELECT COUNT(*) as cnt FROM users", conn).iloc[0]['cnt']
            s_count = pd.read_sql("SELECT COUNT(*) as cnt FROM my_skills", conn).iloc[0]['cnt']
            user_list = pd.read_sql("SELECT user_id, nickname, last_login FROM users", conn)
            skill_list = pd.read_sql("SELECT * FROM my_skills", conn)
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as cnt FROM users")
                u_count = cur.fetchone()['cnt']
                cur.execute("SELECT COUNT(*) as cnt FROM my_skills")
                s_count = cur.fetchone()['cnt']
            user_list = pd.read_sql("SELECT user_id, nickname, last_login FROM users", conn)
            skill_list = pd.read_sql("SELECT * FROM my_skills", conn)
            
        return u_count, s_count, user_list, skill_list
    finally:
        conn.close()    