“””
app.py — Джарвис v3.0
Исправления: PDF поддержка, мобильный UX, стабильный синтаксис.
“””
import os
import base64
import io
import zipfile
from pathlib import Path

import streamlit as st
from groq import Groq

import config
from styles import get_css, PWA_JS, CHAT_JS

# ── Конфигурация страницы ─────────────────────────────────────

st.set_page_config(
page_title=config.APP_TITLE,
page_icon=config.APP_ICON,
layout=“centered”,
initial_sidebar_state=“collapsed”,
)
st.markdown(PWA_JS, unsafe_allow_html=True)

# ── Groq клиент ───────────────────────────────────────────────

@st.cache_resource
def get_groq() -> Groq:
key = config.GROQ_API_KEY
if not key:
st.error(
“**GROQ_API_KEY не задан.**\n\n”
“Replit: Secrets → GROQ_API_KEY\n”
“ПК: `export GROQ_API_KEY=gsk_...`\n”
“Получить бесплатно: https://console.groq.com”
)
st.stop()
return Groq(api_key=key)

def ask_jarvis(
messages: list,
img_b64: str = None,
img_mime: str = None,
) -> str:
“”“Отправляет запрос в Groq и возвращает ответ.”””
client = get_groq()
context = [{“role”: “system”, “content”: config.SYSTEM_PROMPT}]
context += messages[-config.MAX_CONTEXT:]

```
if img_b64:
    last = context[-1]
    user_text = last.get("content", "Опиши что изображено.")
    context[-1] = {
        "role": "user",
        "content": [
            {"type": "text", "text": user_text},
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img_mime};base64,{img_b64}"
                },
            },
        ],
    }
    for model in [config.VISION_MODEL, config.VISION_FALLBACK]:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=context,
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
            )
            return resp.choices[0].message.content
        except Exception:
            continue
    return (
        "⚠️ Vision-модели временно недоступны. "
        "Опишите изображение текстом, сэр."
    )

for model in [config.TEXT_MODEL, config.TEXT_FAST]:
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=context,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
        )
        return resp.choices[0].message.content
    except Exception:
        continue

return (
    "⚠️ Groq API временно недоступен. "
    "Повторите запрос через несколько секунд, сэр."
)
```

# ── Сессия ────────────────────────────────────────────────────

def init_session():
defaults = {
“messages”:    [],
“pending_img”: None,
“pending_pdf”: None,
“theme”:       “dark”,
“_inject”:     None,
}
for key, val in defaults.items():
if key not in st.session_state:
st.session_state[key] = val

# ── Обработка файлов ──────────────────────────────────────────

MIME_MAP = {
“jpg”:  “image/jpeg”,
“jpeg”: “image/jpeg”,
“png”:  “image/png”,
“webp”: “image/webp”,
“gif”:  “image/gif”,
}

def store_image(file) -> None:
data = file.read()
ext  = file.name.rsplit(”.”, 1)[-1].lower()
mime = MIME_MAP.get(ext, “image/jpeg”)
st.session_state[“pending_img”] = {
“b64”:  base64.b64encode(data).decode(),
“mime”: mime,
“name”: file.name,
}

def pdf_to_images_b64(pdf_bytes: bytes) -> list[dict]:
“””
Конвертирует PDF в список base64-изображений (по странице).
Использует PyMuPDF если доступен, иначе fallback на текст.
“””
try:
import fitz  # PyMuPDF
doc = fitz.open(stream=pdf_bytes, filetype=“pdf”)
pages = []
max_pages = min(len(doc), config.PDF_MAX_PAGES)
for i in range(max_pages):
page = doc.load_page(i)
mat  = fitz.Matrix(config.PDF_DPI / 72, config.PDF_DPI / 72)
pix  = page.get_pixmap(matrix=mat)
img_bytes = pix.tobytes(“jpeg”)
b64 = base64.b64encode(img_bytes).decode()
pages.append({“b64”: b64, “mime”: “image/jpeg”, “index”: i + 1})
doc.close()
return pages
except ImportError:
return []

def extract_pdf_text(pdf_bytes: bytes) -> str:
“”“Извлекает текст из PDF через PyMuPDF или pypdf.”””
try:
import fitz
doc  = fitz.open(stream=pdf_bytes, filetype=“pdf”)
text = “”
for i in range(min(len(doc), config.PDF_MAX_PAGES)):
text += f”\n— Страница {i+1} —\n”
text += doc.load_page(i).get_text()
doc.close()
return text.strip()
except ImportError:
pass
try:
from pypdf import PdfReader
reader = PdfReader(io.BytesIO(pdf_bytes))
text = “”
for i, page in enumerate(reader.pages[:config.PDF_MAX_PAGES]):
text += f”\n— Страница {i+1} —\n”
text += page.extract_text() or “”
return text.strip()
except Exception:
return “”

