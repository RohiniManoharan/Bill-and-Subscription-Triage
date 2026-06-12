# gmail_tool.py

import os
import base64
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv
load_dotenv()
import json
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


# ── keywords that suggest bill or subscription emails ──────────────────────
BILL_KEYWORDS = [
    "invoice", "bill", "payment due", "amount due", "overdue",
    "balance", "statement", "your bill", "pay now", "past due",
    "minimum payment", "account statement"
]

SUBSCRIPTION_KEYWORDS = [
    "subscription", "renewal", "renewing", "your plan", "billing cycle",
    "auto-renew", "membership", "trial ending", "trial expires",
    "your receipt", "order confirmation", "charge", "recurring"
]

ALL_KEYWORDS = BILL_KEYWORDS + SUBSCRIPTION_KEYWORDS


def get_gmail_service():
    """Authenticate and return Gmail API service. Opens browser on first run."""
    creds = None

    if Path(TOKEN_FILE).exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def decode_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    for part in payload.get("parts", []):
        result = decode_body(part)
        if result:
            return result

    return ""


def is_relevant(subject: str, snippet: str) -> bool:
    """
    Returns True if the email looks like a bill or subscription.
    Checks subject line and snippet (first ~100 chars of body).
    """
    text = (subject + " " + snippet).lower()
    return any(keyword in text for keyword in ALL_KEYWORDS)


def fetch_relevant_emails(max_scan: int = 50) -> list[dict]:
    """
    Scans up to max_scan unread emails and returns only
    those that appear to be bills or subscriptions.
    """
    service = get_gmail_service()

    # Step 1 — get list of unread inbox email IDs
    results = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=max_scan
    ).execute()

    message_refs = results.get("messages", [])

    if not message_refs:
        print("No unread emails found.")
        return []

    relevant = []

    # Step 2 — fetch each email and filter
    for ref in message_refs:
        msg = service.users().messages().get(
            userId="me",
            id=ref["id"],
            format="full"
        ).execute()

        # extract headers
        headers = {
            h["name"].lower(): h["value"]
            for h in msg["payload"]["headers"]
        }

        subject = headers.get("subject", "")
        sender  = headers.get("from", "")
        date    = headers.get("date", "")
        snippet = msg.get("snippet", "")
        body    = decode_body(msg["payload"])

        # Step 3 — apply keyword filter
        if not is_relevant(subject, snippet):
            #print(f"SKIP → {subject[:60]}")
            continue

        print(f"MATCH → {subject[:60]}")

        relevant.append({
            "id":       msg["id"],
            "subject":  subject,
            "sender":   sender,
            "date":     date,
            "snippet":  snippet,
            "body":     body or snippet,  # fallback to snippet if body empty
        })

    return relevant



from langchain_openai import ChatOpenAI
from datetime import datetime
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
import os
api_key = os.getenv("OPENAI_API_KEY")
def extract_bill_details(email_text: str) -> dict:
    """
    Uses LLM to extract structured details from a bill/subscription email.
    Returns dict with company, amount, due_date, category, urgency.
    """
     # GET TODAY'S DATE
    today = datetime.now().strftime("%Y-%m-%d")
    today_date = datetime.now().strftime("%A, %B %d, %Y")
    
    prompt = f"""Extract billing details from this email.
Respond with ONLY a JSON object, no explanation, no markdown.

CURRENT DATE: Today is {today_date} ({today})

Rules:
- due_date: convert to YYYY-MM-DD format. If it says "in 3 days", calculate: today ({today}) + 3 days = YYYY-MM-DD
- If a field is not found, use null.
- urgency: "urgent" if due within 10 days of TODAY ({today}) or overdue, otherwise "medium" if due within 20 days of TODAY ({today})
- category: "bill" or "subscription"

Required JSON format:
{{
  "company":    "name of the company",
  "amount":     "dollar amount as string e.g. $42.50",
  "due_date":   "YYYY-MM-DD or null",
  "category":   "bill or subscription",
  "urgency":    "urgent or medium",
  "confidence": "high or low"
}}

Email:
{email_text}
"""

    response = llm.invoke([HumanMessage(content=prompt)])

    try:
        # strip markdown fences if model adds them
        raw = response.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except json.JSONDecodeError:
        # fallback if LLM response is malformed
        return {
            "company":    "Unknown",
            "amount":     None,
            "due_date":   None,
            "category":   "bill",
            "urgency":    "medium",
            "confidence": "low"
        }