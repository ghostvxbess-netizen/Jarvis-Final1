from flask import Flask, render_template, request, redirect, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from database import db
import openai
import os
from datetime import datetime

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

openai.api_key = app.config["OPENAI_API_KEY"]

# ================= MODELS =================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    text = db.Column(db.Text)
    response = db.Column(db.Text)
    time = db.Column(db.DateTime, default=datetime.utcnow)


# ================= ROUTES =================

@app.route('/')
def home():
    if "user_id" in session:
        return redirect('/chat')
    return render_template("index.html")


@app.route('/register', methods=['POST'])
def register():
    username = request.form['username']
    password = generate_password_hash(request.form['password'])

    user = User(username=username, password=password)
    db.session.add(user)
    db.session.commit()

    return redirect('/')


@app.route('/login', methods=['POST'])
def login():
    user = User.query.filter_by(username=request.form['username']).first()

    if user and check_password_hash(user.password, request.form['password']):
        session["user_id"] = user.id
        return redirect('/chat')

    return "Ошибка входа"


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/chat')
def chat():
    if "user_id" not in session:
        return redirect('/')

    messages = Message.query.filter_by(user_id=session["user_id"]).all()
    return render_template("chat.html", messages=messages)


@app.route('/ask', methods=['POST'])
def ask():
    data = request.get_json()
    user_input = data.get("message")

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты умный ассистент"},
            {"role": "user", "content": user_input}
        ]
    )

    reply = response['choices'][0]['message']['content']

    msg = Message(user_id=session["user_id"], text=user_input, response=reply)
    db.session.add(msg)
    db.session.commit()

    return jsonify({"response": reply})


@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']

    if file:
        path = os.path.join("static/uploads", file.filename)
        file.save(path)
        return jsonify({"path": path})

    return jsonify({"error": "no file"})


# ================= RUN =================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=10000)