def store_pdf(file) -> None:
“”“Сохраняет PDF и конвертирует в изображения или текст.”””
data   = file.read()
pages  = pdf_to_images_b64(data)
text   = extract_pdf_text(data) if not pages else “”
st.session_state[“pending_pdf”] = {
“name”:   file.name,
“pages”:  pages,   # список изображений
“text”:   text,    # fallback — просто текст
“n_pages”: len(pages) if pages else “?”,
}

# ── ZIP скачивание ────────────────────────────────────────────

def build_zip() -> bytes:
root  = Path(**file**).parent
files = [
“app.py”, “config.py”, “styles.py”,
“requirements.txt”,
]
buf = io.BytesIO()
with zipfile.ZipFile(buf, “w”, zipfile.ZIP_DEFLATED) as zf:
for fname in files:
fpath = root / fname
if fpath.exists():
zf.write(fpath, fname)
return buf.getvalue()

# ── Сайдбар ───────────────────────────────────────────────────

def render_sidebar():
with st.sidebar:
st.markdown(
“<h2 style='"
"font-family:var(--mono,monospace);"
"font-size:1rem;"
"letter-spacing:0.1em;"
"margin:0 0 4px"
"'>”
“<span style='color:var(--accent,#4F8EF7)'>⚡</span>”
f” JARVIS v{config.VERSION}”
“</h2>”,
unsafe_allow_html=True,
)
st.caption(“Персональный ИИ-ассистент”)
st.divider()

```
    theme_val = st.radio(
        "Тема",
        ["🌙 Тёмная", "☀️ Светлая"],
        index=0 if st.session_state.get("theme", "dark") == "dark" else 1,
        horizontal=True,
        key="theme_radio",
    )
    new_theme = "dark" if "Тёмная" in theme_val else "light"
    if st.session_state.get("theme") != new_theme:
        st.session_state["theme"] = new_theme
        st.rerun()

    st.divider()

    if st.button("🗑 Очистить историю", use_container_width=True):
        st.session_state["messages"]    = []
        st.session_state["pending_img"] = None
        st.session_state["pending_pdf"] = None
        st.rerun()

    st.divider()
    st.caption("**Скачать проект**")
    st.download_button(
        label="📦 jarvis_project.zip",
        data=build_zip(),
        file_name="jarvis_project.zip",
        mime="application/zip",
        use_container_width=True,
    )
    st.divider()

    with st.expander("⚙ Конфигурация"):
        st.code(
            f"Модель:   {config.TEXT_MODEL}\n"
            f"Vision:   {config.VISION_MODEL}\n"
            f"Контекст: {config.MAX_CONTEXT} сообщ.\n"
            f"Токены:   {config.MAX_TOKENS}\n"
            f"PDF стр.: {config.PDF_MAX_PAGES}",
            language=None,
        )
        st.caption("Изменяется в `config.py`")

    msg_count = len(st.session_state.get("messages", []))
    if msg_count:
        with st.expander(f"📊 Сессия ({msg_count // 2} обменов)"):
            u = sum(
                1 for m in st.session_state["messages"]
                if m["role"] == "user"
            )
            st.markdown(f"• Запросов: **{u}**")
            st.markdown(f"• Ответов: **{msg_count - u}**")

    st.divider()
    st.caption(
        f"Jarvis AI · Groq × Llama\n"
        f"© {config.OWNER_NAME}"
    )
```

# ── Отправка сообщения ────────────────────────────────────────

def send_message(text: str):
st.session_state[”_inject”] = text
st.rerun()

# ── Основной чат ──────────────────────────────────────────────

def show_chat():
theme = st.session_state.get(“theme”, “dark”)
msgs  = st.session_state.get(“messages”, [])

