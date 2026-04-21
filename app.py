import streamlit as st
import os
import sqlite3
import hashlib
from groq import Groq

# --- 1. КОНФИГУРАЦИЯ И СТИЛЬ (ChatGPT Mobile Style) ---
st.set_page_config(page_title="ChatGPT", page_icon="🧪", layout="wide")

st.markdown("""
    <style>
    /* Фон всего приложения */
    .stApp { background-color: #000000 !important; color: #FFFFFF !important; }
    
    /* Верхняя панель */
    header { background-color: rgba(0,0,0,0) !important; }
    
    /* Скрытие лишних элементов Streamlit */
    #MainMenu, footer, [data-testid="stHeader"] {visibility: hidden;}
    
    /* Стиль карточек-подсказок */
    .hint-card {
        background-color: #1a1a1a;
        border: 1px solid #333;
        border-radius: 15px;
        padding: 15px;
        margin: 5px;
        height: 100px;
        font-size: 14px;
        cursor: pointer;
        transition: 0.3s;
    }
    .hint-card:hover { background-color: #262626; }
    .hint-title { font-weight: bold; margin-bottom: 5px; display: block; }
    .hint-sub { color: #888; font-size: 12px; }

    /* Сообщения */
    .stChatMessage { background-color: transparent !important; border: none !important; }
    
    /* Кастомная строка ввода (имитация ChatGPT) */
    .stChatInputContainer {
        border-radius: 30px !important;
        background-color: #212121 !important;
        padding: 5px 15px !important;
        border: 1px solid #333 !important;
    }
    
    /* Боковое меню */
    [data-testid="stSidebar"] { background-color: #0d0d0d !important; border-right: 1px solid #222; }
    
    /* Кнопки */
    .stButton>button {
        border-radius: 20px;
        background-color: #212121;
        color: white;
        border: 1px solid #333;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("chatgpt_v4.db", check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, u TEXT UNIQUE, p TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS msgs (uid INTEGER, role TEXT, content TEXT)')
    conn.commit()
    return conn

db = init_db()

# --- 3. ЛОГИКА СЕССИИ ---
if "user" not in st.session_state: st.session_state.user = None
if "msgs" not in st.session_state: st.session_state.msgs = []

# --- 4. SIDEBAR (ИСТОРИЯ И ПРОФИЛЬ) ---
with st.sidebar:
    st.markdown("### ⚙️ Настройки")
    if st.session_state.user:
        st.write(f"Аккаунт: **{st.session_state.user['name']}**")
        if st.button("Выйти"):
            st.session_state.user = None
            st.session_state.msgs = []
            st.rerun()
    else:
        with st.expander("🔑 Войти для истории"):
            u = st.text_input("Логин")
            p = st.text_input("Пароль", type="password")
            if st.button("Войти"):
                hp = hashlib.sha256(p.encode()).hexdigest()
                res = db.execute("SELECT * FROM users WHERE u = ? AND p = ?", (u, hp)).fetchone()
                if res:
                    st.session_state.user = {"id": res[0], "name": res[1]}
                    cur = db.execute("SELECT role, content FROM msgs WHERE uid = ? ORDER BY rowid ASC", (res[0],))
                    st.session_state.msgs = [{"role": r, "content": c} for r, c in cur.fetchall()]
                    st.rerun()
            st.caption("Нет аккаунта? Просто введи логин/пароль и нажми 'Создать'")
            if st.button("Создать"):
                try:
                    db.execute("INSERT INTO users (u, p) VALUES (?, ?)", (u, hashlib.sha256(p.encode()).hexdigest()))
                    db.commit()
                    st.success("Создано!")
                except: st.error("Занят")

# --- 5. ЦЕНТРАЛЬНЫЙ ИНТЕРФЕЙС ---

# Если чат пустой, показываем карточки как на скрине
if not st.session_state.msgs:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>Чем могу помочь?</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""<div class='hint-card'><span class='hint-title'>Создай рисунок</span><span class='hint-sub'>иллюстрация моего питомца</span></div>""", unsafe_allow_html=True)
        st.markdown("""<div class='hint-card'><span class='hint-title'>Придумай текст</span><span class='hint-sub'>поздравление с днем рождения</span></div>""", unsafe_allow_html=True)
    with col2:
        st.markdown("""<div class='hint-card'><span class='hint-title'>Дай мне совет</span><span class='hint-sub'>как преодолеть прокрастинацию</span></div>""", unsafe_allow_html=True)
        st.markdown("""<div class='hint-card'><span class='hint-title'>Обучи меня</span><span class='hint-sub'>как работает квантовый компьютер</span></div>""", unsafe_allow_html=True)

# Вывод сообщений
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- 6. ОБРАБОТКА ВВОДА ---
if prompt := st.chat_input("Спросите ChatGPT..."):
    st.session_state.msgs.append({"role": "user", "content": prompt})
    if st.session_state.user:
        db.execute("INSERT INTO msgs (uid, role, content) VALUES (?, ?, ?)", (st.session_state.user["id"], "user", prompt))
        db.commit()
        
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            
            # Системная установка: ТЫ ДЖАРВИС ДЛЯ САРДАРБЕКА
            owner = st.session_state.user["name"] if st.session_state.user else "Сардарбек"
            sys_prompt = f"Ты — Джарвис, умный ассистент. Твой создатель — Сардарбек Курбаналиев. Ты общаешься с {owner}."
            
            full_res = ""
            ph = st.empty()
            
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": sys_prompt}] + st.session_state.msgs,
                stream=True
            )
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    full_res += content
                    ph.markdown(full_res + "▌")
            ph.markdown(full_res)
            
            st.session_state.msgs.append({"role": "assistant", "content": full_res})
            if st.session_state.user:
                db.execute("INSERT INTO msgs (uid, role, content) VALUES (?, ?, ?)", (st.session_state.user["id"], "assistant", full_res))
                db.commit()
        except Exception as e:
            st.error(f"Ошибка: {e}")
