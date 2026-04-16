# database.py - PostgreSQL version for deployment
import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os

def get_db_connection():
    """Get database connection using Streamlit secrets"""
    try:
        # For local development
        if os.getenv('DATABASE_URL'):
            conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        # For Streamlit Cloud
        else:
            conn = psycopg2.connect(
                host=st.secrets["database"]["host"],
                port=st.secrets["database"]["port"],
                database=st.secrets["database"]["database"],
                user=st.secrets["database"]["user"],
                password=st.secrets["database"]["password"],
                cursor_factory=RealDictCursor
            )
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        raise

@contextmanager
def get_connection():
    """Context manager for database connections"""
    conn = get_db_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """Initialize database schema"""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Students table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT NOT NULL,
                student_code TEXT UNIQUE NOT NULL,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Attendance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(id),
                qr_code TEXT NOT NULL,
                check_in_time TIMESTAMP,
                check_out_time TIMESTAMP,
                attendance_date DATE DEFAULT CURRENT_DATE,
                check_in_email_sent INTEGER DEFAULT 0,
                check_out_email_sent INTEGER DEFAULT 0,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Scan logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scan_log (
                id SERIAL PRIMARY KEY,
                qr_code TEXT NOT NULL,
                scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT,
                status TEXT,
                details TEXT
            )
        ''')
        
        print("Database initialized successfully")