```
render_sidebar()
st.markdown(get_css(theme), unsafe_allow_html=True)
st.markdown(CHAT_JS, unsafe_allow_html=True)

# ── Загрузка фото ────────────────────────────────────────
col_img, col_pdf = st.columns(2)

with col_img:
    uploaded_img = st.file_uploader(
        "📷 Фото",
        type=list(MIME_MAP.keys()),
        key="fu_img",
        label_visibility="visible",
    )
    if uploaded_img:
        pimg = st.session_state.get("pending_img") or {}
        if pimg.get("name") != uploaded_img.name:
            store_image(uploaded_img)
            st.rerun()

# ── Загрузка PDF ─────────────────────────────────────────
with col_pdf:
    uploaded_pdf = st.file_uploader(
        "📄 PDF",
        type=["pdf"],
        key="fu_pdf",
        label_visibility="visible",
    )
    if uploaded_pdf:
        ppdf = st.session_state.get("pending_pdf") or {}
        if ppdf.get("name") != uploaded_pdf.name:
            with st.spinner("Обрабатываю PDF…"):
                store_pdf(uploaded_pdf)
            st.rerun()

# ── Превью прикреплённых файлов ──────────────────────────
pimg = st.session_state.get("pending_img")
if pimg:
    c1, c2 = st.columns([5, 1])
    with c1:
        st.image(
            f"data:{pimg['mime']};base64,{pimg['b64']}",
            width=160,
        )
    with c2:
        if st.button("✕", key="rm_img"):
            st.session_state["pending_img"] = None
            st.rerun()

ppdf = st.session_state.get("pending_pdf")
if ppdf:
    c1, c2 = st.columns([5, 1])
    with c1:
        n = ppdf.get("n_pages", "?")
        st.info(
            f"📄 **{ppdf['name']}** · {n} стр. готово к анализу"
        )
    with c2:
        if st.button("✕", key="rm_pdf"):
            st.session_state["pending_pdf"] = None
            st.rerun()

# ── Пустой экран — hero + карточки ───────────────────────
if not msgs:
    st.markdown(
        '<div class="jv-hero">'
        '<div class="jv-badge">NEURAL AI · GROQ × LLAMA</div>'
        '<div class="jv-logo">JAR<span>V</span>IS</div>'
        '<p class="jv-sub">'
        "Персональный ИИ-ассистент нового поколения.<br>"
        "Задайте вопрос или выберите подсказку ниже."
        "</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, (title, sub) in enumerate(config.SUGGEST_CARDS):
        with cols[i % 2]:
            if st.button(
                f"**{title}**\n{sub}",
                key=f"card_{i}",
                use_container_width=True,
            ):
                send_message(f"{title}: {sub}")
else:
    for msg in msgs:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ── Быстрые чипы ─────────────────────────────────────────
cols = st.columns(len(config.CHIPS))
for i, (label, cmd) in enumerate(config.CHIPS):
    with cols[i]:
        if st.button(label, key=f"chip_{i}", use_container_width=True):
            if cmd == "__clear__":
                st.session_state["messages"]    = []
                st.session_state["pending_img"] = None
                st.session_state["pending_pdf"] = None
                st.rerun()
            else:
                send_message(cmd)

# ── Поле ввода ────────────────────────────────────────────
injected = st.session_state.pop("_inject", None)
prompt   = injected or st.chat_input(config.PLACEHOLDER)

if prompt:
    pi   = st.session_state.get("pending_img")
    pd_f = st.session_state.get("pending_pdf")

    # Показываем сообщение пользователя
    with st.chat_message("user"):
        if pi:
            st.image(
                f"data:{pi['mime']};base64,{pi['b64']}",
                width=160,
            )
        if pd_f:
            st.caption(f"📄 {pd_f['name']}")
        st.markdown(prompt)

    st.session_state["messages"].append(
        {"role": "user", "content": prompt}
    )

    # Определяем что передавать в API
    ib64  = None
    imime = None

    if pi:
        ib64  = pi["b64"]
        imime = pi["mime"]
        st.session_state["pending_img"] = None
    elif pd_f:
        pages = pd_f.get("pages", [])
        if pages:
            # Первая страница как изображение для Vision
            ib64  = pages[0]["b64"]
            imime = pages[0]["mime"]
            # Если несколько страниц — добавим текст в промпт
            if len(pages) > 1:
                extra = (
                    f"\n\n[PDF: {pd_f['name']}, "
                    f"{len(pages)} стр. — показана стр. 1]"
                )
                msgs_with_ctx = list(
                    st.session_state["messages"]
                )
                msgs_with_ctx[-1]["content"] += extra
                st.session_state["messages"] = msgs_with_ctx
        elif pd_f.get("text"):
            # Fallback: текстовый режим
            text_ctx = (
                f"\n\n[Содержимое PDF '{pd_f['name']}':"
                f"\n{pd_f['text'][:3000]}]"
            )
            msgs2 = list(st.session_state["messages"])
            msgs2[-1]["content"] += text_ctx
            st.session_state["messages"] = msgs2
        st.session_state["pending_pdf"] = None

    # Показываем ответ
    with st.chat_message("assistant"):
        slot = st.empty()
        slot.markdown(
            '<div class="jv-typing">'
            "<span></span><span></span><span></span>"
            "</div>",
            unsafe_allow_html=True,
        )
        try:
            reply = ask_jarvis(
                st.session_state["messages"],
                ib64,
                imime,
            )
        except Exception as e:
            reply = (
                f"⚠️ Ошибка API: `{e}`\n\n"
                "Проверьте GROQ_API_KEY и подключение."
            )
        slot.markdown(reply)

    st.session_state["messages"].append(
        {"role": "assistant", "content": reply}
    )
    st.rerun()
```

# ── Точка входа ───────────────────────────────────────────────

def main():
init_session()
show_chat()

if **name** == “**main**”:
main()
