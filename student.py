# app.py
import streamlit as st
import pandas as pd
import qrcode
import io
import base64
from datetime import datetime, time, timedelta
import hashlib
import sqlite3
from PIL import Image
import plotly.express as px
import plotly.graph_objects as go
from streamlit_option_menu import option_menu
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
import os
from dotenv import load_dotenv
import time as timelib
import qrcode.constants

# Load environment variables
load_dotenv()

# Email configuration
EMAIL_CONFIG = {
    'host': os.getenv('EMAIL_HOST', 'smtp.gmail.com'),
    'port': int(os.getenv('EMAIL_PORT', 587)),
    'user': os.getenv('EMAIL_USER'),
    'password': os.getenv('EMAIL_PASSWORD'),
    'use_tls': os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
}

# Database setup with proper schema and migration
def init_database():
    """Initialize the database with proper schema and handle migrations"""
    conn = sqlite3.connect('attendance_system.db')
    c = conn.cursor()
    
    # Create students table with correct schema
    c.execute('''CREATE TABLE IF NOT EXISTS students
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  full_name TEXT NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  phone TEXT UNIQUE NOT NULL,
                  student_code TEXT UNIQUE NOT NULL,
                  registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active BOOLEAN DEFAULT 1)''')
    
    # Verify students table columns
    c.execute("PRAGMA table_info(students)")
    students_columns = [column[1] for column in c.fetchall()]
    print("Students table columns:", students_columns)
    
    # Check if attendance table exists
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
    table_exists = c.fetchone()
    
    if not table_exists:
        # Create new attendance table with correct schema
        c.execute('''CREATE TABLE attendance
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      student_code TEXT NOT NULL,
                      sign_in_time TIMESTAMP,
                      sign_out_time TIMESTAMP,
                      attendance_date DATE DEFAULT CURRENT_DATE,
                      sign_in_attempts INTEGER DEFAULT 0,
                      sign_out_attempts INTEGER DEFAULT 0,
                      email_sent_signin BOOLEAN DEFAULT 0,
                      email_sent_signout BOOLEAN DEFAULT 0,
                      last_attempt_time TIMESTAMP,
                      FOREIGN KEY (student_code) REFERENCES students (student_code),
                      UNIQUE(student_code, attendance_date))''')
        print("Created new attendance table")
    else:
        # Check if old table has correct columns
        c.execute("PRAGMA table_info(attendance)")
        columns = [column[1] for column in c.fetchall()]
        
        required_columns = ['sign_in_time', 'sign_out_time', 'attendance_date', 
                          'sign_in_attempts', 'sign_out_attempts', 
                          'email_sent_signin', 'email_sent_signout', 'last_attempt_time',
                          'student_code']
        
        # If table exists but missing columns, recreate it
        missing_columns = [col for col in required_columns if col not in columns]
        if missing_columns:
            print(f"Missing columns in attendance table: {missing_columns}")
            print("Recreating attendance table...")
            
            # Drop old table and create new one
            c.execute('DROP TABLE IF EXISTS attendance_old')
            c.execute('ALTER TABLE attendance RENAME TO attendance_old')
            
            # Create new table
            c.execute('''CREATE TABLE attendance
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          student_code TEXT NOT NULL,
                          sign_in_time TIMESTAMP,
                          sign_out_time TIMESTAMP,
                          attendance_date DATE DEFAULT CURRENT_DATE,
                          sign_in_attempts INTEGER DEFAULT 0,
                          sign_out_attempts INTEGER DEFAULT 0,
                          email_sent_signin BOOLEAN DEFAULT 0,
                          email_sent_signout BOOLEAN DEFAULT 0,
                          last_attempt_time TIMESTAMP,
                          FOREIGN KEY (student_code) REFERENCES students (student_code),
                          UNIQUE(student_code, attendance_date))''')
            
            # Try to migrate old data if possible
            try:
                c.execute('''SELECT * FROM attendance_old''')
                old_data = c.fetchall()
                if old_data:
                    for row in old_data:
                        # Map old columns to new ones based on available data
                        student_code = row[1] if len(row) > 1 else None
                        attendance_date = row[2] if len(row) > 2 else datetime.now().date()
                        if student_code:
                            c.execute('''INSERT OR IGNORE INTO attendance 
                                        (student_code, attendance_date)
                                        VALUES (?, ?)''',
                                     (student_code, attendance_date))
            except:
                pass
            print("Migration complete")
    
    # Create email logs table
    c.execute('''CREATE TABLE IF NOT EXISTS email_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  student_code TEXT NOT NULL,
                  email_type TEXT NOT NULL,
                  sent_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  status TEXT,
                  error_message TEXT,
                  recipient_email TEXT,
                  FOREIGN KEY (student_code) REFERENCES students (student_code))''')
    
    # Verify email_logs table columns
    c.execute("PRAGMA table_info(email_logs)")
    email_logs_columns = [column[1] for column in c.fetchall()]
    print("Email logs table columns:", email_logs_columns)
    
    conn.commit()
    conn.close()

# Generate unique student code
def generate_student_code(email, phone):
    """Generate a unique student code"""
    unique_string = f"{email}{phone}{datetime.now().strftime('%Y%m%d%H%M%S%f')}{secrets.token_hex(8)}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:12].upper()

