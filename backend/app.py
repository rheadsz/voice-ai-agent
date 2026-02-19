from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from db import conn  # use our helper
import os, httpx
from fastapi import Request



app = FastAPI()

VAPI_API_KEY = os.getenv("VAPI_API_KEY")
VAPI_AGENT_ID = os.getenv("VAPI_AGENT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")
VAPI_BASE = "https://api.vapi.ai"
ACQUISITIONS_LEAD_NUMBER = "+16695884446"

@app.get("/healthz")
def healthz():
    return {"ok": True}

class OutboundCallIn(BaseModel):
    to: str
    owner_name: str | None = None
    address: str | None = None

@app.post("/start-call")
async def start_call(payload: OutboundCallIn):
    if not (VAPI_API_KEY and VAPI_AGENT_ID):
        return {"ok": False, "error": "VAPI_API_KEY or VAPI_AGENT_ID missing"}
    
    if not VAPI_PHONE_NUMBER_ID:
        return {"ok": False, "error": "VAPI_PHONE_NUMBER_ID missing"}

    body = {
        "assistantId": VAPI_AGENT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": payload.to
        },
        "assistantOverrides": {
            "variableValues": {
                "owner_name": payload.owner_name or "",
                "address": payload.address or ""
            }
        }
    }

    headers = {"Authorization": f"Bearer {VAPI_API_KEY}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{VAPI_BASE}/call", json=body, headers=headers)
        print("VAPI RESPONSE:", r.status_code, r.text)
        return r.json()

#  Intent Reporting Endpoint 
@app.post("/intent/report") #my webhook
async def report_intent(request: Request):
    """
    VAPI assistant calls this when it detects seller intent.
    For now, just log it to the terminal.
    """
    data = await request.json()
    
    # Extracting intent data from VAPI's nested structure
    tool_calls = data.get('message', {}).get('toolCalls', [])
    intent_data = {}
    
    if tool_calls:
        # Gets the arguments from the first tool call
        intent_data = tool_calls[0].get('function', {}).get('arguments', {})
    
    # Extracts call details
    call_info = data.get('message', {}).get('call', {})
    customer = call_info.get('customer', {})
    assistant_overrides = call_info.get('assistantOverrides', {})
    variable_values = assistant_overrides.get('variableValues', {})
    
    print("\n")
    print("INTENT DETECTED!")
    print("\n")
    print(f"Intent: {intent_data.get('intent')}")
    print(f"Confidence: {intent_data.get('confidence')}")
    print(f"Phone: {customer.get('number')}")
    print(f"Owner: {variable_values.get('owner_name')}")
    print(f"Address: {variable_values.get('address')}")
    print("\n")
    
    return {"ok": True, "message": "Intent logged successfully"}

# --- models for request ---
class LeadIn(BaseModel):
    owner_name: Optional[str] = None
    phone: str
    address: Optional[str] = None

# POST /leads  -> upsert by phone
@app.post("/leads")
def create_or_update_lead(lead: LeadIn):
    q = """
    insert into leads (owner_name, phone, address)
    values (%s, %s, %s)
    on conflict (phone) do update set
      owner_name = coalesce(excluded.owner_name, leads.owner_name),
      address    = coalesce(excluded.address, leads.address)
    returning id, owner_name, phone, address;
    """
    with conn() as c, c.cursor() as cur:
        cur.execute(q, (lead.owner_name, lead.phone, lead.address))
        return cur.fetchone()

# GET /leads  -> list latest 50
@app.get("/leads")
def list_leads():
    with conn() as c, c.cursor() as cur:
        cur.execute("select * from leads order by last_call_at desc nulls last, id desc limit 50")
        return cur.fetchall()
