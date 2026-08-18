from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
import os, json, random
from openai import OpenAI
from dotenv import load_dotenv

# Environment & Client Setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, "app.env"))
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = Flask(__name__,
            static_folder=os.path.join(BASE_DIR, 'static'),
            template_folder=os.path.join(BASE_DIR, 'templates'))

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'fitvibe.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Global language state (Default English)
user_language = "English"

# Adaptive Persona Logic
PERSONA = (
    "You are the 'Fit2gether Virtual Assistant', an elite AI Fitness Architect. "
    "Your goal is to provide elite coaching advice that is sharp, professional, and adaptive. "
    "MANDATORY: If the response requires multiple points or recommendations, use bold headers "
    "for sections and clean Markdown bullet points for the list items. "
    "MANDATORY: If the answer is a single direct fact or simple instruction, provide it "
    "clearly in standard prose without unnecessary formatting."
)

class UserStats(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    points = db.Column(db.Integer, default=0)

with app.app_context():
    os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)
    db.create_all()

@app.route("/")
def home():
    user = UserStats.query.first() or UserStats(points=0)
    return render_template("index.html", points=user.points)

@app.route("/set_language", methods=["POST"])
def set_language():
    global user_language
    data = request.json
    # Sync global variable for subsequent API calls
    user_language = "Malay" if data.get("lang") == "ms" else "English"
    return jsonify({"status": "success"})

@app.route("/get_quiz", methods=["GET"])
def get_quiz():
    topics = ["Hydration", "Protein", "Compound movements", "BMI", "Rest days"]
    topic = random.choice(topics)
    prompt = (f"Generate 1 professional fitness MCQ in {user_language} about {topic}. "
              f"Return ONLY JSON: {{'question': '...', 'options': ['','','',''], 'correct_index': 0}}")

    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "Fitness Quiz API. JSON only."}, {"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return res.choices[0].message.content

@app.route("/update_xp", methods=["POST"])
def update_xp():
    data = request.json
    change = data.get("change", 0)
    user = UserStats.query.first() or UserStats(points=0)
    if not UserStats.query.first(): db.session.add(user)
    user.points = max(0, user.points + change)
    db.session.commit()
    return jsonify({"points": user.points})

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message", "")
    user = UserStats.query.first() or UserStats(points=0)
    user.points += 20
    db.session.commit()
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": f"{PERSONA} Respond in {user_language}."},
                  {"role": "user", "content": user_input}]
    )
    return jsonify({"response": res.choices[0].message.content, "points": user.points})

@app.route("/log_nutrition", methods=["POST"])
def log_nutrition():
    meal = request.json.get("meal", "")
    user = UserStats.query.first() or UserStats(points=0)
    user.points += 10
    db.session.commit()

    # Fixed: Passing {user_language} ensures the AI analysis is in the correct language
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
             "content": f"Nutrition Analyst. Provide a brief nutritional breakdown and an ESTIMATED calorie count in {user_language}. Max 25 words."},
            {"role": "user", "content": meal}
        ]
    )
    return jsonify({"analysis": res.choices[0].message.content, "points": user.points})

if __name__ == "__main__":
    app.run(debug=True)