# Generate QR Code
def generate_qr_code(data):
    """Generate QR code for the given data"""
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5,
        error_correction=qrcode.constants.ERROR_CORRECT_H
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert PIL image to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()
    
    return img_bytes

# Send email function with retry logic
def send_email(recipient_email, student_name, attendance_type, timestamp, student_code, retry_count=0):
    """
    Send email notification for sign-in or sign-out with retry logic
    """
    max_retries = 3
    
    if not EMAIL_CONFIG['user'] or not EMAIL_CONFIG['password']:
        return False, "Email not configured"
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = EMAIL_CONFIG['user']
        msg['To'] = recipient_email
        msg['Subject'] = f"🎓 Attendance {attendance_type} Confirmation - {student_name}"
        
        # Current time formatting
        time_str = timestamp.strftime('%I:%M %p')
        date_str = timestamp.strftime('%B %d, %Y')
        
        # HTML Email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; margin: 0; padding: 0; background-color: #f4f4f4;">
            <div style="max-width: 600px; margin: 20px auto; background-color: #ffffff; border-radius: 15px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1);">
                <!-- Header -->
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                    <h1 style="color: white; margin: 0; font-size: 28px;">📚 Attendance System</h1>
                </div>
                
                <!-- Content -->
                <div style="padding: 40px 30px;">
                    <h2 style="color: #333; margin-top: 0;">Hello {student_name}!</h2>
                    
                    <div style="background-color: {('#4CAF50' if attendance_type == 'IN' else '#FF9800')}; color: white; padding: 20px; border-radius: 10px; text-align: center; margin: 30px 0;">
                        <h3 style="margin: 0; font-size: 24px;">✓ Successfully Signed {attendance_type}</h3>
                    </div>
                    
                    <div style="background-color: #f9f9f9; padding: 25px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #555; margin-top: 0; border-bottom: 2px solid #eee; padding-bottom: 10px;">Attendance Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 12px 0; color: #666; width: 40%;"><strong>📋 Student Code:</strong></td>
                                <td style="padding: 12px 0; color: #333;"><code style="background: #eee; padding: 4px 8px; border-radius: 4px;">{student_code}</code></td>
                            </tr>
                            <tr>
                                <td style="padding: 12px 0; color: #666;"><strong>⏰ Time:</strong></td>
                                <td style="padding: 12px 0; color: #333;">{time_str}</td>
                            </tr>
                            <tr>
                                <td style="padding: 12px 0; color: #666;"><strong>📅 Date:</strong></td>
                                <td style="padding: 12px 0; color: #333;">{date_str}</td>
                            </tr>
                            <tr>
                                <td style="padding: 12px 0; color: #666;"><strong>📍 Status:</strong></td>
                                <td style="padding: 12px 0; color: #333;">{'Present' if attendance_type == 'IN' else 'Departed'}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background-color: #e3f2fd; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <p style="margin: 0; color: #1976d2; font-style: italic;">
                            💡 This is an automated notification. Please keep this email for your records.
                        </p>
                    </div>
                </div>
                
                <!-- Footer -->
                <div style="background-color: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #dee2e6;">
                    <p style="color: #6c757d; margin: 5px 0;">© 2024 Student Attendance System. All rights reserved.</p>
                    <p style="color: #6c757d; margin: 5px 0; font-size: 12px;">This is an automated message, please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text alternative
        text_body = f"""
        Attendance {attendance_type} Confirmation - {student_name}
        
        Hello {student_name}!
        
        You have been successfully signed {attendance_type} at {time_str} on {date_str}.
        
        Details:
        - Student Code: {student_code}
        - Time: {time_str}
        - Date: {date_str}
        - Status: {'Present' if attendance_type == 'IN' else 'Departed'}
        
        This is an automated notification. Please keep this for your records.
        
        Student Attendance System
        """
        
        # Attach both plain text and HTML versions
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        # Send email with timeout
        server = smtplib.SMTP(EMAIL_CONFIG['host'], EMAIL_CONFIG['port'], timeout=30)
        if EMAIL_CONFIG['use_tls']:
            server.starttls()
        server.login(EMAIL_CONFIG['user'], EMAIL_CONFIG['password'])
        server.send_message(msg)
        server.quit()
        
        return True, "Email sent successfully"
        
    except smtplib.SMTPAuthenticationError:
        return False, "Email authentication failed. Check your credentials."
    except smtplib.SMTPException as e:
        if retry_count < max_retries:
            timelib.sleep(2 ** retry_count)  # Exponential backoff
            return send_email(recipient_email, student_name, attendance_type, timestamp, student_code, retry_count + 1)
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"

# Log email status
def log_email_status(student_code, email_type, status, error_message="", recipient_email=""):
    """Log email sending status"""
    conn = sqlite3.connect('attendance_system.db')
    c = conn.cursor()
    c.execute('''INSERT INTO email_logs (student_code, email_type, status, error_message, recipient_email)
                 VALUES (?, ?, ?, ?, ?)''',
              (student_code, email_type, status, error_message, recipient_email))
    conn.commit()
    conn.close()

