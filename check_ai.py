"""Run this to see exactly why facial recognition fails: python check_ai.py"""
import os, sys
print("Python", sys.version.split()[0])
for m in ["flask", "cryptography", "numpy", "tensorflow", "tf_keras", "deepface"]:
    try:
        __import__(m); print("OK   ", m)
    except Exception as e:
        print("FAIL ", m, "-", type(e).__name__, e)
print("DARNA_BIOMETRIC_KEY set:", bool(os.environ.get("DARNA_BIOMETRIC_KEY")))
