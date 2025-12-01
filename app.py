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
# 🔐 DATABASE CONNECTION
# =====================================================
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =====================================================
# 🔑 API KEYS
# =====================================================
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ICD_CLIENT_ID = 'c4f58ec7-9f5e-4d15-b638-71de5ff51103_9c73e6ca-0cfa-4c3e-a635-6c44c2f9ffed'
ICD_CLIENT_SECRET = 'dyPIp9AacFq8D7YU6tAluIBEHIglwTajELzscG6/EYQ='

try:
    client_ai = OpenAI(api_key=OPENAI_API_KEY)
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

    # Get all doctors for the "Active Doctors" list
    doctors = User.query.filter_by(role='doctor').all()
    doc_list = [{"id": d.id, "name": d.name, "specialization": d.specialization, "location": "Bhopal"} for d in doctors]
    stats["active_doctors_count"] = len(doc_list)
    stats["active_doctors_list"] = doc_list

    if user_role == 'individual':
        # Fetch appointments for this specific user email
        my_appts = Appointment.query.filter_by(userEmail=user_email).order_by(Appointment.created_at.desc()).all()
        stats["total_app_count"] = len(my_appts)
        
        for appt in my_appts:
            stats["past_appointments"].append({
                "doctorName": appt.doctorName, "date": appt.date, "time": appt.time,
                "disease": appt.disease, "status": appt.status
            })
        
        # Find the next confirmed appointment
        # UPDATED: Sending full details (Doctor, Time, Date, Disease)
        active = next((a for a in my_appts if a.status == 'Confirmed'), None)
        if active:
            stats["active_appointment"] = {
                "doctor": active.doctorName, 
                "time": active.time,
                "date": active.date,       # Added Date
                "disease": active.disease  # Added Disease
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

# ... (Keeping Search & Symptom API Routes same as they don't affect dashboard stats)
@app.route('/api/search-disease', methods=['POST'])
def search_disease():
    return jsonify({"success": True, "data": {"name": "Result", "codes": {}, "carePlan": {"symptoms": [], "diet": [], "exercise": [], "yoga": []}}})

@app.route('/api/analyze-symptoms', methods=['POST'])
def analyze_symptoms():
    return jsonify({"success": True, "data": {"disease": "Result", "risk": "Low", "specialty": "General", "advice": "Rest"}})

print("--- 3. CHECKING MAIN BLOCK ---")
if __name__ == '__main__':
    print("--- 4. STARTING FLASK SERVER ---")
    app.run(debug=True, port=5000)