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
        pass
    return sqlite3.connect('cobuddy.db', check_same_thread=False)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    # VARCHAR 길이를 명확히 지정하여 MySQL 호환성 확보
    queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id VARCHAR(50) PRIMARY KEY,
            nickname VARCHAR(100) UNIQUE,
            password_hash VARCHAR(255),
            last_login VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS my_skills (
            user_id VARCHAR(50),
            skill_name VARCHAR(100),
            level INTEGER,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, skill_name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    ]
    try:
        if isinstance(conn, sqlite3.Connection):
            for q in queries:
                cursor.execute(q.split("ENGINE=")[0])
        else:
            for q in queries:
                cursor.execute(q)
        conn.commit()
    finally:
        conn.close()

def save_skill(user_id, skill, level):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # ID와 스킬명에서 혹시 모를 공백 제거
        user_id = str(user_id).strip()
        skill = str(skill).strip()
        
        if not isinstance(conn, sqlite3.Connection):
            # MySQL 전용: INSERT ... ON DUPLICATE KEY UPDATE
            query = """
                INSERT INTO my_skills (user_id, skill_name, level) 
                VALUES (%s, %s, %s) 
                ON DUPLICATE KEY UPDATE level = %s
            """
            cursor.execute(query, (user_id, skill, level, level))
        else:
            # SQLite 전용
            query = "INSERT OR REPLACE INTO my_skills (user_id, skill_name, level) VALUES (?, ?, ?)"
            cursor.execute(query, (user_id, skill, level))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"저장 실패: {e}")
        return False
    finally:
        conn.close()

def get_my_skills(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        user_id = str(user_id).strip()
        is_mysql = not isinstance(conn, sqlite3.Connection)
        
        query = "SELECT skill_name, level FROM my_skills WHERE user_id = %s" if is_mysql else "SELECT skill_name, level FROM my_skills WHERE user_id = ?"
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()
        
        if not rows:
            db_type = "MySQL" if is_mysql else "SQLite"
            # 디버깅을 위해 현재 조회 시도한 ID의 앞 4자리만 살짝 표시
            return f"🐣 등록된 스킬이 없어요. (DB: {db_type} / ID: {user_id[:4]}...)\n'**파이썬 5**'처럼 입력해보세요!"

        res = "### 📋 현재 당신의 기술 스택\n\n"
        for r in rows:
            # Row 객체나 Dict 객체 모두 대응하도록 처리
            name = r['skill_name'] if is_mysql else dict(r)['skill_name']
            lv = r['level'] if is_mysql else dict(r)['level']
            gauge = "🔥" * lv + "⚪" * (10-lv)
            res += f"**{name}** (Lv.{lv})  \n{gauge}\n\n"
        return res
    except Exception as e:
        return f"❌ 조회 에러: {e}"
    finally:
        conn.close()

# --- 기타 인증 함수들 (기본 로직 유지하되 commit 보강) ---

def create_user(nickname, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        user_id = str(uuid.uuid4())[:16]
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        if not isinstance(conn, sqlite3.Connection):
            cursor.execute("INSERT INTO users (user_id, nickname, password_hash) VALUES (%s, %s, %s)", (user_id, nickname, pw_hash))
        else:
            cursor.execute("INSERT INTO users (user_id, nickname, password_hash) VALUES (?, ?, ?)", (user_id, nickname, pw_hash))
        conn.commit()
        return True, user_id
    except Exception as e: return False, str(e)
    finally: conn.close()

def get_or_create_google_user(email, name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        nickname = email.split('@')[0]
        q = "SELECT * FROM users WHERE nickname = %s" if not isinstance(conn, sqlite3.Connection) else "SELECT * FROM users WHERE nickname = ?"
        cursor.execute(q, (nickname,))
        user = cursor.fetchone()
        if user:
            return True, user['user_id'] if not isinstance(conn, sqlite3.Connection) else dict(user)['user_id']
        
        user_id = str(uuid.uuid4())[:16]
        q_ins = "INSERT INTO users (user_id, nickname, password_hash) VALUES (%s, %s, %s)" if not isinstance(conn, sqlite3.Connection) else "INSERT INTO users (user_id, nickname, password_hash) VALUES (?, ?, ?)"
        cursor.execute(q_ins, (user_id, nickname, "GOOGLE_OAUTH"))
        conn.commit()
        return True, user_id
    finally: conn.close()

def authenticate_user(nickname, password):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        q = "SELECT * FROM users WHERE nickname = %s" if not isinstance(conn, sqlite3.Connection) else "SELECT * FROM users WHERE nickname = ?"
        cursor.execute(q, (nickname,))
        user = cursor.fetchone()
        if not user: return None
        if isinstance(conn, sqlite3.Connection): user = dict(user)
        if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return user
        return None
    finally: conn.close()

def get_admin_stats():
    """관리자용: 전체 통계 데이터 가져오기"""
    conn = get_db_connection()
    try:
        # 데이터프레임이 비어있을 때를 대비하여 컬럼명 명시
        user_cols = ["user_id", "nickname", "last_login"]
        skill_cols = ["user_id", "skill_name", "level", "added_at"]
        
        # 1. 사용자 목록 조회
        u_list = pd.read_sql("SELECT user_id, nickname, last_login FROM users", conn)
        # 2. 스킬 목록 조회
        s_list = pd.read_sql("SELECT * FROM my_skills", conn)

        # 데이터가 없으면 빈 데이터프레임을 만들어서 컬럼을 유지합니다.
        if u_list.empty:
            u_list = pd.DataFrame(columns=user_cols)
        if s_list.empty:
            s_list = pd.DataFrame(columns=skill_cols)
            
        return len(u_list), len(s_list), u_list, s_list
    finally:
        conn.close()