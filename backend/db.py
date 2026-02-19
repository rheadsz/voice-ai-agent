# backend/db.py
import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()  # loads backend/.env

DSN = os.getenv("DATABASE_URL")
if not DSN:
    raise RuntimeError("DATABASE_URL not set")

def conn():
    return psycopg.connect(DSN, row_factory=dict_row)
