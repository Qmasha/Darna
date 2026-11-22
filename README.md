# Darna - Intelligent Property Maintenance & Security

Run:
    pip install -r requirements.txt
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   
    export DARNA_BIOMETRIC_KEY=<key>        # required for facial recognition (Windows: set ...)
    export DARNA_SECRET_KEY=<any long random string>
    python seed_demo.py                      # optional demo maintenance assets
    python app.py                            # http://127.0.0.1:5000

Login: admin@darna.com / Darna123!. Set FLASK_DEBUG=1 only for development.
Modules: face_service/facial_routes (facial recognition), network_service (device & threat detection),
maintenance_service (predictive maintenance), security_routes (their APIs), app.py (auth, cameras, locks).
