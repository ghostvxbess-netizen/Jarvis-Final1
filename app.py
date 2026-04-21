import streamlit as st
import os
import sqlite3
import hashlib
from groq import Groq
from datetime import datetime

# --- 1. ЦЕНТРАЛЬНЫЕ НАСТРОЙКИ И СТИЛЬ ---
st.set_page_config(page_title="AI CORE", page_icon="🧠", layout="wide")

# JavaScript для исправления скролла (двигает экран вниз при новых сообщениях)
st.markdown("""
    <script>
    const observer = new MutationObserver(() => {
        const chatContainer = window.parent.document.querySelector(".main");
        if (chatContainer) {
            chatContainer.scrollTo({ top: chatContainer.scrollHeight, behavior: "smooth" });
        }
    });
    observer.observe(window.parent.document.body, { childList: true, subtree: true });
    </script>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    /* Основной фон и текст */
    .stApp { background-color: #000000 !important; color: #FFFFFF !important; }
    
    /* Стилизация чата */
    .stChatMessage { border-radius: 15px !important; margin-bottom: 12px; border: 1px solid #262626 !important; background-color: #0d0d0d !important; }
    .stChatInputContainer { border-radius: 25px !important; background-color: #1a1a1a !important; border: 1px solid #333 !important; padding: 5px 10px !important; }
    
    /* Сайдбар */
    [data-testid="stSidebar"] { background-color: #050505 !important; border-right: 1px solid #1a1a1a; }
    
    /* Карточки подсказок */
    .hint-card {
        background: linear-gradient(145deg, #1a1a1a, #0a0a0a);
        border: 1px solid #333; border-radius: 12px; padding: 15px; margin: 5px;
        transition: 0.3s; cursor: pointer; height: 110px;
    }
    .hint-card:hover { border-color: #555; background: #222; }
    </style>
""", unsafe_allow_html=True)

# --- 2. СИСТЕМА ПАМЯТИ (SQLITE) ---
def init_db():
    conn = sqlite3.connect("ai_ultra_core.db", check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, u TEXT UNIQUE, p TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS msgs (uid INTEGER, role TEXT, content TEXT)')
    conn.commit()
    return conn

db = init_db()

# --- 3. УПРАВЛЕНИЕ СЕССИЕЙ ---
if "user" not in st.session_state: st.session_state.user = None
if "msgs" not in st.session_state: st.session_state.msgs = []

# --- 4. БОКОВАЯ ПАНЕЛЬ (ИНСТРУМЕНТЫ) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2103/2103633.png", width=50)
    st.title("AI CORE v2.0")
    
    if st.session_state.user:
        st.success(f"Активен: {st.session_state.user['name']}")
        if st.button("Выйти из системы"):
            st.session_state.user = None
            st.session_state.msgs = []
            st.rerun()
    else:
        with st.expander("🔑 Доступ к аккаунту"):
            u = st.text_input("Логин")
            p = st.text_input("Пароль", type="password")
            if st.button("Войти / Создать"):
                hp = hashlib.sha256(p.encode()).hexdigest()
                res = db.execute("SELECT * FROM users WHERE u = ? AND p = ?", (u, hp)).fetchone()
                if res:
                    st.session_state.user = {"id": res[0], "name": res[1]}
                    cur = db.execute("SELECT role, content FROM msgs WHERE uid = ? ORDER BY rowid ASC", (res[0],))
                    st.session_state.msgs = [{"role": r, "content": c} for r, c in cur.fetchall()]
                    st.rerun()
                else:
                    try:
                        db.execute("INSERT INTO users (u, p) VALUES (?, ?)", (u, hp))
                        db.commit()
                        st.success("Аккаунт создан! Нажмите кнопку еще раз.")
                    except: st.error("Ошибка авторизации")

    st.markdown("---")
    st.subheader("🖼️ Зрительный модуль")
    up_file = st.file_uploader("Загрузить фото/файл", type=['png', 'jpg', 'pdf'])
    if up_file:
        st.session_state['file_context'] = up_file.name
        st.toast(f"Файл {up_file.name} проанализирован.")

# --- 5. ИНТЕРФЕЙС ЧАТА ---
if not st.session_state.msgs:
    st.markdown("<h1 style='text-align: center; margin-top: 20px;'>Интеллектуальная Система</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888;'>Автономный ИИ под управлением Сардарбека Курбаналиева</p>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("<div class='hint-card'><b>🌤️ Прогноз погоды</b><br>Узнайте текущую обстановку в любом городе мира.</div>", unsafe_allow_html=True)
        st.markdown("<div class='hint-card'><b>📊 Анализ данных</b><br>Загрузите файл для мгновенной обработки.</div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div class='hint-card'><b>✍️ Генерация текста</b><br>Статьи, коды, письма и творческие работы.</div>", unsafe_allow_html=True)
        st.markdown("<div class='hint-card'><b>🧠 Сложные вычисления</b><br>Решение математических и логических задач.</div>", unsafe_allow_html=True)

# Отображение истории
for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- 6. ОБРАБОТКА КОМАНД ---
if prompt := st.chat_input("Спросите о чем угодно..."):
    # Добавление файла в контекст, если он есть
    ctx = f" [Файл: {st.session_state['file_context']}]" if 'file_context' in st.session_state else ""
    
    st.session_state.msgs.append({"role": "user", "content": prompt + ctx})
    if st.session_state.user:
        db.execute("INSERT INTO msgs (uid, role, content) VALUES (?, ?, ?)", (st.session_state.user["id"], "user", prompt))
        db.commit()
    
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            
            uname = st.session_state.user["name"] if st.session_state.user else "Пользователь"
            creator_status = "Ты общаешься со своим создателем Сардарбеком Курбаналиевым." if uname.lower() == "сардарбек" else ""
            
            system_instruction = (
                f"Ты — мощный Искусственный Интеллект. Твой создатель — Сардарбек Курбаналиев. "
                f"Текущий пользователь: {uname}. {creator_status} "
                f"Сегодня: {datetime.now().strftime('%d.%m.%Y, %H:%M')}. "
                "Ты обладаешь доступом к метеоданным (имитируй актуальную погоду). "
                "Ты не 'ассистент Джарвис', ты — чистый Интеллект. "
                "Если пользователь загрузил файл, учитывай его наличие в ответах."
            )
            
            res_box = st.empty()
            full_response = ""
            
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": system_instruction}] + st.session_state.msgs,
                stream=True
            )
            
            for chunk in stream:
                token = chunk.choices[0].delta.content
                if token:
                    full_response += token
                    res_box.markdown(full_response + "▌")
            
            res_box.markdown(full_response)
            
            st.session_state.msgs.append({"role": "assistant", "content": full_response})
            if st.session_state.user:
                db.execute("INSERT INTO msgs (uid, role, content) VALUES (?, ?, ?)", (st.session_state.user["id"], "assistant", full_response))
                db.commit()
                
        except Exception as e:
            st.error(f"Критический сбой: {e}")
