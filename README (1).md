# Darna - Intelligent Property Maintenance & Security

A web app that protects and maintains a property with AI facial recognition, network threat monitoring and predictive maintenance.

## Team Members
Qmasha Almansoori, Shama Alketbi, Anoud Alaleeli

## Problem
Property owners handle security and maintenance separately: unknown people enter unnoticed, strange devices join the network, and equipment is fixed only after it fails. Darna brings these into one dashboard.

## Key Features
- **Facial recognition:** identifies faces as authorized, unauthorized or unrecognized. Enrollment needs consent, face data is stored as encrypted templates (not photos), and every result needs manual review.
- **Network monitoring:** flags unknown devices, IP/MAC conflicts and risky open ports (Telnet, FTP, SMB, RDP, VNC).
- **Predictive maintenance:** scores assets by age, time since last service and lock battery, then gives a risk level and recommendation.
- **Dashboard:** cameras, smart locks, members and activity feed, with role-based access and login lockout.

## Technologies
Python 3.12, Flask, SQLite, DeepFace (Facenet512) with TensorFlow, `cryptography` (Fernet), HTML/CSS/JavaScript.

## Prerequisites
- Python 3.12 (TensorFlow does not support newer versions yet)
- Git, about 3 GB free disk space, and internet (the first face request downloads the model)

## Installation
```powershell
git clone https://github.com/Qmasha/Darna.git
cd Darna
py -3.12 -m venv env312
.\env312\Scripts\Activate.ps1
pip install -r requirements.txt
```
macOS/Linux: `python3.12 -m venv env312` and `source env312/bin/activate`.

## Configuration
Set two environment variables (they are never stored in the code):
```powershell
$env:DARNA_SECRET_KEY = "any-long-random-text"
$env:DARNA_BIOMETRIC_KEY = python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
macOS/Linux: use `export NAME="value"`. Generate the biometric key once and keep it: templates made with a different key cannot be read.

## How to Run
```powershell
python app.py
```
Open http://127.0.0.1:5000 and sign in with `admin@darna.com` / `Darna123!` (change it for real use). Optional: `python seed_demo.py` adds demo maintenance assets.

## How to Test
Automated (uses a temporary database):
```powershell
python -m unittest -v
```
Manual: on the **Network** page click *Run demo scan* (alerts appear, a second scan adds none); on **Maintenance** click *Run predictions*; on **Facial Recognition** enroll a person with consent and a clear one-face photo, then identify a different photo of them.

## Limitations
The network scan is simulated for the demo, maintenance prediction is rule-based (not machine learning), and facial matches are suggestions that a person must review.