# Check if current time is within sign-in/out window
def get_attendance_action():
    """Determine if current time is within attendance windows"""
    current_time = datetime.now()
    current_hour = current_time.hour
    current_minute = current_time.minute
    
    # Sign-in window: 7 PM to 7:30 PM (19:00 to 19:30)
    if current_hour == 19 and current_minute <= 30:
        return "sign_in"
    # Sign-out window: 1 PM to 1:30 PM (13:00 to 13:30)
    elif current_hour == 13 and current_minute <= 30:
        return "sign_out"
    else:
        return None

# Process attendance scan with duplicate prevention
def process_attendance_scan(student_code):
    """Process attendance scan with comprehensive duplicate checking"""
    conn = sqlite3.connect('attendance_system.db')
    c = conn.cursor()
    
    action = get_attendance_action()
    current_time = datetime.now()
    today = current_time.date()
    
    # Get student details
    c.execute('''SELECT full_name, email FROM students 
                 WHERE student_code = ? AND is_active = 1''', 
              (student_code,))
    student = c.fetchone()
    
    if not student:
        conn.close()
        return False, "❌ Invalid or inactive student code!", None, None
    
    student_name, student_email = student
    
    # Check if attendance record exists for today (using attendance_date)
    c.execute('''SELECT id, sign_in_time, sign_out_time, 
                        sign_in_attempts, sign_out_attempts
                 FROM attendance 
                 WHERE student_code = ? AND attendance_date = ?''',
              (student_code, today))
    
    record = c.fetchone()
    
    if action == "sign_in":
        if record:
            record_id, sign_in_time, sign_out_time, sign_in_attempts, sign_out_attempts = record
            
            if sign_in_time is not None:
                # Already signed in
                conn.close()
                try:
                    sign_in_time_obj = datetime.fromisoformat(sign_in_time) if isinstance(sign_in_time, str) else sign_in_time
                    time_str = sign_in_time_obj.strftime('%I:%M %p')
                except:
                    time_str = "unknown time"
                return False, f"⚠️ Already signed in today at {time_str}", student_name, None
            
            # Update attempts
            c.execute('''UPDATE attendance 
                        SET sign_in_attempts = sign_in_attempts + 1,
                            last_attempt_time = ?
                        WHERE id = ?''',
                     (current_time, record_id))
        else:
            # Create new attendance record
            c.execute('''INSERT INTO attendance 
                        (student_code, sign_in_time, sign_in_attempts, attendance_date, last_attempt_time)
                        VALUES (?, ?, 1, ?, ?)''',
                     (student_code, current_time, today, current_time))
        
        # Send email notification
        email_sent, email_message = send_email(
            student_email, 
            student_name, 
            "IN", 
            current_time,
            student_code
        )
        
        # Update email sent status
        if record:
            c.execute('''UPDATE attendance SET email_sent_signin = 1 
                        WHERE student_code = ? AND attendance_date = ?''',
                     (student_code, today))
        
        # Log email status
        log_email_status(
            student_code, 
            "sign_in", 
            "success" if email_sent else "failed", 
            "" if email_sent else email_message,
            student_email
        )
        
        conn.commit()
        conn.close()
        
        if email_sent:
            return True, f"✅ Successfully signed in! Email sent to {student_email}", student_name, current_time
        else:
            return True, f"✅ Successfully signed in! ⚠️ Email notification failed: {email_message}", student_name, current_time
    
    elif action == "sign_out":
        if not record:
            conn.close()
            return False, "⚠️ Cannot sign out - no sign-in record for today!", student_name, None
        
        record_id, sign_in_time, sign_out_time, sign_in_attempts, sign_out_attempts = record
        
        if sign_in_time is None:
            conn.close()
            return False, "⚠️ Cannot sign out - you haven't signed in today!", student_name, None
        
        if sign_out_time is not None:
            # Already signed out
            conn.close()
            try:
                sign_out_time_obj = datetime.fromisoformat(sign_out_time) if isinstance(sign_out_time, str) else sign_out_time
                time_str = sign_out_time_obj.strftime('%I:%M %p')
            except:
                time_str = "unknown time"
            return False, f"⚠️ Already signed out today at {time_str}", student_name, None
        
        # Update sign out
        c.execute('''UPDATE attendance 
                    SET sign_out_time = ?,
                        sign_out_attempts = sign_out_attempts + 1,
                        last_attempt_time = ?
                    WHERE id = ?''',
                 (current_time, current_time, record_id))
        
        # Send email notification
        email_sent, email_message = send_email(
            student_email, 
            student_name, 
            "OUT", 
            current_time,
            student_code
        )
        
        # Update email sent status
        c.execute('''UPDATE attendance SET email_sent_signout = 1 
                    WHERE student_code = ? AND attendance_date = ?''',
                 (student_code, today))
        
        # Log email status
        log_email_status(
            student_code, 
            "sign_out", 
            "success" if email_sent else "failed", 
            "" if email_sent else email_message,
            student_email
        )
        
        conn.commit()
        conn.close()
        
        if email_sent:
            return True, f"✅ Successfully signed out! Email sent to {student_email}", student_name, current_time
        else:
            return True, f"✅ Successfully signed out! ⚠️ Email notification failed: {email_message}", student_name, current_time
    
    else:
        conn.close()
        # Outside attendance hours
        current_time_str = current_time.strftime('%I:%M %p')
        return False, f"⏰ Attendance can only be marked during:\n• Sign-in: 7:00 PM - 7:30 PM\n• Sign-out: 1:00 PM - 1:30 PM\nCurrent time: {current_time_str}", student_name, None

