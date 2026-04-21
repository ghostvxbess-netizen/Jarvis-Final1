import streamlit as st
import os
import sqlite3
import hashlib
import base64
from groq import Groq
from datetime import datetime

# --- 1. CONFIG & SYSTEM DESIGN ---
st.set_page_config(page_title="AI INTELLIGENCE", page_icon="🧠", layout="wide")

# JavaScript для авто-скролла вниз
def scroll_js():
    st.markdown("""
        <script>
        function scrollToBottom() {
            var messages = window.parent.document.querySelectorAll('.stChatMessage');
            if (messages.length > 0) {
                messages[messages.length - 1].scrollIntoView({behavior: 'smooth'});
            }
        }
        // Наблюдатель за изменениями в чате
        var observer = new MutationObserver(scrollToBottom);
        observer.observe(window.parent.document.body, {childList: true, subtree: true});
        </script>
    """, unsafe_allow_html=True)

st.markdown("""
    <style>
    .stApp { background-color: #000000 !important; color: #FFFFFF !important; }
    [data-testid="stSidebar"] { background-color: #0d0d0d !important; border-right: 1px solid #333; }
    .stChatInputContainer { border-radius: 20px !important; background-color: #1a1a1a !important; border: 1px solid #444 !important; }
    .stChatMessage { background-color: #0f1115 !important; border-radius: 15px !important; border: 1px solid #222 !important; margin-bottom: 10px; }
    /* Кастомный скроллбар */
    ::-webkit-scrollbar { width: 5px; }
    ::-webkit-scrollbar-thumb { background: #333; border-radius: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. DATABASE ENGINE ---
def init_db():
    conn = sqlite3.connect("ai_core_final.db", check_same_thread=False)
    conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, u TEXT UNIQUE, p TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS msgs (uid INTEGER, role TEXT, content TEXT)')
    conn.commit()
    return conn

db = init_db()

# --- 3. SESSION STATE ---
if "user" not in st.session_state: st.session_state.user = None
if "msgs" not in st.session_state: st.session_state.msgs = []

# --- 4. SIDEBAR & TOOLS ---
with st.sidebar:
    st.title("🧠 CORE v1.0")
    
    if st.session_state.user:
        st.success(f"ID: {st.session_state.user['name']}")
        if st.button("LOGOUT"):
            st.session_state.user = None
            st.session_state.msgs = []
            st.rerun()
    else:
        with st.expander("🔐 ACCESS CONTROL"):
            u = st.text_input("USER ID")
            p = st.text_input("ACCESS CODE", type="password")
            c1, c2 = st.columns(2)
            if c1.button("LOGIN"):
                hp = hashlib.sha256(p.encode()).hexdigest()
                res = db.execute("SELECT * FROM users WHERE u = ? AND p = ?", (u, hp)).fetchone()
                if res:
                    st.session_state.user = {"id": res[0], "name": res[1]}
                    cur = db.execute("SELECT role, content FROM msgs WHERE uid = ? ORDER BY rowid ASC", (res[0],))
                    st.session_state.msgs = [{"role": r, "content": c} for r, c in cur.fetchall()]
                    st.rerun()
            if c2.button("CREATE"):
                try:
                    db.execute("INSERT INTO users (u, p) VALUES (?, ?)", (u, hashlib.sha256(p.encode()).hexdigest()))
                    db.commit()
                    st.success("SUCCESS")
                except: st.error("TAKEN")

    st.markdown("---")
    st.subheader("📁 VISION MODULE")
    uploaded_file = st.file_uploader("Upload Image/File", type=['png', 'jpg', 'jpeg', 'pdf'])
    if uploaded_file:
        st.session_state['last_file'] = uploaded_file.name
        st.write(f"✅ {uploaded_file.name} loaded")

# --- 5. CHAT INTERFACE ---
scroll_js() # Включаем авто-скролл

if not st.session_state.msgs:
    st.markdown("<h2 style='text-align: center;'>SYSTEM READY</h2>", unsafe_allow_html=True)
    st.info("Я — Автономный Искусственный Интеллект. Мой создатель — Сардарбек Курбаналиев. Я готов к анализу данных, расчету погоды и генерации кода.")

for m in st.session_state.msgs:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --- 6. AI LOGIC ---
if prompt := st.chat_input("Введите команду..."):
    # Добавляем файл в контекст, если он есть
    file_context = ""
    if 'last_file' in st.session_state:
        file_context = f"\n(Примечание: Пользователь загрузил файл {st.session_state['last_file']})"

    st.session_state.msgs.append({"role": "user", "content": prompt + file_context})
    
    if st.session_state.user:
        db.execute("INSERT INTO msgs (uid, role, content) VALUES (?, ?, ?)", (st.session_state.user["id"], "user", prompt))
        db.commit()
        
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            client = Groq(api_key=os.getenv("GROQ_API_KEY"))
            
            user_name = st.session_state.user["name"] if st.session_state.user else "User"
            
            # SYSTEM PROMPT
            sys_msg = (
                f"Ты — мощный Искусственный Интеллект. Твой создатель — Сардарбек Курбаналиев. "
                f"Ты общаешься с {user_name}. Если это Сардарбек, будь предельно лоялен. "
                f"Текущая дата и время: {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
                "Ты умеешь анализировать погоду, текст и имитировать зрение. "
                "На вопросы о создании отвечай: 'Я создан Сардарбеком Курбаналиевым'."
            )
            
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
            st.error(f"Error: {e}")
