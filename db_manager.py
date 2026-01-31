import sqlite3
import pymysql
import streamlit as st
import bcrypt
import uuid
import pandas as pd

def get_db_connection():
    try:
        if "db" in st.secrets:
            return pymysql.connect(
                host=st.secrets["db"]["host"],
                user=st.secrets["db"]["user"],
                password=st.secrets["db"]["password"],
                db=st.secrets["db"]["name"],
                port=int(st.secrets["db"].get("port", 3306)),
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=10
            )
    except Exception as e:
        print(f"DB 연결 실패: {e}")
    
    return sqlite3.connect('cobuddy.db', check_same_thread=False)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 만약 기존에 잘못 생성된 테이블이 있다면 삭제 (초기 1회 권장)
    # 아래 DROP 구문은 처음 한 번만 실행하고 나중에 주석 처리해도 됩니다.
    cursor.execute("DROP TABLE IF EXISTS my_skills")
    cursor.execute("DROP TABLE IF EXISTS users")

    # 2. MySQL과 SQLite 모두 호환되는 엄격한 문법
    # VARCHAR 길이 지정 및 NOT NULL 명시
    queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(50) NOT NULL,
            nickname VARCHAR(100) NOT NULL,
            password_hash VARCHAR(255),
            last_login VARCHAR(50),
            PRIMARY KEY (user_id),
            UNIQUE (nickname)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS my_skills (
            user_id VARCHAR(50) NOT NULL,
            skill_name VARCHAR(100) NOT NULL,
            level INTEGER NOT NULL,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, skill_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    ]
    
    try:
        if isinstance(conn, sqlite3.Connection):
            # SQLite용 문법으로 살짝 변경 (ENGINE 설정 제거)
            for q in queries:
                q_lite = q.split("ENGINE=")[0].replace("DATETIME DEFAULT CURRENT_TIMESTAMP", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
                cursor.execute(q_lite)
        else:
            # MySQL용 실행
            for q in queries:
                cursor.execute(q)
        
        if hasattr(conn, 'commit'):
            conn.commit()
        print("✅ DB 초기화 및 테이블 생성 완료")
    except Exception as e:
        print(f"❌ DB 초기화 에러: {e}")
    finally:
        conn.close()

# --- 아래 함수들은 기존과 동일 (수정 불필요하지만 전체 코드 유지를 위해 포함) ---

def authenticate_user(nickname, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not isinstance(conn, sqlite3.Connection):
            query = "SELECT * FROM users WHERE nickname = %s"
        else:
            query = "SELECT * FROM users WHERE nickname = ?"
        cursor.execute(query, (nickname,))
        user = cursor.fetchone()
        if user and isinstance(user, sqlite3.Row): user = dict(user)
        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return user
        return None
    finally: conn.close()

def save_skill(user_id, skill, level):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if not isinstance(conn, sqlite3.Connection):
            query = "INSERT INTO my_skills (user_id, skill_name, level) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE level = %s"
            cursor.execute(query, (user_id, skill, level, level))
        else:
            query = "INSERT OR REPLACE INTO my_skills (user_id, skill_name, level) VALUES (?, ?, ?)"
            cursor.execute(query, (user_id, skill, level))
        conn.commit()
    finally: conn.close()

def create_user(nickname, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        q_check = "SELECT nickname FROM users WHERE nickname = %s" if not isinstance(conn, sqlite3.Connection) else "SELECT nickname FROM users WHERE nickname = ?"
        cursor.execute(q_check, (nickname,))
        if cursor.fetchone(): return False, "이미 존재하는 닉네임입니다."
        user_id = str(uuid.uuid4())[:16]
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        q_ins = "INSERT INTO users (user_id, nickname, password_hash) VALUES (%s, %s, %s)" if not isinstance(conn, sqlite3.Connection) else "INSERT INTO users (user_id, nickname, password_hash) VALUES (?, ?, ?)"
        cursor.execute(q_ins, (user_id, nickname, pw_hash))
        conn.commit()
        return True, user_id
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_or_create_google_user(email, name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        nickname = email.split('@')[0]
        q_find = "SELECT * FROM users WHERE nickname = %s" if not isinstance(conn, sqlite3.Connection) else "SELECT * FROM users WHERE nickname = ?"
        cursor.execute(q_find, (nickname,))
        user = cursor.fetchone()
        if user: return True, user['user_id'] if not isinstance(conn, sqlite3.Connection) else dict(user)['user_id']
        user_id = str(uuid.uuid4())[:16]
        q_ins = "INSERT INTO users (user_id, nickname, password_hash) VALUES (%s, %s, %s)" if not isinstance(conn, sqlite3.Connection) else "INSERT INTO users (user_id, nickname, password_hash) VALUES (?, ?, ?)"
        cursor.execute(q_ins, (user_id, nickname, "GOOGLE_OAUTH"))
        conn.commit()
        return True, user_id
    finally: conn.close()

def get_my_skills(user_id):
    conn = get_db_connection()
    try:
        q = "SELECT skill_name, level FROM my_skills WHERE user_id = %s" if not isinstance(conn, sqlite3.Connection) else "SELECT skill_name, level FROM my_skills WHERE user_id = ?"
        df = pd.read_sql(q, conn, params=(user_id,))
        if df.empty: return "🐣 아직 등록된 스킬이 없어요."
        res = "### 📋 현재 당신의 기술 스택\n\n"
        for _, r in df.iterrows():
            lv = r['level']
            res += f"**{r['skill_name']}** (Lv.{lv})  \n" + "🔥" * lv + "⚪" * (10-lv) + "\n\n"
        return res
    finally: conn.close()

def get_admin_stats():
    conn = get_db_connection()
    try:
        u_list = pd.read_sql("SELECT user_id, nickname, last_login FROM users", conn)
        s_list = pd.read_sql("SELECT * FROM my_skills", conn)
        return len(u_list), len(s_list), u_list, s_list
    finally: conn.close()