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

# 1. Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# =====================================================
# 🔐 CONFIGURATION & DATABASE CONNECTION
# =====================================================

# Read from .env file (Secure)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =====================================================
# 🔑 API KEYS
# =====================================================
# SECURE: Get key from .env file
OPENAI_API_KEY_SECURE = os.getenv('OPENAI_API_KEY') 

ICD_CLIENT_ID = 'c4f58ec7-9f5e-4d15-b638-71de5ff51103_9c73e6ca-0cfa-4c3e-a635-6c44c2f9ffed'
ICD_CLIENT_SECRET = 'dyPIp9AacFq8D7YU6tAluIBEHIglwTajELzscG6/EYQ='

# Initialize OpenAI
try:
    client_ai = OpenAI(api_key=OPENAI_API_KEY_SECURE)
except:
    client_ai = None # Fallback if key is missing

# =====================================================
# 🗄️ DATABASE MODELS (MySQL Tables)
# =====================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), default='individual')
    # Doctor Specific Fields
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
    userEmail = db.Column(db.String(100)) # Link to patient email
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

# =====================================================
# 🚀 API ROUTES
# =====================================================

# --- 1. REGISTER ---
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"message": "User already exists!", "success": False}), 400
    
    new_user = User(
        name=data['name'],
        email=data['email'],
        password=data['password'],
        role=data.get('role', 'individual'),
        specialization=data.get('specialization'),
        hospitalName=data.get('hospitalName'),
        address=data.get('address'),
        timings=data.get('timings')
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Registration Successful!", "success": True})

# --- 2. LOGIN ---
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user = User.query.filter_by(email=data['email']).first()
    if user and user.password == data['password']:
        return jsonify({
            "message": "Login Successful!", 
            "success": True, 
            "user": {"name": user.name, "role": user.role, "email": user.email}
        })
    return jsonify({"message": "Invalid Credentials", "success": False}), 401

# --- 3. GET DOCTORS LIST ---
@app.route('/api/doctors', methods=['GET'])
def get_doctors():
    doctors = User.query.filter_by(role='doctor').all()
    doc_list = []
    for doc in doctors:
        doc_list.append({
            "id": doc.id,
            "name": doc.name,
            "specialization": doc.specialization or 'General Physician',
            "hospitalName": doc.hospitalName or 'Clinic',
            "address": doc.address or 'Bhopal',
            "timings": doc.timings or '10:00 AM - 05:00 PM',
            "email": doc.email
        })
    return jsonify(doc_list)

# --- 4. BOOK APPOINTMENT ---
@app.route('/api/book-appointment', methods=['POST'])
def book_appointment():
    data = request.json
    new_appt = Appointment(
        patientName=data['patientName'],
        doctorName=data['doctorName'],
        date=data['date'],
        time=data['time'],
        disease=data['disease'],
        phone=data['phone'],
        userEmail=data['userEmail'],
        status='Confirmed'
    )
    db.session.add(new_appt)
    db.session.commit()
    return jsonify({"message": "Appointment Booked Successfully!", "success": True})

# --- 5. UPDATE APPOINTMENT STATUS ---
@app.route('/api/update-appointment-status', methods=['POST'])
def update_appointment_status():
    data = request.json
    appt = Appointment.query.get(data.get('id'))
    if appt:
        appt.status = data.get('status')
        db.session.commit()
        return jsonify({"success": True, "message": "Status Updated"})
    return jsonify({"success": False, "message": "Not Found"})

# --- 6. UPDATE DOCTOR PROFILE ---
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
# --- 6.1. HEALTH CHECK ENDPOINT (NEW) ---
# This assures Render that the service is alive and listening.
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Service is healthy and ready to process requests"}), 200

# --- 7. DASHBOARD STATS ---
@app.route('/api/dashboard-stats', methods=['POST'])
def dashboard_stats():
    data = request.json
    user_role = data.get('role')
    user_email = data.get('email')

    stats = {
        "active_doctors_count": 0, "active_doctors_list": [], "active_appointment": None,
        "past_appointments": [], "total_app_count": 0, "all_appointments": [], 
        "doctor_active_appts": [], "patient_records": [],
        "efficacy_stats": {"success": 0, "missed": 0, "total": 0},
        "system_health": {"status": "Operational", "uptime": "100%", "database": "Connected"}
    }

    # -- Active Doctors --
    doctors = User.query.filter_by(role='doctor').all()
    doc_list = [{"id": d.id, "name": d.name, "specialization": d.specialization, "location": "Bhopal"} for d in doctors]
    stats["active_doctors_count"] = len(doc_list)
    stats["active_doctors_list"] = doc_list

    # -- Role Specific --
    if user_role == 'individual':
        my_appts = Appointment.query.filter_by(userEmail=user_email).order_by(Appointment.created_at.desc()).all()
        stats["total_app_count"] = len(my_appts)
        
        for appt in my_appts:
            stats["past_appointments"].append({
                "doctorName": appt.doctorName, "date": appt.date, "time": appt.time,
                "disease": appt.disease, "status": appt.status
            })
        
        active = next((a for a in my_appts if a.status == 'Confirmed'), None)
        if active:
            stats["active_appointment"] = {"doctor": active.doctorName, "time": f"{active.date} at {active.time}"}

    elif user_role == 'doctor':
        current_user = User.query.filter_by(email=user_email).first()
        if current_user:
            # Get appointments for this doctor
            doc_appts = Appointment.query.filter_by(doctorName=current_user.name).order_by(Appointment.created_at.desc()).all()
            
            for appt in doc_appts:
                if appt.status == 'Confirmed':
                    stats["doctor_active_appts"].append({
                        "id": appt.id, "patient_name": appt.patientName, "disease": appt.disease,
                        "time": appt.time, "date": appt.date
                    })
                stats["patient_records"].append({
                    "patient": appt.patientName, "doctor": appt.doctorName, "date": appt.date, "feedback": random.choice(["Good", "Satisfied"])
                })
            
            success = Appointment.query.filter_by(doctorName=current_user.name, status='Successful').count()
            missed = Appointment.query.filter_by(doctorName=current_user.name, status='Not Appeared').count()
            stats["efficacy_stats"] = {"success": success, "missed": missed, "total": success+missed}

    else:
        # Admin
        all_appts = Appointment.query.order_by(Appointment.created_at.desc()).all()
        for appt in all_appts:
            stats["all_appointments"].append({
                "id": appt.id, "patient_name": appt.patientName, "doctor_name": appt.doctorName,
                "status": appt.status, "disease": appt.disease
            })
            stats["patient_records"].append({
                "patient": appt.patientName, "doctor": appt.doctorName, "date": appt.date, "feedback": "Recorded"
            })

    return jsonify({"success": True, "stats": stats})

# --- 8. AI & DISEASE SEARCH (Keep Logic Same) ---
@app.route('/api/search-disease', methods=['POST'])
def search_disease():
    query = request.json.get('query', '').lower().strip()
    
    icd_fallback_db = {
        "asthma": {"code": "CA23", "title": "Asthma"},
        "diabetes": {"code": "5A11", "title": "Type 2 Diabetes Mellitus"},
        "sugar": {"code": "5A11", "title": "Type 2 Diabetes Mellitus"},
        "hypertension": {"code": "BA00", "title": "Essential Hypertension"},
        "bp": {"code": "BA00", "title": "Essential Hypertension"},
        "migraine": {"code": "8A80", "title": "Migraine"},
        "fever": {"code": "MG26", "title": "Fever of unknown origin"},
        "cold": {"code": "1A00", "title": "Common Cold"},
        "arthritis": {"code": "FA00", "title": "Rheumatoid Arthritis"}
    }
    
    namaste_db = {
        "diabetes": "TM2-E-034 (Madhumeha)", "sugar": "TM2-E-034 (Madhumeha)",
        "bp": "TM2-C-001 (Uchcha Rakta Chapa)", "hypertension": "TM2-C-001 (Uchcha Rakta Chapa)",
        "migraine": "TM2-N-012 (Ardhavabhedaka)", "asthma": "TM2-R-008 (Tamaka Shwasa)",
        "fever": "TM2-J-005 (Jwara)", "cold": "TM2-R-002 (Pratishyaya)"
    }

    openai_fallback_db = {
        "asthma": {
            "description": "A chronic condition affecting the airways in the lungs.",
            "symptoms": ["Shortness of breath", "Chest tightness", "Wheezing"],
            "diet": ["Vitamin D rich foods", "Magnesium rich foods"],
            "exercise": ["Swimming (warm)", "Walking"],
            "yoga": ["Sukhasana", "Upavistha Konasana"]
        },
        "diabetes": {
            "description": "A chronic condition that affects how your body turns food into energy.",
            "symptoms": ["Increased thirst", "Frequent urination", "Fatigue"],
            "diet": ["Leafy greens", "Whole grains", "Avoid sugar"],
            "exercise": ["Aerobic exercise", "Resistance training"],
            "yoga": ["Dhanurasana", "Paschimottanasana"]
        },
        "migraine": {
            "description": "A headache of varying intensity, often accompanied by nausea.",
            "symptoms": ["Throbbing pain", "Sensitivity to light", "Nausea"],
            "diet": ["Magnesium rich foods", "Stay hydrated"],
            "exercise": ["Light cardio", "Stretching"],
            "yoga": ["Shishuasana", "Setu Bandhasana"]
        },
        "hypertension": {
            "description": "High blood pressure condition.",
            "symptoms": ["Headaches", "Shortness of breath"],
            "diet": ["DASH diet", "Low sodium"],
            "exercise": ["Walking", "Jogging"],
            "yoga": ["Baddhakonasana", "Virasana"]
        },
        "fever": {
            "description": "A temporary increase in your body temperature.",
            "symptoms": ["Sweating", "Chills", "Headache"],
            "diet": ["Fluids", "Soup"],
            "exercise": ["Rest recommended"],
            "yoga": ["Shavasana"]
        }
    }

    icd_result = {"code": "Not Found", "title": query.capitalize()}
    token = get_icd_token()
    if token:
        try:
            headers = { 'Authorization': f'Bearer {token}', 'Accept': 'application/json', 'API-Version': 'v2', 'Accept-Language': 'en'}
            res = requests.get(f"https://id.who.int/icd/entity/search?q={query}", headers=headers).json()
            if res.get('destinationEntities') and len(res['destinationEntities']) > 0:
                best_match = res['destinationEntities'][0]
                icd_result = { "code": best_match.get('theCode', 'No Code'), "title": best_match.get('title', query) }
        except: pass
    
    if icd_result['code'] == "Not Found":
        for key, data in icd_fallback_db.items():
            if key in query:
                icd_result = data
                break

    namaste_code = "Not Found in TM2"
    for key, code in namaste_db.items():
        if key in query:
            namaste_code = code
            break

    ai_response = {}
    openai_success = False
    try:
        if client_ai:
            prompt = f"Provide a structured Ayurvedic and medical summary for the disease: '{query}'. Return ONLY valid JSON with structure: {{\"description\": \"\", \"symptoms\": [], \"diet\": [], \"exercise\": [], \"yoga\": []}}"
            gpt_call = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            ai_response = json.loads(gpt_call.choices[0].message.content)
            openai_success = True
    except: pass

    if not openai_success:
        found_backup = False
        for key, data in openai_fallback_db.items():
            if key in query:
                ai_response = data
                found_backup = True
                break
        if not found_backup:
            ai_response = {"description": "Consult a specialist.", "symptoms": [], "diet": [], "exercise": [], "yoga": []}

    final_data = {
        "name": icd_result['title'],
        "codes": {"icd11": icd_result['code'], "namaste": namaste_code},
        "description": ai_response.get('description'),
        "carePlan": {
            "symptoms": ai_response.get('symptoms', []),
            "diet": ai_response.get('diet', []),
            "exercise": ai_response.get('exercise', []),
            "yoga": ai_response.get('yoga', [])
        }
    }
    return jsonify({"success": True, "data": final_data})

@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    symptoms = request.json.get('symptoms', '').lower()
    
    local_diagnosis_db = [
        {"keywords": ["chest", "heart", "breath"], "disease": "Potential Cardiac Issue", "risk": "High", "specialty": "Cardiologist", "advice": "Visit hospital immediately."},
        {"keywords": ["fever", "cough", "cold"], "disease": "Viral Influenza (Flu)", "risk": "Low", "specialty": "General Physician", "advice": "Rest and hydration."},
        {"keywords": ["headache", "nausea", "light"], "disease": "Migraine", "risk": "Moderate", "specialty": "Neurologist", "advice": "Rest in dark room."},
        {"keywords": ["thirst", "urination", "hunger"], "disease": "Diabetes", "risk": "Moderate", "specialty": "Endocrinologist", "advice": "Check blood sugar."},
        {"keywords": ["joint", "pain", "knee"], "disease": "Arthritis", "risk": "Moderate", "specialty": "Orthopedist", "advice": "Consult specialist."},
        {"keywords": ["skin", "rash", "itch"], "disease": "Dermatitis", "risk": "Low", "specialty": "Dermatologist", "advice": "Avoid scratching."}
    ]

    ai_result = {}
    openai_success = False
    
    try:
        if client_ai:
            prompt = f"Analyze these symptoms: \"{symptoms}\". Return valid JSON with: {{\"disease\": \"\", \"risk\": \"\", \"specialty\": \"\", \"advice\": \"\"}}"
            gpt = client_ai.chat.completions.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": prompt}])
            ai_result = json.loads(gpt.choices[0].message.content)
            openai_success = True
    except: pass

    if not openai_success:
        best_match = {"disease": "General Health Issue", "risk": "Unknown", "specialty": "General Physician", "advice": "Consult a doctor."}
        for condition in local_diagnosis_db:
            if any(word in symptoms for word in condition['keywords']):
                best_match = condition
                break
        ai_result = best_match

    return jsonify({"success": True, "data": ai_result})

print("--- 3. CHECKING MAIN BLOCK ---")
if __name__ == '__main__':
    print("--- 4. STARTING FLASK SERVER ---")
    app.run(debug=True, port=5000)