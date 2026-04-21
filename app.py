import streamlit as st
import os
import sqlite3
import hashlib
import time
from groq import Groq
from datetime import datetime

# --- 1. CONFIG & THEME ---
st.set_page_config(page_title="AI Assistant", page_icon="🤖", layout="wide")

# Custom CSS для UI/UX уровня ChatGPT
st.markdown("""
    <style>
    /* Базовые настройки темы */
    .stApp { background-color: #0d0d0d !important; color: #ececf1 !important; }
    [data-testid="stSidebar"] { background-color: #000000 !important; border-right: 1px solid #2d2d2d; }
    
    /* Стилизация чата */
    .stChatMessage { 
        padding: 1.5rem !important; 
        border-bottom: 1px solid #212121 !important; 
        background-color: transparent !important; 
    }
    .stChatMessage[data-testid="stChatMessageUser"] { background-color: #1a1a1a !important; border-radius: 15px; }
    
    /* Контейнер ввода (Bottom Dock) */
    .stChatInputContainer {
        position: fixed; bottom: 20px;
        border-radius: 15px !important;
        background-color: #212121 !important;
        border: 1px solid #333 !important;
    }
    
    /* Кнопки в сайдбаре */
    .chat-history-item {
        padding: 10px; margin: 5px 0;
        border-radius: 8px; cursor: pointer;
        background: transparent; border: 1px solid transparent;
        transition: 0.2s; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    }
    .chat-history-item:hover { background: #202123; border-color: #444; }
    
    /* Индикатор печати */
    .typing { color: #8e8ea0; font-size: 0.8rem; margin-left: 1rem; }
    </style>
    
    <script>
    // Авто-скролл вниз при обновлении
    const observer = new MutationObserver(() => {
        const main = window.parent.document.querySelector(".main");
        if (main) main.scrollTo({top: main.scrollHeight, behavior: 'smooth'});
    });
    observer.observe(window.parent.document.body, {childList: true, subtree: true});
    </script>
""", unsafe_allow_html=True)

# --- 2. DATABASE LAYER ---
def init_db():
    conn = sqlite3.connect("core_v2.db", check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, u TEXT UNIQUE, p TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS threads (id TEXT PRIMARY KEY, uid INTEGER, title TEXT, created_at TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS messages (tid TEXT, role TEXT, content TEXT, timestamp TEXT)')
    conn.commit()
    return conn

db = init_db()

# --- 3. SESSION LOGIC ---
if "user" not in st.session_state: st.session_state.user = None
if "active_tid" not in st.session_state: st.session_state.active_tid = None
if "temp_files" not in st.session_state: st.session_state.temp_files = []

# --- 4. SIDEBAR (HISTORY & SETTINGS) ---
with st.sidebar:
    st.markdown("### AI Assistant")
    if st.button("+ Новый чат", use_container_width=True):
        st.session_state.active_tid = None
        st.rerun()
    
    st.markdown("---")
    if st.session_state.user:
        st.write("🕓 История")
        threads = db.execute("SELECT id, title FROM threads WHERE uid = ? ORDER BY created_at DESC", 
                             (st.session_state.user['id'],)).fetchall()
        for tid, title in threads:
            col_t, col_d = st.columns([0.85, 0.15])
            if col_t.button(f"💬 {title[:20]}...", key=tid, use_container_width=True):
                st.session_state.active_tid = tid
                st.rerun()
            if col_d.button("🗑️", key=f"del_{tid}"):
                db.execute("DELETE FROM threads WHERE id = ?", (tid,))
                db.execute("DELETE FROM messages WHERE tid = ?", (tid,))
                db.commit()
                st.rerun()
        
        st.markdown("---")
        if st.button("🚪 Выход"):
            st.session_state.user = None
            st.rerun()
    else:
        st.info("Войдите для сохранения истории")

# --- 5. AUTH SCREEN (UX: Registration/Login) ---
if not st.session_state.user:
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    with tab1:
        u = st.text_input("Username", key="login_u")
        p = st.text_input("Password", type="password", key="login_p")
        if st.button("Войти"):
            hp = hashlib.sha256(p.encode()).hexdigest()
            res = db.execute("SELECT * FROM users WHERE u=? AND p=?", (u, hp)).fetchone()
            if res:
                st.session_state.user = {"id": res[0], "name": res[1]}
                st.rerun()
            else: st.error("Неверные данные")
    with tab2:
        nu = st.text_input("New Username", key="reg_u")
        np = st.text_input("New Password", type="password", key="reg_p")
        if st.button("Создать аккаунт"):
            try:
                db.execute("INSERT INTO users (u, p) VALUES (?, ?)", (nu, hashlib.sha256(np.encode()).hexdigest()))
                db.commit()
                st.success("Успех! Теперь войдите.")
            except: st.error("Имя занято")
    st.stop()

# --- 6. CHAT LOGIC ---
# Загрузка сообщений
if st.session_state.active_tid:
    msgs = db.execute("SELECT role, content FROM messages WHERE tid = ? ORDER BY timestamp ASC", 
                      (st.session_state.active_tid,)).fetchall()
    st.session_state.messages = [{"role": r, "content": c} for r, c in msgs]
else:
    st.session_state.messages = []

# Отрисовка
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if st.button("📋", key=hash(m["content"])):
            st.write("Скопировано в буфер (имитация)")

# Ввод файлов (над чатом)
with st.expander("📎 Прикрепить файлы"):
    files = st.file_uploader("Фото или документы", accept_multiple_files=True)
    if files:
        st.session_state.temp_files = [f.name for f in files]
        st.write("Готовы к отправке:", st.session_state.temp_files)

# Ввод сообщения
if prompt := st.chat_input("Спросите о чем угодно..."):
    if not st.session_state.active_tid:
        new_tid = str(int(time.time()))
        db.execute("INSERT INTO threads (id, uid, title, created_at) VALUES (?, ?, ?, ?)",
                   (new_tid, st.session_state.user['id'], prompt[:30], datetime.now().isoformat()))
        st.session_state.active_tid = new_tid
    
    # Добавляем контекст файлов
    full_prompt = prompt
    if st.session_state.temp_files:
        full_prompt += f"\n\n[Система: Пользователь прикрепил файлы: {', '.join(st.session_state.temp_files)}]"
    
    # Сохраняем User message
    db.execute("INSERT INTO messages (tid, role, content, timestamp) VALUES (?, ?, ?, ?)",
               (st.session_state.active_tid, "user", full_prompt, datetime.now().isoformat()))
    db.commit()
    st.rerun()

# Генерация ответа (если последнее сообщение от user)
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant"):
        st.markdown("<div class='typing'>AI печатает...</div>", unsafe_allow_html=True)
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": m["role"], "content": m["content"]} for m in st.session_state.messages],
                stream=True
            )
            full_res = ""
            ph = st.empty()
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_res += content
                    ph.markdown(full_res)
            
            db.execute("INSERT INTO messages (tid, role, content, timestamp) VALUES (?, ?, ?, ?)",
                       (st.session_state.active_tid, "assistant", full_res, datetime.now().isoformat()))
            db.commit()
            st.session_state.temp_files = [] # Сброс файлов
            st.rerun()
        except Exception as e:
            st.error(f"Ошибка API: {e}")
