# backend/app.py
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
# Allow CORS for Vercel frontend
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
with app.app_context():
    db.create_all()
    print("✅ Connected to Cloud MySQL Database!")

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

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Backend is live"}), 200

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"message": "User already exists!", "success": False}), 400
    
    new_user = User(
        name=data['name'], email=data['email'], password=data['password'],
        role=data.get('role', 'individual'), specialization=data.get('specialization'),
        hospitalName=data.get('hospitalName'), address=data.get('address'), timings=data.get('timings')
    )
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
    doc_list = []
    for doc in doctors:
        doc_list.append({
            "id": doc.id, "name": doc.name, "specialization": doc.specialization or 'General Physician',
            "hospitalName": doc.hospitalName or 'Clinic', "address": doc.address or 'Bhopal',
            "timings": doc.timings or '10:00 AM - 05:00 PM', "email": doc.email
        })
    return jsonify(doc_list)

@app.route('/api/book-appointment', methods=['POST'])
def book_appointment():
    data = request.json
    new_appt = Appointment(
        patientName=data['patientName'], doctorName=data['doctorName'], date=data['date'],
        time=data['time'], disease=data['disease'], phone=data['phone'],
        userEmail=data['userEmail'], status='Confirmed'
    )
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

    stats = {
        "active_doctors_count": 0, "active_doctors_list": [], "active_appointment": None,
        "past_appointments": [], "total_app_count": 0, "all_appointments": [], 
        "doctor_active_appts": [], "patient_records": [],
        "efficacy_stats": {"success": 0, "missed": 0, "total": 0},
        "system_health": {"status": "Operational", "uptime": "100%", "database": "Connected"}
    }

    doctors = User.query.filter_by(role='doctor').all()
    doc_list = [{"id": d.id, "name": d.name, "specialization": d.specialization, "location": "Bhopal"} for d in doctors]
    stats["active_doctors_count"] = len(doc_list)
    stats["active_doctors_list"] = doc_list

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
            stats["active_appointment"] = {
                "doctor": active.doctorName, "time": active.time, "date": active.date, "disease": active.disease
            }

    elif user_role == 'doctor':
        current_user = User.query.filter_by(email=user_email).first()
        if current_user:
            doc_appts = Appointment.query.filter_by(doctorName=current_user.name).order_by(Appointment.created_at.desc()).all()
            for appt in doc_appts:
                if appt.status == 'Confirmed':
                    stats["doctor_active_appts"].append({
                        "id": appt.id, "patient_name": appt.patientName, "disease": appt.disease,
                        "time": appt.time, "date": appt.date, "phone": appt.phone
                    })
                stats["patient_records"].append({
                    "patient": appt.patientName, "doctor": appt.doctorName, "date": appt.date, "feedback": random.choice(["Good", "Satisfied"])
                })
            success = Appointment.query.filter_by(doctorName=current_user.name, status='Successful').count()
            missed = Appointment.query.filter_by(doctorName=current_user.name, status='Not Appeared').count()
            stats["efficacy_stats"] = {"success": success, "missed": missed, "total": success+missed}
    else:
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

# ... (Imports and DB Config remain same) ...

# --- 8. AI & DISEASE SEARCH ---
@app.route('/api/search-disease', methods=['POST'])
def search_disease():
    query = request.json.get('query', '').lower().strip()
    
    # EXPANDED BACKUP DB (Ensures specific data)
    backup_db = {
        "asthma": {
            "name": "Asthma",
            "specialist": "Pulmonologist",
            "codes": {"icd11": "CA23", "namaste": "TM2-R-008"},
            "description": "Chronic inflammatory disease of the airways.",
            "carePlan": {
                "symptoms": ["Wheezing", "Shortness of breath", "Chest tightness"],
                "diet": ["Ginger tea", "Garlic", "Avoid cold dairy"],
                "exercise": ["Walking", "Swimming"],
                "yoga": ["Pranayama", "Sukhasana"]
            }
        },
        "diabetes": {
            "name": "Diabetes Mellitus",
            "specialist": "Endocrinologist",
            "codes": {"icd11": "5A11", "namaste": "TM2-E-034"},
            "description": "Metabolic disorder characterized by high blood sugar.",
            "carePlan": {
                "symptoms": ["Thirst", "Frequent urination", "Fatigue"],
                "diet": ["Leafy greens", "Whole grains", "Bitter gourd"],
                "exercise": ["Brisk walking", "Cycling"],
                "yoga": ["Mandukasana", "Surya Namaskar"]
            }
        },
        "migraine": {
            "name": "Migraine",
            "specialist": "Neurologist",
            "codes": {"icd11": "8A80", "namaste": "TM2-N-012"},
            "description": "Recurrent throbbing headache often with nausea.",
            "carePlan": {
                "symptoms": ["Throbbing pain", "Nausea", "Light sensitivity"],
                "diet": ["Magnesium rich foods", "Water"],
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
                "exercise": ["Rest recommended"],
                "yoga": ["Shavasana"]
            }
        }
    }

    if query in backup_db:
        return jsonify({"success": True, "data": backup_db[query]})

    # Fallback
    return jsonify({"success": False, "message": "Disease not found in basic database."})

# --- 9. ANALYZE SYMPTOMS (SMART MATCHING) ---
@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    symptoms = request.json.get('symptoms', '').lower()
    
    # EXPANDED KEYWORD MATCHING
    smart_diagnosis = [
        {"keywords": ["headache", "nausea", "light", "throbbing"], "disease": "Migraine", "risk": "Moderate", "specialty": "Neurologist", "advice": "Rest in a dark room, hydrate."},
        {"keywords": ["chest", "heart", "squeeze", "breath"], "disease": "Cardiac Issue", "risk": "High", "specialty": "Cardiologist", "advice": "Seek immediate medical help."},
        {"keywords": ["fever", "chills", "hot", "shivering"], "disease": "Viral Fever", "risk": "Low", "specialty": "General Physician", "advice": "Rest, take paracetamol if needed, drink fluids."},
        {"keywords": ["sugar", "thirst", "urination"], "disease": "Diabetes", "risk": "Moderate", "specialty": "Endocrinologist", "advice": "Check blood sugar levels."},
        {"keywords": ["joint", "knee", "pain", "stiff"], "disease": "Arthritis", "risk": "Moderate", "specialty": "Orthopedist", "advice": "Use hot compress, avoid strain."},
        {"keywords": ["skin", "rash", "itch", "red"], "disease": "Dermatitis", "risk": "Low", "specialty": "Dermatologist", "advice": "Apply moisturizer, avoid scratching."}
    ]

    match = {"disease": "General Health Issue", "risk": "Unknown", "specialty": "General Physician", "advice": "Consult a doctor for better diagnosis."}

    for item in smart_diagnosis:
        # Check if ANY keyword is present in the user input
        if any(word in symptoms for word in item['keywords']):
            match = item
            break

    return jsonify({"success": True, "data": match})
    
   
if __name__ == '__main__':
    app.run(debug=True, port=5000)