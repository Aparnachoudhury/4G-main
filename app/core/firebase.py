import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
if not firebase_admin._apps:
    firebase_creds = os.getenv("FIREBASE_CREDENTIALS")

    if firebase_creds:
        # Railway / production
        firebase_config = json.loads(firebase_creds)
        cred = credentials.Certificate(firebase_config)
    else:
        # Local
        cred = credentials.Certificate("serviceAccountKey.json")

    firebase_admin.initialize_app(cred)

firebase_db = firestore.client()