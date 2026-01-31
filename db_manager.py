import sqlite3
import pymysql
import streamlit as st
import bcrypt
import uuid

def get_db_connection():
    try:
        if "db" in st.secrets:
            return pymysql.connect(
                host=st.secrets["db"]["host"],
                user=st.secrets["db"]["user"],
                password=st.secrets["db"]["password"],
                db=st.secrets["db"]["name"],
                charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
            )
    except: pass
    conn = sqlite3.connect('cobuddy.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

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