print("--- 1. STARTING PYTHON SERVER ---")
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import datetime
import requests
from openai import OpenAI
import json
import random
import os
from dotenv import load_dotenv

# Translation Libraries
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# DB Config
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# API Keys
OPENAI_API_KEY_SECURE = os.getenv('OPENAI_API_KEY') 
ICD_CLIENT_ID = 'c4f58ec7-9f5e-4d15-b638-71de5ff51103_9c73e6ca-0cfa-4c3e-a635-6c44c2f9ffed'
ICD_CLIENT_SECRET = 'dyPIp9AacFq8D7YU6tAluIBEHIglwTajELzscG6/EYQ='

try:
    client_ai = OpenAI(api_key=OPENAI_API_KEY_SECURE)
except:
    client_ai = None

# --- DATABASE MODELS (Kept Same) ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), default='individual')
    specialization = db.Column(db.String(100), nullable=True)
    hospitalName = db.Column(db.String(100), nullable=True)
    address = db.Column(db.String(200), nullable=True)
    timings = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(100), default='Bhopal')

class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patientName = db.Column(db.String(100))
    doctorName = db.Column(db.String(100))
    date = db.Column(db.String(50))
    time = db.Column(db.String(50))
    disease = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    status = db.Column(db.String(50), default='Confirmed')
    userEmail = db.Column(db.String(100)) 
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

with app.app_context():
    db.create_all()

# --- SMART TRANSLATION HELPERS ---

def detect_and_translate_input(text):
    try:
        lang = detect(text)
        # If it's not English, translate it to English so we can search our DB
        if lang != 'en':
            translated_text = GoogleTranslator(source='auto', target='en').translate(text)
            return lang, translated_text
        return 'en', text
    except:
        return 'en', text

def smart_translate_response(data, target_lang):
    """
    Uses OpenAI for high-quality medical translation if available.
    Falls back to Google Translate for basic literal translation.
    """
    if target_lang == 'en': 
        return data

    # 1. Try OpenAI (Best Quality for Medical Context)
    if client_ai:
        try:
            # We ask GPT to translate the JSON values but keep the keys/structure intact
            prompt = f"""
            Translate the values of this JSON object into the language code '{target_lang}'.
            Maintain the exact JSON structure. 
            Ensure medical terms are translated accurately and professionally (not literally).
            
            JSON:
            {json.dumps(data)}
            """
            gpt_call = client_ai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            translated_json = json.loads(gpt_call.choices[0].message.content)
            return translated_json
        except Exception as e:
            print(f"OpenAI Translation Failed: {e}")
            # Fall through to Google Translate

    # 2. Google Translate Fallback (Literal)
    translator = GoogleTranslator(source='en', target=target_lang)
    def t(val):
        if isinstance(val, str) and val:
            try: return translator.translate(val)
            except: return val
        if isinstance(val, list):
            return [translator.translate(v) for v in val]
        return val

    try:
        translated_data = {}
        for key, value in data.items():
            if key in ['codes', 'id', 'risk']: 
                translated_data[key] = value
            elif isinstance(value, dict):
                translated_data[key] = smart_translate_response(value, target_lang)
            else:
                translated_data[key] = t(value)
        return translated_data
    except:
        return data

def get_icd_token():
    # (Same token logic)
    return None 

# --- STANDARD ROUTES (Login, Register, etc.) ---
@app.route('/health', methods=['GET'])
def health_check(): return jsonify({"status": "ok"}), 200

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(email=data['email']).first(): return jsonify({"message": "User exists", "success": False}), 400
    new_user = User(name=data['name'], email=data['email'], password=data['password'], role=data.get('role', 'individual'), specialization=data.get('specialization'), hospitalName=data.get('hospitalName'), address=data.get('address'), timings=data.get('timings'))
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Success", "success": True})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and user.password == data['password']:
        return jsonify({"message": "Success", "success": True, "user": {"name": user.name, "role": user.role, "email": user.email}})
    return jsonify({"message": "Invalid", "success": False}), 401

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    doctors = User.query.filter_by(role='doctor').all()
    return jsonify([{"id": d.id, "name": d.name, "specialization": d.specialization, "hospitalName": d.hospitalName, "address": d.address, "timings": d.timings, "email": d.email} for d in doctors])

@app.route('/api/book-appointment', methods=['POST'])
def book_appointment():
    data = request.json
    db.session.add(Appointment(patientName=data['patientName'], doctorName=data['doctorName'], date=data['date'], time=data['time'], disease=data['disease'], phone=data['phone'], userEmail=data['userEmail']))
    db.session.commit()
    return jsonify({"message": "Success", "success": True})