# Safe database query function with error handling
def safe_read_sql_query(query, conn, params=None):
    """Safely execute SQL query with error handling"""
    try:
        if params:
            return pd.read_sql_query(query, conn, params=params)
        else:
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return pd.DataFrame()

# Get table column info
def get_table_columns(conn, table_name):
    """Get column names for a table"""
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({table_name})")
    return [column[1] for column in c.fetchall()]

# Main app
def main():
    st.set_page_config(
        page_title="Student Attendance System", 
        page_icon="🎓", 
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize database
    init_database()
    
    # Custom CSS
    st.markdown("""
        <style>
        /* Main header styling */
        .main-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 15px;
            color: white;
            text-align: center;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        /* Card styling */
        .custom-card {
            background: white;
            padding: 1.5rem;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 1rem;
        }
        
        /* Status boxes */
        .success-box {
            padding: 1rem;
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 10px;
            color: #155724;
            margin: 1rem 0;
        }
        
        .warning-box {
            padding: 1rem;
            background-color: #fff3cd;
            border: 1px solid #ffeeba;
            border-radius: 10px;
            color: #856404;
            margin: 1rem 0;
        }
        
        .error-box {
            padding: 1rem;
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 10px;
            color: #721c24;
            margin: 1rem 0;
        }
        
        .info-box {
            padding: 1rem;
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            border-radius: 10px;
            color: #0c5460;
            margin: 1rem 0;
        }
        
        /* Button styling */
        .stButton > button {
            width: 100%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: bold;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 5px;
            transition: all 0.3s ease;
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        
        /* Metric styling */
        .metric-card {
            background: white;
            padding: 1rem;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* QR code container */
        .qr-container {
            background: white;
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("""
            <div style="text-align: center; padding: 1rem;">
                <h1 style="color: #667eea;">🎓</h1>
                <h2 style="color: #333;">Attendance System</h2>
            </div>
        """, unsafe_allow_html=True)
        
        selected = option_menu(
            menu_title=None,
            options=["Registration", "Scan Attendance", "Analytics", "Email Logs", "Settings"],
            icons=["person-plus", "qr-code-scan", "graph-up", "envelope", "gear"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#fafafa"},
                "icon": {"color": "#667eea", "font-size": "20px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px"},
                "nav-link-selected": {"background-color": "#667eea"},
            }
        )
        
        # Email status indicator
        st.markdown("---")
        if EMAIL_CONFIG['user'] and EMAIL_CONFIG['password']:
            st.success("✅ Email System: Active")
        else:
            st.warning("⚠️ Email System: Not Configured")
            with st.expander("📧 Email Setup"):
                st.markdown("""
                **Configure Email:**
                1. Create `.env` file
                2. Add your credentials:
                ```
                EMAIL_USER=your-email@gmail.com
                EMAIL_PASSWORD=your-app-password
                ```
                
                **For Gmail:**
                - Enable 2FA
                - Generate App Password
                """)
    
    # Registration Page
    if selected == "Registration":
        st.markdown("<div class='main-header'><h1>📝 Student Registration</h1><p>Register to get your unique QR code</p></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### 📋 Registration Form")
            
            with st.form("registration_form"):
                full_name = st.text_input("Full Name *", placeholder="Enter your full name")
                email = st.text_input("Email Address *", placeholder="Enter your email")
                phone = st.text_input("Phone Number *", placeholder="Enter your phone number")
                
                col_accept, col_submit = st.columns(2)
                with col_accept:
                    accept_terms = st.checkbox("✅ I agree to receive email notifications")
                with col_submit:
                    submitted = st.form_submit_button("Register Now", use_container_width=True)
                
                if submitted:
                    if full_name and email and phone:
                        if accept_terms:
                            try:
                                conn = sqlite3.connect('attendance_system.db')
                                c = conn.cursor()
                                
                                # Check if email already exists
                                c.execute("SELECT * FROM students WHERE email = ?", (email,))
                                if c.fetchone():
                                    st.error("❌ Email address already registered!")
                                    conn.close()
                                else:
                                    # Check if phone already exists
                                    c.execute("SELECT * FROM students WHERE phone = ?", (phone,))
                                    if c.fetchone():
                                        st.error("❌ Phone number already registered!")
                                        conn.close()
                                    else:
                                        # Generate unique student code
                                        student_code = generate_student_code(email, phone)
                                        
                                        # Insert student data
                                        c.execute('''INSERT INTO students (full_name, email, phone, student_code)
                                                     VALUES (?, ?, ?, ?)''',
                                                  (full_name, email, phone, student_code))
                                        
                                        conn.commit()
                                        
                                        # Generate QR code
                                        qr_bytes = generate_qr_code(student_code)
                                        
                                        # Store in session state
                                        st.session_state['qr_bytes'] = qr_bytes
                                        st.session_state['student_code'] = student_code
                                        st.session_state['full_name'] = full_name
                                        st.session_state['email'] = email
                                        
                                        st.success("✅ Registration successful!")
                                        
                                        # Send welcome email
                                        if EMAIL_CONFIG['user'] and EMAIL_CONFIG['password']:
                                            with st.spinner("Sending welcome email..."):
                                                welcome_sent, welcome_msg = send_email(
                                                    email, 
                                                    full_name, 
                                                    "REGISTRATION", 
                                                    datetime.now(),
                                                    student_code
                                                )
                                                if welcome_sent:
                                                    st.info("📧 Welcome email sent to your inbox")
                                                else:
                                                    st.warning(f"⚠️ Welcome email failed: {welcome_msg}")
                                        
                                        conn.close()
                            except sqlite3.IntegrityError:
                                st.error("❌ Registration failed! Please try again.")
                            except Exception as e:
                                st.error(f"❌ An error occurred: {str(e)}")
                    else:
                        st.warning("⚠️ Please fill all required fields!")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            if 'qr_bytes' in st.session_state:
                st.markdown("<div class='qr-container'>", unsafe_allow_html=True)
                st.markdown("### 🎯 Your QR Code")
                
                # Display QR code
                st.image(st.session_state['qr_bytes'], width=250)
                
                # Student details
                st.markdown("---")
                st.markdown(f"**👤 Name:** {st.session_state['full_name']}")
                st.markdown(f"**📧 Email:** {st.session_state['email']}")
                st.markdown(f"**🔑 Student Code:** `{st.session_state['student_code']}`")
                
                # Download button
                b64 = base64.b64encode(st.session_state['qr_bytes']).decode()
                href = f'''
                <a href="data:image/png;base64,{b64}" 
                   download="qr_code_{st.session_state['student_code']}.png"
                   style="display: inline-block; padding: 10px 20px; 
                          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                          color: white; text-decoration: none; border-radius: 5px;
                          margin-top: 10px;">
                    📥 Download QR Code
                </a>
                '''
                st.markdown(href, unsafe_allow_html=True)
                
                st.markdown("---")
                st.markdown("""
                <div class='info-box'>
                    <h4>📌 Important Notes:</h4>
                    <ul>
                        <li>Save this QR code for attendance</li>
                        <li>You'll receive email notifications</li>
                        <li>Keep your student code confidential</li>
                        <li>Attendance hours: 7-7:30 PM (sign-in), 1-1:30 PM (sign-out)</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class='info-box'>
                    <h4>👋 Welcome!</h4>
                    <p>Complete the registration form to get your unique QR code.</p>
                    <p>After registration, you'll receive:</p>
                    <ul>
                        <li>Unique QR code for attendance</li>
                        <li>Welcome email confirmation</li>
                        <li>Email notifications for each attendance</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
    
    # Scan Attendance Page
    elif selected == "Scan Attendance":
        st.markdown("<div class='main-header'><h1>📱 Scan Attendance</h1><p>Mark your attendance by scanning QR code</p></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### 🔍 Manual Code Entry")
            
            # Manual entry form
            with st.form("manual_entry"):
                student_code = st.text_input("Enter Student Code", placeholder="Enter or scan the student code").upper()
                scan_submitted = st.form_submit_button("Submit Attendance", use_container_width=True)
                
                if scan_submitted and student_code:
                    with st.spinner("Processing attendance..."):
                        success, message, student_name, timestamp = process_attendance_scan(student_code)
                        
                        if success:
                            st.markdown(f"""
                            <div class='success-box'>
                                <h4>✅ Attendance Recorded!</h4>
                                <p><strong>Student:</strong> {student_name}</p>
                                <p><strong>Time:</strong> {timestamp.strftime('%I:%M %p') if timestamp else 'N/A'}</p>
                                <p><strong>Message:</strong> {message}</p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class='warning-box'>
                                <h4>⚠️ Attendance Failed</h4>
                                <p>{message}</p>
                            </div>
                            """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Recent activity
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### 📋 Recent Activity")
            
            conn = sqlite3.connect('attendance_system.db')
            try:
                recent = pd.read_sql_query('''
                    SELECT s.full_name, a.sign_in_time, a.sign_out_time, a.attendance_date
                    FROM attendance a
                    JOIN students s ON a.student_code = s.student_code
                    WHERE a.attendance_date = date('now')
                    ORDER BY a.sign_in_time DESC
                    LIMIT 5
                ''', conn)
                
                if not recent.empty:
                    for _, row in recent.iterrows():
                        sign_in = row['sign_in_time'][:19] if row['sign_in_time'] and pd.notna(row['sign_in_time']) else 'Not signed in'
                        sign_out = row['sign_out_time'][:19] if row['sign_out_time'] and pd.notna(row['sign_out_time']) else 'Not signed out'
                        st.markdown(f"""
                        <div style="padding: 10px; border-bottom: 1px solid #eee;">
                            <strong>{row['full_name']}</strong><br>
                            <small>In: {sign_in}</small><br>
                            <small>Out: {sign_out}</small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No activity today")
            except Exception as e:
                st.info("No recent activity")
            finally:
                conn.close()
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### ⏰ Current Status")
            
            # Display current time and attendance window
            current_time = datetime.now()
            st.metric("Current Time", current_time.strftime("%I:%M %p"))
            st.metric("Current Date", current_time.strftime("%Y-%m-%d"))
            
            # Show attendance window
            action = get_attendance_action()
            if action == "sign_in":
                st.markdown("""
                <div class='success-box'>
                    <h4>🟢 Sign-in Active</h4>
                    <p>7:00 PM - 7:30 PM</p>
                </div>
                """, unsafe_allow_html=True)
            elif action == "sign_out":
                st.markdown("""
                <div class='success-box'>
                    <h4>🟢 Sign-out Active</h4>
                    <p>1:00 PM - 1:30 PM</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class='info-box'>
                    <h4>🔴 Inactive</h4>
                    <p><strong>Sign-in:</strong> 7:00-7:30 PM</p>
                    <p><strong>Sign-out:</strong> 1:00-1:30 PM</p>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### 📱 How to Scan")
            st.markdown("""
            1. Open camera on phone
            2. Point at QR code
            3. Code will be auto-detected
            4. Or enter manually above
            5. Check email for confirmation
            """)
            st.markdown("</div>", unsafe_allow_html=True)
    
    # Analytics Page
    elif selected == "Analytics":
        st.markdown("<div class='main-header'><h1>📊 Analytics Dashboard</h1><p>Track attendance and registration metrics</p></div>", unsafe_allow_html=True)
        
        # Filters
        st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
        st.markdown("### 🔍 Filters")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            name_filter = st.text_input("Filter by Name", placeholder="Enter name...")
        with col2:
            email_filter = st.text_input("Filter by Email", placeholder="Enter email...")
        with col3:
            phone_filter = st.text_input("Filter by Phone", placeholder="Enter phone...")
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start Date", datetime.now().date() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End Date", datetime.now().date())
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Fetch data
        conn = sqlite3.connect('attendance_system.db')
        
        try:
            # Get table columns to verify structure
            students_cols = get_table_columns(conn, 'students')
            attendance_cols = get_table_columns(conn, 'attendance')
            
            # Student registration query with filters
            student_query = "SELECT * FROM students WHERE is_active = 1"
            params = []
            
            if name_filter:
                student_query += " AND full_name LIKE ?"
                params.append(f"%{name_filter}%")
            if email_filter:
                student_query += " AND email LIKE ?"
                params.append(f"%{email_filter}%")
            if phone_filter:
                student_query += " AND phone LIKE ?"
                params.append(f"%{phone_filter}%")
            
            students_df = safe_read_sql_query(student_query, conn, params=params if params else None)
            
            # Attendance query with dynamic column selection
            select_cols = ['s.full_name', 's.email', 's.phone', 'a.attendance_date']
            
            if 'sign_in_time' in attendance_cols:
                select_cols.append('a.sign_in_time')
            else:
                select_cols.append("NULL as sign_in_time")
                
            if 'sign_out_time' in attendance_cols:
                select_cols.append('a.sign_out_time')
            else:
                select_cols.append("NULL as sign_out_time")
                
            if 'email_sent_signin' in attendance_cols:
                select_cols.append('a.email_sent_signin')
            else:
                select_cols.append("0 as email_sent_signin")
                
            if 'email_sent_signout' in attendance_cols:
                select_cols.append('a.email_sent_signout')
            else:
                select_cols.append("0 as email_sent_signout")
                
            if 'sign_in_attempts' in attendance_cols:
                select_cols.append('a.sign_in_attempts')
            else:
                select_cols.append("0 as sign_in_attempts")
                
            if 'sign_out_attempts' in attendance_cols:
                select_cols.append('a.sign_out_attempts')
            else:
                select_cols.append("0 as sign_out_attempts")
            
            select_clause = ", ".join(select_cols)
            
            attendance_query = f'''
                SELECT {select_clause}
                FROM attendance a
                JOIN students s ON a.student_code = s.student_code
                WHERE date(a.attendance_date) BETWEEN date(?) AND date(?)
            '''
            
            attendance_params = [start_date, end_date]
            
            if name_filter:
                attendance_query += " AND s.full_name LIKE ?"
                attendance_params.append(f"%{name_filter}%")
            if email_filter:
                attendance_query += " AND s.email LIKE ?"
                attendance_params.append(f"%{email_filter}%")
            if phone_filter:
                attendance_query += " AND s.phone LIKE ?"
                attendance_params.append(f"%{phone_filter}%")
            
            attendance_df = safe_read_sql_query(attendance_query, conn, params=attendance_params)
            
            # Key Metrics
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### 📈 Key Metrics")
            
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.metric("Total Students", len(students_df) if not students_df.empty else 0)
            with col2:
                today = datetime.now().date()
                if not attendance_df.empty and 'attendance_date' in attendance_df.columns:
                    today_attendance = attendance_df[attendance_df['attendance_date'] == str(today)]
                else:
                    today_attendance = pd.DataFrame()
                st.metric("Today's Attendance", len(today_attendance))
            with col3:
                if not today_attendance.empty and 'sign_in_time' in today_attendance.columns:
                    signed_in_today = len(today_attendance[today_attendance['sign_in_time'].notna()])
                else:
                    signed_in_today = 0
                st.metric("Signed In Today", signed_in_today)
            with col4:
                if not today_attendance.empty and 'sign_out_time' in today_attendance.columns:
                    signed_out_today = len(today_attendance[today_attendance['sign_out_time'].notna()])
                else:
                    signed_out_today = 0
                st.metric("Signed Out Today", signed_out_today)
            with col5:
                if not attendance_df.empty:
                    emails_sent = 0
                    if 'email_sent_signin' in attendance_df.columns:
                        emails_sent += len(attendance_df[attendance_df['email_sent_signin'] == 1])
                    if 'email_sent_signout' in attendance_df.columns:
                        emails_sent += len(attendance_df[attendance_df['email_sent_signout'] == 1])
                else:
                    emails_sent = 0
                st.metric("Emails Sent", emails_sent)
            
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                st.markdown("### 📊 Daily Attendance Trend")
                if not attendance_df.empty and 'attendance_date' in attendance_df.columns:
                    daily_counts = attendance_df.groupby('attendance_date').size().reset_index(name='count')
                    fig = px.line(daily_counts, x='attendance_date', y='count', 
                                title='Daily Attendance Over Time',
                                labels={'attendance_date': 'Date', 'count': 'Number of Students'})
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No attendance data available")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
                st.markdown("### 📧 Email Notifications")
                if not attendance_df.empty:
                    email_stats_data = []
                    if 'email_sent_signin' in attendance_df.columns:
                        email_stats_data.append({
                            'Type': 'Sign-in Emails',
                            'Sent': len(attendance_df[attendance_df['email_sent_signin'] == 1])
                        })
                    if 'email_sent_signout' in attendance_df.columns:
                        email_stats_data.append({
                            'Type': 'Sign-out Emails',
                            'Sent': len(attendance_df[attendance_df['email_sent_signout'] == 1])
                        })
                    
                    if email_stats_data:
                        email_stats = pd.DataFrame(email_stats_data)
                        fig = px.bar(email_stats, x='Type', y='Sent', 
                                   title='Email Notifications Sent',
                                   color='Type',
                                   color_discrete_sequence=['#667eea', '#764ba2'])
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No email data available")
                else:
                    st.info("No email data available")
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Data tables
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            tab1, tab2 = st.tabs(["📋 Student List", "📋 Attendance Records"])
            
            with tab1:
                st.markdown("### Registered Students")
                if not students_df.empty:
                    display_cols = ['full_name', 'email', 'phone', 'student_code', 'registration_date']
                    available_cols = [col for col in display_cols if col in students_df.columns]
                    students_display = students_df[available_cols]
                    
                    # Rename columns
                    column_names = []
                    for col in available_cols:
                        if col == 'full_name':
                            column_names.append('Full Name')
                        elif col == 'email':
                            column_names.append('Email')
                        elif col == 'phone':
                            column_names.append('Phone')
                        elif col == 'student_code':
                            column_names.append('Student Code')
                        elif col == 'registration_date':
                            column_names.append('Registration Date')
                        else:
                            column_names.append(col)
                    
                    students_display.columns = column_names
                    st.dataframe(students_display, use_container_width=True, hide_index=True)
                    
                    # Download button
                    csv = students_display.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Student List (CSV)",
                        data=csv,
                        file_name=f"students_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No students found")
            
            with tab2:
                st.markdown("### Attendance Records")
                if not attendance_df.empty:
                    display_cols = ['full_name', 'email', 'attendance_date', 'sign_in_time', 'sign_out_time',
                                  'email_sent_signin', 'email_sent_signout']
                    available_cols = [col for col in display_cols if col in attendance_df.columns]
                    attendance_display = attendance_df[available_cols]
                    
                    # Rename columns
                    column_names = []
                    for col in available_cols:
                        if col == 'full_name':
                            column_names.append('Full Name')
                        elif col == 'email':
                            column_names.append('Email')
                        elif col == 'attendance_date':
                            column_names.append('Date')
                        elif col == 'sign_in_time':
                            column_names.append('Sign In Time')
                        elif col == 'sign_out_time':
                            column_names.append('Sign Out Time')
                        elif col == 'email_sent_signin':
                            column_names.append('Email Sent (In)')
                        elif col == 'email_sent_signout':
                            column_names.append('Email Sent (Out)')
                        else:
                            column_names.append(col)
                    
                    attendance_display.columns = column_names
                    st.dataframe(attendance_display, use_container_width=True, hide_index=True)
                    
                    # Download button
                    csv = attendance_display.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Attendance Data (CSV)",
                        data=csv,
                        file_name=f"attendance_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No attendance records found")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"An error occurred while loading analytics: {str(e)}")
        finally:
            conn.close()
    
    # Email Logs Page
    elif selected == "Email Logs":
        st.markdown("<div class='main-header'><h1>📧 Email Notification Logs</h1><p>Track all email communications</p></div>", unsafe_allow_html=True)
        
        conn = sqlite3.connect('attendance_system.db')
        
        try:
            # Get table columns
            students_cols = get_table_columns(conn, 'students')
            email_logs_cols = get_table_columns(conn, 'email_logs')
            
            # Build dynamic query based on available columns
            select_cols = []
            
            # Email logs columns
            for col in email_logs_cols:
                select_cols.append(f"e.{col}")
            
            # Students columns (avoiding duplicates)
            if 'full_name' in students_cols:
                select_cols.append("s.full_name")
            
            select_clause = ", ".join(select_cols)
            
            logs_query = f'''
                SELECT {select_clause}
                FROM email_logs e
                JOIN students s ON e.student_code = s.student_code
                ORDER BY e.sent_time DESC
                LIMIT 200
            '''
            
            logs_df = safe_read_sql_query(logs_query, conn)
            
            if not logs_df.empty:
                # Summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Emails", len(logs_df))
                with col2:
                    if 'status' in logs_df.columns:
                        success_count = len(logs_df[logs_df['status'] == 'success'])
                        success_rate = (success_count/len(logs_df))*100 if len(logs_df) > 0 else 0
                        st.metric("Successful", success_count, f"{success_rate:.1f}%")
                    else:
                        st.metric("Successful", 0)
                with col3:
                    if 'status' in logs_df.columns:
                        failed_count = len(logs_df[logs_df['status'] == 'failed'])
                        failure_rate = (failed_count/len(logs_df))*100 if len(logs_df) > 0 else 0
                        st.metric("Failed", failed_count, f"{failure_rate:.1f}%")
                    else:
                        st.metric("Failed", 0)
                with col4:
                    if 'student_code' in logs_df.columns:
                        unique_students = logs_df['student_code'].nunique()
                        st.metric("Unique Students", unique_students)
                    else:
                        st.metric("Unique Students", 0)
                
                # Display logs
                st.markdown("---")
                st.markdown("### 📋 Recent Email Activity")
                
                # Select display columns
                display_cols = []
                if 'sent_time' in logs_df.columns:
                    display_cols.append('sent_time')
                if 'full_name' in logs_df.columns:
                    display_cols.append('full_name')
                if 'recipient_email' in logs_df.columns:
                    display_cols.append('recipient_email')
                if 'email_type' in logs_df.columns:
                    display_cols.append('email_type')
                if 'status' in logs_df.columns:
                    display_cols.append('status')
                if 'error_message' in logs_df.columns:
                    display_cols.append('error_message')
                
                if display_cols:
                    logs_display = logs_df[display_cols]
                    
                    # Rename columns
                    column_names = []
                    for col in display_cols:
                        if col == 'sent_time':
                            column_names.append('Time Sent')
                        elif col == 'full_name':
                            column_names.append('Student Name')
                        elif col == 'recipient_email':
                            column_names.append('Recipient')
                        elif col == 'email_type':
                            column_names.append('Type')
                        elif col == 'status':
                            column_names.append('Status')
                        elif col == 'error_message':
                            column_names.append('Error Message')
                        else:
                            column_names.append(col)
                    
                    logs_display.columns = column_names
                    
                    # Fill NaN values
                    logs_display = logs_display.fillna('')
                    
                    st.dataframe(logs_display, use_container_width=True, hide_index=True)
                    
                    # Download logs
                    csv = logs_display.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Email Logs (CSV)",
                        data=csv,
                        file_name=f"email_logs_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No displayable columns found")
            else:
                st.info("No email logs available")
        
        except Exception as e:
            st.error(f"Error loading email logs: {str(e)}")
        finally:
            conn.close()
    
    # Settings Page
    elif selected == "Settings":
        st.markdown("<div class='main-header'><h1>⚙️ System Settings</h1><p>Configure system parameters</p></div>", unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### ⏰ Attendance Windows")
            
            st.markdown("**Current Settings:**")
            st.markdown("""
            - **Sign-in Window:** 7:00 PM - 7:30 PM
            - **Sign-out Window:** 1:00 PM - 1:30 PM
            """)
            
            st.markdown("---")
            st.markdown("### 📧 Email Configuration")
            
            if EMAIL_CONFIG['user']:
                st.success(f"✅ Email configured for: {EMAIL_CONFIG['user']}")
            else:
                st.warning("⚠️ Email not configured")
                
                with st.form("email_config"):
                    email_user = st.text_input("Email Address", placeholder="your-email@gmail.com")
                    email_password = st.text_input("App Password", type="password", 
                                                  placeholder="16-digit app password")
                    email_host = st.text_input("SMTP Host", value="smtp.gmail.com")
                    email_port = st.number_input("SMTP Port", value=587)
                    
                    if st.form_submit_button("Save Configuration"):
                        st.success("Configuration saved! Please update your .env file and restart the app.")
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("<div class='custom-card'>", unsafe_allow_html=True)
            st.markdown("### 📊 System Statistics")
            
            conn = sqlite3.connect('attendance_system.db')
            try:
                # Get stats
                total_students = pd.read_sql_query("SELECT COUNT(*) as count FROM students", conn).iloc[0]['count']
                total_attendance = pd.read_sql_query("SELECT COUNT(*) as count FROM attendance", conn).iloc[0]['count']
                total_emails = pd.read_sql_query("SELECT COUNT(*) as count FROM email_logs", conn).iloc[0]['count']
                
                st.metric("Total Students Registered", total_students)
                st.metric("Total Attendance Records", total_attendance)
                st.metric("Total Emails Sent", total_emails)
                
                st.markdown("---")
                st.markdown("### 🗄️ Database Management")
                
                if st.button("🔄 Reset Database", type="secondary"):
                    if st.checkbox("I understand this will delete all data"):
                        # Backup first
                        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                        try:
                            import shutil
                            shutil.copy("attendance_system.db", backup_name)
                            st.success(f"Database backed up as {backup_name}")
                            
                            # Reinitialize
                            os.remove("attendance_system.db")
                            init_database()
                            st.success("Database reset successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error resetting database: {str(e)}")
            
            except Exception as e:
                st.error(f"Error loading statistics: {str(e)}")
            finally:
                conn.close()
            
            st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()