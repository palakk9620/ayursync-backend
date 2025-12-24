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

# Ensure consistent language detection
DetectorFactory.seed = 0
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Database Config
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

# --- DATABASE MODELS ---
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

# --- TRANSLATION HELPERS (FIXED) ---
def detect_and_translate_input(text):
    # 1. FORCE ENGLISH for common medical terms to prevent mis-detection
    common_english_terms = [
        "fever", "viral fever", "headache", "migraine", "asthma", "diabetes", 
        "cold", "cough", "flu", "pain", "chest pain", "stomach pain", 
        "acne", "rash", "joint pain", "arthritis", "dengue", "malaria",
        "typhoid", "jaundice", "infection"
    ]
    
    if text.lower().strip() in common_english_terms:
        return 'en', text

    try:
        # 2. Otherwise, use AI detection
        lang = detect(text)
        if lang != 'en':
            translated_text = GoogleTranslator(source='auto', target='en').translate(text)
            return lang, translated_text
        return 'en', text
    except:
        return 'en', text

def translate_response(data, target_lang):
    if target_lang == 'en': return data
    
    # Use OpenAI for smarter translation if available
    if client_ai:
        try:
            prompt = f"Translate the values of this JSON to language code '{target_lang}'. Keep keys exactly the same. JSON: {json.dumps(data)}"
            gpt = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            return json.loads(gpt.choices[0].message.content)
        except: pass

    # Fallback to Google Translate
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
                translated_data[key] = translate_response(value, target_lang)
            else:
                translated_data[key] = t(value)
        return translated_data
    except:
        return data

def get_icd_token():
    return None 

# --- STANDARD ROUTES ---
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

# --- 8. DISEASE SEARCH ---
@app.route('/api/search-disease', methods=['POST'])
def search_disease():
    raw_query = request.json.get('query', '').strip()
    
    # 1. Detect & Translate to English (With Safety Override)
    user_lang, query = detect_and_translate_input(raw_query)
    query = query.lower()
    
    # [BACKUP DB]
    backup_db = {
    "asthma": { "name": "Asthma", "specialist": "Pulmonologist", "codes": {"icd11": "CA23", "namaste": "TM2-R-008"}, "description": "A chronic condition affecting the airways in the lungs, causing wheezing and tightness.", "carePlan": { "symptoms": ["Wheezing", "Shortness of breath"], "diet": ["Ginger tea", "Warm fluids"], "exercise": ["Walking"], "yoga": ["Pranayama"] } },
    "diabetes": { "name": "Diabetes Mellitus", "specialist": "Endocrinologist", "codes": {"icd11": "5A11", "namaste": "TM2-E-034"}, "description": "A metabolic disease causing high blood sugar levels.", "carePlan": { "symptoms": ["Increased thirst", "Frequent urination"], "diet": ["Leafy greens", "Bitter gourd"], "exercise": ["Brisk walking"], "yoga": ["Mandukasana"] } },
    "migraine": { "name": "Migraine", "specialist": "Neurologist", "codes": {"icd11": "8A80", "namaste": "TM2-N-012"}, "description": "Intense, debilitating headaches often with nausea.", "carePlan": { "symptoms": ["Throbbing pain", "Nausea"], "diet": ["Magnesium rich foods"], "exercise": ["Gentle stretching"], "yoga": ["Shishuasana"] } },
    "viral fever": { "name": "Viral Fever", "specialist": "General Physician", "codes": {"icd11": "MG26", "namaste": "TM2-J-005"}, "description": "Acute viral infection characterized by high body temperature and fatigue.", "carePlan": { "symptoms": ["High fever", "Chills", "Body ache"], "diet": ["Soup", "Herbal tea", "Light meals"], "exercise": ["Rest is recommended"], "yoga": ["Shavasana"] } },
    "fever": { "name": "Viral Fever", "specialist": "General Physician", "codes": {"icd11": "MG26", "namaste": "TM2-J-005"}, "description": "Acute viral infection characterized by high body temperature and fatigue.", "carePlan": { "symptoms": ["High fever", "Chills", "Body ache"], "diet": ["Soup", "Herbal tea", "Light meals"], "exercise": ["Rest is recommended"], "yoga": ["Shavasana"] } },
    "cancer": { "name": "Cancer", "specialist": "Oncologist", "codes": {"icd11": "2A00", "namaste": "TM2-C-999"}, "description": "Uncontrolled growth of abnormal cells.", "carePlan": { "symptoms": ["Fatigue", "Lump"], "diet": ["High protein", "Berries"], "exercise": ["Light walking"], "yoga": ["Sukhasana"] } },
    "hypertension": { "name": "Hypertension", "specialist": "Cardiologist", "codes": {"icd11": "BA00", "namaste": "TM2-H-045"}, "description": "High blood pressure condition.", "carePlan": { "symptoms": ["Dizziness", "Headache"], "diet": ["Low salt", "Bananas"], "exercise": ["Cycling"], "yoga": ["Savasana"] } }
}

    result_data = None

    # 2. Find in Backup
    for key in backup_db:
        if key in query or query in key:
            result_data = backup_db[key]
            break
    
    # 3. Fallback to OpenAI
    if not result_data and client_ai:
        try:
            prompt = f"Provide Ayurvedic medical summary for '{query}'. Return JSON: name, specialist, codes(icd11, namaste), description, carePlan(symptoms, diet, exercise, yoga)."
            gpt = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            result_data = json.loads(gpt.choices[0].message.content)
        except: pass

    # 4. Translate Response Back
    if result_data:
        if user_lang != 'en':
            result_data = translate_response(result_data, user_lang)
        return jsonify({"success": True, "data": result_data})
    
    return jsonify({"success": False, "message": "Disease not found."})