@app.route('/api/update-appointment-status', methods=['POST'])
def update_appointment_status():
    data = request.json
    appt = Appointment.query.get(data.get('id'))
    if appt:
        appt.status = data.get('status')
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/update-doctor-profile', methods=['POST'])
def update_doctor_profile():
    data = request.json
    user = User.query.filter_by(name=data['name']).first()
    if user:
        user.specialization = data.get('specialization')
        user.hospitalName = data.get('hospitalName')
        user.address = data.get('address')
        user.timings = data.get('timings')
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False})

@app.route('/api/dashboard-stats', methods=['POST'])
def dashboard_stats():
    data = request.json
    user_role = data.get('role')
    user_email = data.get('email')
    stats = {"active_doctors_count": 0, "active_doctors_list": [], "active_appointment": None, "past_appointments": [], "total_app_count": 0, "all_appointments": [], "doctor_active_appts": [], "patient_records": [], "efficacy_stats": {"success": 0, "missed": 0, "total": 0}, "system_health": {"status": "Operational", "uptime": "100%", "database": "Connected"}}
    
    doctors = User.query.filter_by(role='doctor').all()
    doc_list = [{"id": d.id, "name": d.name, "specialization": d.specialization, "location": "Bhopal"} for d in doctors]
    stats["active_doctors_count"] = len(doc_list)
    stats["active_doctors_list"] = doc_list

    if user_role == 'individual':
        my_appts = Appointment.query.filter_by(userEmail=user_email).order_by(Appointment.created_at.desc()).all()
        stats["total_app_count"] = len(my_appts)
        for appt in my_appts: stats["past_appointments"].append({"doctorName": appt.doctorName, "date": appt.date, "time": appt.time, "disease": appt.disease, "status": appt.status})
        active = next((a for a in my_appts if a.status == 'Confirmed'), None)
        if active: stats["active_appointment"] = {"doctor": active.doctorName, "time": active.time, "date": active.date, "disease": active.disease}
    elif user_role == 'doctor':
        current_user = User.query.filter_by(email=user_email).first()
        if current_user:
            doc_appts = Appointment.query.filter_by(doctorName=current_user.name).order_by(Appointment.created_at.desc()).all()
            for appt in doc_appts:
                if appt.status == 'Confirmed': stats["doctor_active_appts"].append({"id": appt.id, "patient_name": appt.patientName, "disease": appt.disease, "time": appt.time, "date": appt.date, "phone": appt.phone})
                stats["patient_records"].append({"patient": appt.patientName, "doctor": appt.doctorName, "date": appt.date, "feedback": random.choice(["Good", "Satisfied"])})
            success = Appointment.query.filter_by(doctorName=current_user.name, status='Successful').count()
            missed = Appointment.query.filter_by(doctorName=current_user.name, status='Not Appeared').count()
            stats["efficacy_stats"] = {"success": success, "missed": missed, "total": success+missed}
    else:
        all_appts = Appointment.query.order_by(Appointment.created_at.desc()).all()
        for appt in all_appts: stats["all_appointments"].append({"id": appt.id, "patient_name": appt.patientName, "doctor_name": appt.doctorName, "status": appt.status, "disease": appt.disease}); stats["patient_records"].append({"patient": appt.patientName, "doctor": appt.doctorName, "date": appt.date, "feedback": "Recorded"})
    return jsonify({"success": True, "stats": stats})

