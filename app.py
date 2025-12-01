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

# NEW: Translation Libraries
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0

# 1. Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# =====================================================
# 🔐 CONFIGURATION & DATABASE CONNECTION
# =====================================================
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# =====================================================
# 🔑 API KEYS
# =====================================================
OPENAI_API_KEY_SECURE = os.getenv('OPENAI_API_KEY') 
ICD_CLIENT_ID = 'c4f58ec7-9f5e-4d15-b638-71de5ff51103_9c73e6ca-0cfa-4c3e-a635-6c44c2f9ffed'
ICD_CLIENT_SECRET = 'dyPIp9AacFq8D7YU6tAluIBEHIglwTajELzscG6/EYQ='

try:
    client_ai = OpenAI(api_key=OPENAI_API_KEY_SECURE)
except:
    client_ai = None

# =====================================================
# 🗄️ DATABASE MODELS
# =====================================================
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

print("--- 2. CONNECTING TO DATABASE ---")
# Create Tables in Cloud DB
try:
    with app.app_context():
        db.create_all()
        print("✅ Connected to Cloud MySQL Database!")
except Exception as e:
    print(f"❌ CONNECTION FAILED: {e}")

# =====================================================
# 🛠️ HELPER FUNCTIONS
# =====================================================
def get_icd_token():
    token_endpoint = 'https://icdaccessmanagement.who.int/connect/token'
    payload = {'client_id': ICD_CLIENT_ID, 'client_secret': ICD_CLIENT_SECRET, 'scope': 'icdapi_access', 'grant_type': 'client_credentials'}
    try:
        response = requests.post(token_endpoint, data=payload).json()
        return response.get('access_token')
    except: return None

# --- NEW: TRANSLATION HELPERS ---
def detect_and_translate_input(text):
    try:
        lang = detect(text)
        if lang != 'en':
            translated_text = GoogleTranslator(source='auto', target='en').translate(text)
            return lang, translated_text
        return 'en', text
    except:
        return 'en', text

def translate_response(data, target_lang):
    if target_lang == 'en': return data
    
    def t(val):
        if isinstance(val, str):
            try: return GoogleTranslator(source='en', target=target_lang).translate(val)
            except: return val
        if isinstance(val, list):
            return [t(v) for v in val]
        return val

    try:
        translated_data = {}
        for key, value in data.items():
            if key in ['codes', 'risk', 'specialist', 'name']: # Keep medical terms/names in English if preferred, or translate them too. Translating all for now.
                # Optional: Don't translate ICD codes
                if key == 'codes': 
                    translated_data[key] = value
                else:
                    translated_data[key] = t(value)
            elif isinstance(value, dict):
                translated_data[key] = translate_response(value, target_lang)
            else:
                translated_data[key] = t(value)
        return translated_data
    except:
        return data

# =====================================================
# 🚀 API ROUTES
# =====================================================

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Service is healthy"}), 200

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"message": "User already exists!", "success": False}), 400
    new_user = User(name=data['name'], email=data['email'], password=data['password'], role=data.get('role', 'individual'), specialization=data.get('specialization'), hospitalName=data.get('hospitalName'), address=data.get('address'), timings=data.get('timings'))
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Registration Successful!", "success": True})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and user.password == data['password']:
        return jsonify({"message": "Login Successful!", "success": True, "user": {"name": user.name, "role": user.role, "email": user.email}})
    return jsonify({"message": "Invalid Credentials", "success": False}), 401

@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    doctors = User.query.filter_by(role='doctor').all()
    doc_list = [{"id": d.id, "name": d.name, "specialization": d.specialization or 'General Physician', "hospitalName": d.hospitalName or 'Clinic', "address": d.address or 'Bhopal', "timings": d.timings or '10:00 AM - 05:00 PM', "email": d.email} for d in doctors]
    return jsonify(doc_list)

@app.route('/api/book-appointment', methods=['POST'])
def book_appointment():
    data = request.json
    new_appt = Appointment(patientName=data['patientName'], doctorName=data['doctorName'], date=data['date'], time=data['time'], disease=data['disease'], phone=data['phone'], userEmail=data['userEmail'], status='Confirmed')
    db.session.add(new_appt)
    db.session.commit()
    return jsonify({"message": "Appointment Booked Successfully!", "success": True})

@app.route('/api/update-appointment-status', methods=['POST'])
def update_appointment_status():
    data = request.json
    appt = Appointment.query.get(data.get('id'))
    if appt:
        appt.status = data.get('status')
        db.session.commit()
        return jsonify({"success": True, "message": "Status Updated"})
    return jsonify({"success": False, "message": "Not Found"})

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
        return jsonify({"success": True, "message": "Profile Updated"})
    return jsonify({"success": False, "message": "User not found"})

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