# --- 9. ANALYZE SYMPTOMS ---
@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    raw_symptoms = request.json.get('symptoms', '').strip()
    user_lang, symptoms = detect_and_translate_input(raw_symptoms)
    symptoms = symptoms.lower()
    
    local_diagnosis_db = [
        {"keywords": ["headache", "head", "throbbing", "migraine"], "disease": "Migraine", "risk": "Moderate", "specialty": "Neurologist", "advice": "Rest in a dark room and stay hydrated."},
        {"keywords": ["chest", "heart", "pain", "tightness"], "disease": "Cardiac Issue", "risk": "High", "specialty": "Cardiologist", "advice": "Seek emergency medical help immediately."},
        {"keywords": ["fever", "hot", "temp", "cold", "chills", "body ache"], "disease": "Viral Fever", "risk": "Low", "specialty": "General Physician", "advice": "Rest, drink plenty of fluids, and monitor temperature."},
        {"keywords": ["sugar", "thirst", "urination", "glucose"], "disease": "Diabetes", "risk": "Moderate", "specialty": "Endocrinologist", "advice": "Monitor blood sugar levels and consult your specialist."},
        {"keywords": ["joint", "knee", "swelling", "stiffness", "arthritis"], "disease": "Arthritis", "risk": "Moderate", "specialty": "Rheumatologist", "advice": "Apply a warm compress and avoid heavy strain on joints."},
        {"keywords": ["skin", "rash", "itch", "redness"], "disease": "Dermatitis", "risk": "Low", "specialty": "Dermatologist", "advice": "Apply a mild moisturizer and avoid scratching."},
        {"keywords": ["weight loss", "lump", "unexplained fatigue", "growth", "cancer"], "disease": "Cancer (General Neoplasm)", "risk": "High", "specialty": "Oncologist", "advice": "Consult an oncologist for a professional screening and biopsy if needed."},
        {"keywords": ["blood pressure", "hypertension", "dizziness", "nosebleed"], "disease": "Hypertension", "risk": "Moderate", "specialty": "Cardiologist", "advice": "Reduce salt intake, rest, and monitor your BP readings."},
        {"keywords": ["anxiety", "panic", "worry", "heartbeat", "nervous"], "disease": "Anxiety Disorder", "risk": "Low to Moderate", "specialty": "Psychiatrist", "advice": "Practice deep breathing (Pranayama) and consider professional counseling."},
        {"keywords": ["wheezing", "breath", "cough", "asthma", "shortness"], "disease": "Asthma", "risk": "Moderate", "specialty": "Pulmonologist", "advice": "Keep your inhaler handy and avoid dust or smoke triggers."}
    ]

    match = None
    
    # 1. Check Local DB First
    for item in local_diagnosis_db:
        if any(word in symptoms for word in item['keywords']):
            match = item
            break
            
    # 2. Try OpenAI if no local match
    if not match and client_ai:
        try:
            prompt = f"Analyze symptoms: \"{symptoms}\". Return valid JSON with: {{\"disease\": \"\", \"risk\": \"\", \"specialty\": \"\", \"advice\": \"\"}}"
            gpt = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            match = json.loads(gpt.choices[0].message.content)
        except: pass

    if not match:
        match = {"disease": "General Health Query", "risk": "Unknown", "specialty": "General Physician", "advice": "Consult a doctor."}
    
    # 3. Translate Back
    if user_lang != 'en':
        match = translate_response(match, user_lang)

    return jsonify({"success": True, "data": match})

if __name__ == '__main__':
    app.run(debug=True, port=5000)