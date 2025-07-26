from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import tempfile
import os
import pdfplumber
import docx2txt
import pytesseract
from PIL import Image
import requests
import sqlite3
import hashlib
import hmac
import base64
from datetime import datetime

PUBLIC_KEY = os.getenv("IKANOON_PUBLIC_KEY", "your_public_key")
PRIVATE_KEY = os.getenv("IKANOON_PRIVATE_KEY", "your_private_key")
KANOON_API_URL = "https://api.indiankanoon.org/search/"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "feedback.db"
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draft_text TEXT,
                    predicted_questions TEXT,
                    corrected_questions TEXT,
                    timestamp TEXT
                 )''')
conn.commit()
conn.close()

def extract_text(file_path):
    text = ""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
    elif ext in [".doc", ".docx"]:
        text = docx2txt.process(file_path)
    elif ext in [".png", ".jpg", ".jpeg"]:
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image)
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    return text.strip()

def spot_legal_issues(text):
    return [
        "Whether denial of hearing violates principles of natural justice under Article 14?",
        "Whether the impugned order suffers from lack of jurisdiction?",
        "Whether delay in filing appeal can be condoned under Section 5 of Limitation Act?"
    ]

def sign_request(params):
    sorted_params = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
    signature = hmac.new(PRIVATE_KEY.encode(), sorted_params.encode(), hashlib.sha1).digest()
    return base64.b64encode(signature).decode()

def kanoon_search(query, maxcites=3, doctypes="supremecourt,highcourts"):
    params = {
        "formInput": query,
        "maxcites": maxcites,
        "doctypes": doctypes,
        "publicKey": PUBLIC_KEY
    }
    params["signature"] = sign_request(params)
    response = requests.get(KANOON_API_URL, params=params)
    response.raise_for_status()
    return response.json()

@app.post("/analyze")
async def analyze_draft(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        text = extract_text(tmp_path)
        issues = spot_legal_issues(text)
        case_results = []
        for issue in issues:
            try:
                res = kanoon_search(issue, maxcites=5)
                matched = []
                for doc in res.get("results", [])[:3]:
                    matched.append({
                        "name": doc.get("caseName"),
                        "citation": doc.get("citation"),
                        "fragment": doc.get("fragmentText")
                    })
                case_results.append({"issue": issue, "cases": matched})
            except Exception as e:
                case_results.append({"issue": issue, "cases": [], "error": str(e)})
    finally:
        os.remove(tmp_path)

    return {"status": "success", "data": {"questions": issues, "cases": case_results, "draft_text": text}}

@app.post("/feedback")
async def save_feedback(draft_text: str = Form(...), predicted: str = Form(...), corrected: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO feedback (draft_text, predicted_questions, corrected_questions, timestamp) VALUES (?, ?, ?, ?)",
                   (draft_text, predicted, corrected, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Feedback saved. Model will use this data for retraining."}
