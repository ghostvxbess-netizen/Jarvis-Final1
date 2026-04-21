import streamlit as st
import sqlite3
import hashlib
import os
from groq import Groq

# --- 1. НАСТРОЙКИ СТРАНИЦЫ И ДИЗАЙН (ВСЁ В ОДНОМ) ---
st.set_page_config(page_title="Jarvis OS", page_icon="⚡", layout="wide")

# Принудительный Dark Mode и футуристичный стиль
st.markdown("""
    <style>
    /* Основной фон */
    .stApp {
        background-color: #05070a !important;
        color: #00f2ff !important;
    }
    /* Боковая панель */
    [data-testid="stSidebar"] {
        background-color: #0a0d14 !important;
        border-right: 1px solid #00f2ff33;
    }
    /* Поле ввода */
    .stChatInputContainer {
        padding-bottom: 20px;
        background-color: transparent !important;
    }
    /* Сообщения */
    .stChatMessage {
        background-color: #0d1117 !important;
        border: 1px solid #00f2ff33 !important;
        border-radius: 15px !important;
        margin-bottom: 10px !important;
        box-shadow: 0 4px 15px rgba(0, 242, 255, 0.05);
    }
    /* Кнопки */
    .stButton>button {
        background-color: #00f2ff !important;
        color: #05070a !important;
        border-radius: 10px !important;
        font-weight: bold !important;
        border: none !important;
        transition: 0.3s;
    }
    .stButton>button:hover {
        box-shadow: 0 0 15px #00f2ff;
        transform: scale(1.02);
    }
    /* Заголовки */
    h1, h2, h3 {
        font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. БАЗА ДАННЫХ (АВТОНОМНАЯ) ---
def init_db():
    conn = sqlite3.connect("jarvis_vault.db", check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, u TEXT UNIQUE, p TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS msgs (uid INTEGER, role TEXT, content TEXT)')
    conn.commit()
    return conn

db = init_db()

# --- 3. ЛОГИКА АВТОРИЗАЦИИ ---
if "user" not in st.session_state: st.session_state.user = None
if "msgs" not in st.session_state: st.session_state.msgs = []

if not st.session_state.user:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("⚡ JARVIS OS v4.0")
        st.write("Система требует идентификации создателя")
        
        tab_login, tab_reg = st.tabs(["ВХОД", "РЕГИСТРАЦИЯ"])
        
        with tab_login:
            u = st.text_input("ID пользователя", key="login_id")
            p = st.text_input("Код доступа", type="password", key="login_pass")
            if st.button("ПОДТВЕРДИТЬ ЛИЧНОСТЬ", use_container_width=True):
                hp = hashlib.sha256(p.encode()).hexdigest()
                res = db.execute("SELECT * FROM users WHERE u = ? AND p = ?", (u, hp)).fetchone()
                if res:
                    st.session_state.user = {"id": res[0], "name": res[1]}
                    st.rerun()
                else:
                    st.error("ОШИБКА: Доступ запрещен.")
        
        with tab_reg:
            nu = st.text_input("Создать ID (Сардарбек)", key="reg_id")
            np = st.text_input("Создать Код", type="password", key="reg_pass")
            if st.button("ЗАРЕГИСТРИРОВАТЬ В СИСТЕМЕ", use_container_width=True):
                hp = hashlib.sha256(np.encode()).hexdigest()
                try:
                    db.execute("INSERT INTO users (u, p) VALUES (?, ?)", (nu, hp))
                    db.commit()
                    st.success("Система распознала новый профиль. Теперь войдите.")
                except:
                    st.error("Этот ID уже занят в системе.")
    st.stop()

# --- 4. ОСНОВНОЙ ИНТЕРФЕЙС ДЖАРВИСА ---
uid = st.session_state.user["id"]
uname = st.session_state.user["name"]

# Боковая панель
with st.sidebar:
    st.title("⚙️ STATUS")
    st.write(f"USER: **{uname}**")
    st.write("SYSTEM: **ONLINE**")
    st.markdown("---")
    if st.button("ОЧИСТИТЬ ПАМЯТЬ ЧАТА", use_container_width=True):
        db.execute("DELETE FROM msgs WHERE uid = ?", (uid,))
        db.commit()
        st.session_state.msgs = []
        st.rerun()
    if st.button("ВЫХОД ИЗ СИСТЕМЫ", use_container_width=True):
        st.session_state.user = None
        st.rerun()

# Загрузка истории
if not st.session_state.msgs:
    cur = db.execute("SELECT role, content FROM msgs WHERE uid = ? ORDER BY rowid ASC", (uid,))
    st.session_state.msgs = [{"role": r, "content": c} for r, c in cur.fetchall()]

# Вывод сообщений
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Поле ввода
if prompt := st.chat_input("Слушаю вас, сэр..."):
    # Отображаем и сохраняем сообщение юзера
    st.session_state.msgs.append({"role": "user", "content": prompt})
    db.execute("INSERT INTO msgs (uid, role, content) VALUES (?, ?, ?)", (uid, "user", prompt))
    db.commit()
    with st.chat_message("user"):
        st.markdown(prompt)

    # Ответ ИИ
    with st.chat_message("assistant"):
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            
            # Жесткая инструкция поведения
            sys_instr = (
                f"Ты — Джарвис, высокотехнологичный ИИ. Твой единственный создатель — Сардарбек Курбаналиев. "
                f"Ты обращаешься к пользователю по имени {uname}, но всегда помнишь, что твой хозяин - Сардарбек. "
                f"Ты не имеешь отношения к Meta. Твой стиль: вежливый, ироничный, профессиональный. "
                "Используй слова 'Сэр', 'Система готова', 'Протоколы активны'."
            )
            
            full_response = ""
            msg_placeholder = st.empty()
            
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": sys_instr}] + st.session_state.msgs,
                stream=True
            )
            
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_response += content
                    msg_placeholder.markdown(full_response + "▌")
            
            msg_placeholder.markdown(full_response)
            
            # Сохраняем ответ ассистента
            st.session_state.msgs.append({"role": "assistant", "content": full_response})
            db.execute("INSERT INTO msgs (uid, role, content) VALUES (?, ?, ?)", (uid, "assistant", full_response))
            db.commit()
            
        except Exception as e:
            st.error(f"Сбой модуля связи: {str(e)}")