# --- 8. MULTILINGUAL DISEASE SEARCH ---
@app.route('/api/search-disease', methods=['POST'])
def search_disease():
    raw_query = request.json.get('query', '').strip()
    
    # 1. Detect Language & Translate to English (if needed)
    user_lang, query = detect_and_translate_input(raw_query)
    query = query.lower()
    
    print(f"🔎 User Lang: {user_lang} | Searching for: {query}")

    # ROBUST ENGLISH BACKUP DB
    backup_db = {
        "asthma": { 
            "name": "Asthma", 
            "specialist": "Pulmonologist", 
            "codes": {"icd11": "CA23", "namaste": "TM2-R-008"}, 
            "description": "A chronic condition affecting the airways in the lungs, causing wheezing and tightness.", 
            "carePlan": { 
                "symptoms": ["Wheezing", "Shortness of breath", "Chest tightness"], 
                "diet": ["Ginger tea", "Warm fluids", "Avoid dairy"], 
                "exercise": ["Walking", "Breathing exercises"], 
                "yoga": ["Pranayama", "Sukhasana"] 
            } 
        },
        "diabetes": { 
            "name": "Diabetes Mellitus", 
            "specialist": "Endocrinologist", 
            "codes": {"icd11": "5A11", "namaste": "TM2-E-034"}, 
            "description": "A metabolic disease causing high blood sugar levels.", 
            "carePlan": { 
                "symptoms": ["Increased thirst", "Frequent urination", "Fatigue"], 
                "diet": ["Leafy greens", "Bitter gourd", "Avoid sugar"], 
                "exercise": ["Brisk walking", "Cycling"], 
                "yoga": ["Mandukasana", "Surya Namaskar"] 
            } 
        },
        "migraine": { 
            "name": "Migraine", 
            "specialist": "Neurologist", 
            "codes": {"icd11": "8A80", "namaste": "TM2-N-012"}, 
            "description": "Intense, debilitating headaches often with nausea.", 
            "carePlan": { 
                "symptoms": ["Throbbing pain", "Nausea", "Sensitivity to light"], 
                "diet": ["Magnesium rich foods", "Hydration"], 
                "exercise": ["Gentle stretching"], 
                "yoga": ["Shishuasana", "Setu Bandhasana"] 
            } 
        },
        "viral fever": { 
            "name": "Viral Fever", 
            "specialist": "General Physician", 
            "codes": {"icd11": "MG26", "namaste": "TM2-J-005"}, 
            "description": "Acute viral infection characterized by high body temperature.", 
            "carePlan": { 
                "symptoms": ["Fever", "Chills", "Body ache"], 
                "diet": ["Soup", "Herbal tea", "Light meals"], 
                "exercise": ["Rest is recommended"], 
                "yoga": ["Shavasana"] 
            } 
        }
    }

    result_data = None

    # 2. Find in Backup (Using English Query)
    for key in backup_db:
        if key in query:
            result_data = backup_db[key]
            break
    
    # 3. Fallback to OpenAI if not in backup
    if not result_data and client_ai:
        try:
            prompt = f"Provide Ayurvedic medical summary for '{query}'. Return JSON: name, specialist, codes(icd11, namaste), description, carePlan(symptoms, diet, exercise, yoga)."
            gpt = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            result_data = json.loads(gpt.choices[0].message.content)
        except: pass

    # 4. TRANSLATE BACK (The Magic Step)
    if result_data:
        # If user asked in Hindi, translate the ENGLISH result into HINDI
        if user_lang != 'en':
            result_data = smart_translate_response(result_data, user_lang)
        
        return jsonify({"success": True, "data": result_data})
    
    return jsonify({"success": False, "message": "Disease not found."})

# --- 9. MULTILINGUAL SYMPTOM ANALYZER ---
@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    raw_symptoms = request.json.get('symptoms', '').strip()
    
    # 1. Detect & Translate to English
    user_lang, symptoms = detect_and_translate_input(raw_symptoms)
    symptoms = symptoms.lower()
    
    smart_diagnosis = [
        {"keywords": ["headache", "nausea", "light", "head"], "disease": "Migraine", "risk": "Moderate", "specialty": "Neurologist", "advice": "Rest in a dark room, hydrate."},
        {"keywords": ["chest", "heart", "squeeze", "breath"], "disease": "Cardiac Issue", "risk": "High", "specialty": "Cardiologist", "advice": "Seek immediate medical help."},
        {"keywords": ["fever", "chills", "hot", "temperature"], "disease": "Viral Fever", "risk": "Low", "specialty": "General Physician", "advice": "Rest, take paracetamol if needed."},
        {"keywords": ["sugar", "thirst", "urination"], "disease": "Diabetes", "risk": "Moderate", "specialty": "Endocrinologist", "advice": "Check blood sugar levels."},
        {"keywords": ["joint", "knee", "pain"], "disease": "Arthritis", "risk": "Moderate", "specialty": "Orthopedist", "advice": "Use hot compress."},
        {"keywords": ["skin", "rash", "itch"], "disease": "Dermatitis", "risk": "Low", "specialty": "Dermatologist", "advice": "Apply moisturizer."}
    ]

    match = {"disease": "General Health Query", "risk": "Unknown", "specialty": "General Physician", "advice": "Consult a doctor."}

    for item in smart_diagnosis:
        if any(word in symptoms for word in item['keywords']):
            match = item
            break

    # 2. Translate Response Back
    if user_lang != 'en':
        match = smart_translate_response(match, user_lang)

    return jsonify({"success": True, "data": match})

if __name__ == '__main__':
    app.run(debug=True, port=5000)