# --- 8. AI & DISEASE SEARCH (With Translation) ---
@app.route('/api/search-disease', methods=['POST'])
def search_disease():
    raw_query = request.json.get('query', '').strip()
    
    # 1. Detect & Translate
    user_lang, query = detect_and_translate_input(raw_query)
    query = query.lower()

    icd_fallback_db = {
        "asthma": {"code": "CA23", "title": "Asthma"}, "bronchial asthma": {"code": "CA23", "title": "Bronchial Asthma"},
        "diabetes": {"code": "5A11", "title": "Type 2 Diabetes Mellitus"}, "sugar": {"code": "5A11", "title": "Type 2 Diabetes Mellitus"},
        "migraine": {"code": "8A80", "title": "Migraine"}, "hypertension": {"code": "BA00", "title": "Essential Hypertension"}, 
    }
    
    openai_fallback_db = {
        "asthma": { "description": "Chronic airway inflammation.", "symptoms": ["Wheezing", "Shortness of breath"], "diet": ["Warm fluids"], "exercise": ["Walking"], "yoga": ["Pranayama"], "specialist": "Pulmonologist" },
        "diabetes": { "description": "Metabolic disorder.", "symptoms": ["Thirst"], "diet": ["Low sugar"], "exercise": ["Cardio"], "yoga": ["Mandukasana"], "specialist": "Endocrinologist" },
        "migraine": { "description": "Intense headache.", "symptoms": ["Throbbing pain"], "diet": ["Magnesium rich"], "exercise": ["Stretching"], "yoga": ["Shishuasana"], "specialist": "Neurologist" }
    }

    icd_result = {"code": "N/A", "title": query.capitalize()}
    token = get_icd_token()
    if token:
        try:
            headers = { 'Authorization': f'Bearer {token}', 'Accept': 'application/json', 'API-Version': 'v2', 'Accept-Language': 'en'}
            res = requests.get(f"https://id.who.int/icd/entity/search?q={query}", headers=headers).json()
            if res.get('destinationEntities') and len(res['destinationEntities']) > 0:
                best_match = res['destinationEntities'][0]
                icd_result = { "code": best_match.get('theCode', 'No Code'), "title": best_match.get('title', query) }
        except: pass
    
    if icd_result['code'] == "N/A":
        for key, data in icd_fallback_db.items():
            if key in query: icd_result = icd_fallback_db[key]; break

    ai_response = {"description": "Consult a specialist.", "symptoms": [], "diet": [], "exercise": [], "yoga": [], "specialist": "General Physician"}
    openai_success = False
    
    matched_backup = None
    for key in openai_fallback_db:
        if key in query: matched_backup = openai_fallback_db[key]; break

    if matched_backup: 
        ai_response = matched_backup
    elif client_ai:
        try:
            prompt = f"Provide Ayurvedic summary for '{query}'. JSON: description, symptoms[], diet[], exercise[], yoga[], specialist."
            gpt = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            ai_response = json.loads(gpt.choices[0].message.content)
            openai_success = True
        except: pass

    final_data = {
        "name": icd_result['title'],
        "codes": {"icd11": icd_result['code'], "namaste": "TM-Code"},
        "description": ai_response.get('description'),
        "carePlan": ai_response,
        "specialist": ai_response.get('specialist', 'General Physician')
    }

    # 2. Translate Back
    if user_lang != 'en':
        final_data = translate_response(final_data, user_lang)

    return jsonify({"success": True, "data": final_data})

# --- 9. ANALYZE SYMPTOMS (With Translation) ---
@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    raw_symptoms = request.json.get('symptoms', '').strip()
    
    # 1. Detect & Translate
    user_lang, symptoms = detect_and_translate_input(raw_symptoms)
    symptoms = symptoms.lower()
    
    local_diagnosis_db = [
        {"keywords": ["headache", "head", "throbbing"], "disease": "Migraine", "risk": "Moderate", "specialty": "Neurologist", "advice": "Rest in dark room."},
        {"keywords": ["chest", "heart", "pain"], "disease": "Cardiac Issue", "risk": "High", "specialty": "Cardiologist", "advice": "Seek help."},
        {"keywords": ["fever", "hot"], "disease": "Viral Fever", "risk": "Low", "specialty": "General Physician", "advice": "Rest."},
        {"keywords": ["sugar", "thirst"], "disease": "Diabetes", "risk": "Moderate", "specialty": "Endocrinologist", "advice": "Check sugar."},
    ]

    result = {"disease": "General Health Issue", "risk": "Unknown", "specialty": "General Physician", "advice": "Consult a doctor."}
    openai_success = False

    try:
        if client_ai:
            prompt = f"Analyze symptoms: \"{symptoms}\". Return valid JSON with: {{\"disease\": \"\", \"risk\": \"\", \"specialty\": \"\", \"advice\": \"\"}}"
            gpt = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            result = json.loads(gpt.choices[0].message.content)
            openai_success = True
    except: pass

    if not openai_success:
        for condition in local_diagnosis_db:
            if any(word in symptoms for word in condition['keywords']):
                result = condition
                break
    
    # 2. Translate Back
    if user_lang != 'en':
        result = translate_response(result, user_lang)

    return jsonify({"success": True, "data": result})

if __name__ == '__main__':
    app.run(debug=True, port=5000)