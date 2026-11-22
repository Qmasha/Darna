import json
import os
from pathlib import Path

import numpy as np
from cryptography.fernet import Fernet

MODEL_NAME = "Facenet512"
DETECTOR_BACKEND = "opencv"

def get_fernet():
    key = os.environ.get("DARNA_BIOMETRIC_KEY")
    if not key:
        raise RuntimeError(
            "DARNA_BIOMETRIC_KEY is not configured. Generate a key and set it "
            "as an environment variable before using facial recognition."
        )
    return Fernet(key.encode("utf-8"))

def create_face_embedding(image_path):
    from deepface import DeepFace  # imported lazily (heavy)
    results = DeepFace.represent(
        img_path=str(image_path),
        model_name=MODEL_NAME,
        detector_backend=DETECTOR_BACKEND,
        enforce_detection=True
    )
    if len(results) != 1:
        raise ValueError("The image must contain exactly one clearly detected face.")
    return np.asarray(results[0]["embedding"], dtype=np.float32)

def save_encrypted_embedding(embedding, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(embedding.tolist()).encode("utf-8")
    encrypted = get_fernet().encrypt(payload)
    destination.write_bytes(encrypted)

def load_encrypted_embedding(source):
    payload = get_fernet().decrypt(Path(source).read_bytes())
    return np.asarray(json.loads(payload.decode("utf-8")), dtype=np.float32)

def cosine_distance(first, second):
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator == 0:
        return 1.0
    similarity = float(np.dot(first, second) / denominator)
    return 1.0 - similarity
