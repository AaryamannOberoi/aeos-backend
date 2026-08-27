"""
Firestore persistence for pipeline runs.
"""

import os

from dotenv import load_dotenv

load_dotenv()

import firebase_admin
from firebase_admin import credentials, firestore

_cred_path = os.environ["FIREBASE_CREDENTIALS_PATH"]
_app = firebase_admin.initialize_app(credentials.Certificate(_cred_path))
_db = firestore.client()


def save_run(problem_statement: str, weights: dict, result: dict) -> str:
    """Writes one document to the "aeos_runs" collection, returns its id."""
    _, doc_ref = _db.collection("aeos_runs").add(
        {
            "problem_statement": problem_statement,
            "weights": weights,
            "result": result,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )
    return doc_ref.id
