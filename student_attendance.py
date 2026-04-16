"""Standalone Student Attendance Scanner App"""
import streamlit as st
import cv2
import numpy as np
from datetime import datetime
import sys
import os
import time

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CHECK_IN_START, CHECK_IN_END, CHECK_OUT_START, CHECK_OUT_END
from database import (
    get_student_by_qr, process_check_in, process_check_out,
    update_email_status, get_connection
)
from email_service import email_service

# Page configuration
st.set_page_config(
    page_title="Student Attendance Scanner",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Hide default menu
hide_menu_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
"""
st.markdown(hide_menu_style, unsafe_allow_html=True)

# Custom CSS for student scanner
st.markdown("""
<style>
    /* Animated gradient header */
    .main-header {
        font-size: 2.5rem;
        font-weight: 900;
        background: linear-gradient(270deg, #667eea, #764ba2, #f093fb, #4facfe);
        background-size: 300% 300%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
        animation: gradient 8s ease infinite;
    }
    
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Mode indicator cards */
    .mode-card {
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
        animation: slideIn 0.5s ease;
    }
    
    @keyframes slideIn {
        from { transform: translateY(-20px); opacity: 0; }
        to { transform: translateY(0); opacity: 1; }
    }
    
    /* Success animation */
    @keyframes successPulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    
    .success-box {
        animation: successPulse 0.5s ease;
    }
    
    /* Scanner container */
    .scanner-container {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 20px;
        border-radius: 20px;
        margin: 20px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }
    
    /* Status badge */
    .status-badge {
        display: inline-block;
        padding: 8px 20px;
        border-radius: 50px;
        font-weight: 600;
        margin: 10px 0;
    }
    
    /* Instruction card */
    .instruction-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        margin: 15px 0;
    }
    
    /* Time display */
    .time-display {
        text-align: center;
        font-size: 1.2rem;
        font-weight: 600;
        color: #333;
        background: rgba(255,255,255,0.9);
        padding: 10px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

def get_current_mode():
    """Determine current operating mode."""
    now = datetime.now().time()
    
    # Check-in window: 7 PM to 11:59 PM (19:00 to 23:59)
    if CHECK_IN_START <= now <= CHECK_IN_END:
        return "check_in", "✅ CHECK-IN MODE", "#10b981", "You can check in now"
    # Check-out window: 1 PM to 6:59 PM (13:00 to 18:59)
    elif CHECK_OUT_START <= now <= CHECK_OUT_END:
        return "check_out", "✅ CHECK-OUT MODE", "#f59e0b", "You can check out now"
    else:
        next_mode = "Check-in at 7:00 PM" if now < CHECK_IN_START else "Check-in tomorrow at 7:00 PM"
        return "inactive", "⏰ SCANNER INACTIVE", "#6b7280", f"Scanner closed. {next_mode}"

def process_attendance(qr_data, mode):
    """Process attendance based on current mode."""
    student = get_student_by_qr(qr_data)
    
    if not student:
        return False, "❌ Invalid QR Code! Please register first.", None, None
    
    student_id = int(student['id'])
    student_name = student['full_name']
    student_email = student['email']
    
    if mode == "check_in":
        result = process_check_in(student_id, qr_data)
        
        if result['success']:
            # Send email confirmation
            email_sent = email_service.send_check_in_confirmation(
                student_email, student_name, result['timestamp']
            )
            if email_sent:
                update_email_status(result['attendance_id'], 'check_in')
            
            return True, f"✅ Check-in successful!", student_name, {
                'type': 'check_in',
                'time': result['timestamp'],
                'email_sent': email_sent
            }
        
        elif result['status'] == 'duplicate':
            return False, f"⚠️ Already checked in at {result['details']}", student_name, None
        else:
            return False, f"❌ {result['message']}", student_name, None
    
    elif mode == "check_out":
        result = process_check_out(student_id, qr_data)
        
        if result['success']:
            # Send email confirmation
            email_sent = email_service.send_check_out_confirmation(
                student_email, student_name,
                result['check_in_time'], result['timestamp'],
                str(result['duration']).split('.')[0]
            )
            if email_sent:
                update_email_status(result['attendance_id'], 'check_out')
            
            return True, f"✅ Check-out successful!", student_name, {
                'type': 'check_out',
                'time': result['timestamp'],
                'duration': str(result['duration']).split('.')[0],
                'email_sent': email_sent
            }
        
        elif result['status'] == 'duplicate':
            return False, f"⚠️ Already checked out at {result['details']}", student_name, None
        else:
            return False, f"❌ {result['message']}", student_name, None
    
    return False, "Unknown error", None, None

def scanner_page():
    """Main scanner page for students."""
    st.markdown('<h1 class="main-header">📱 Student Attendance Scanner</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666; margin-bottom: 2rem;">Scan your QR code to mark attendance</p>', unsafe_allow_html=True)
    
    # Get current mode
    mode, mode_text, mode_color, mode_message = get_current_mode()
    
    # Display mode indicator
    st.markdown(f"""
    <div class="mode-card" style="background: {mode_color}20; border: 2px solid {mode_color};">
        <h2 style="color: {mode_color}; margin: 0;">{mode_text}</h2>
        <p style="color: #555; margin: 10px 0 0 0;">{mode_message}</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Display current time
    current_time = datetime.now()
    st.markdown(f"""
    <div class="time-display">
        🕐 Current Time: {current_time.strftime('%I:%M:%S %p')} | 📅 {current_time.strftime('%B %d, %Y')}
    </div>
    """, unsafe_allow_html=True)
    
    if mode == "inactive":
        st.warning("⚠️ Scanner is currently closed. Please check back during operating hours.")
        st.info(f"""
        **Operating Hours:**
        - **Check-in:** 7:00 PM - 11:59 PM
        - **Check-out:** 1:00 PM - 6:59 PM
        
        Current time: {current_time.strftime('%I:%M %p')}
        """)
        return
    
    # Initialize session state
    if 'last_processed_qr' not in st.session_state:
        st.session_state.last_processed_qr = None
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'scan_count' not in st.session_state:
        st.session_state.scan_count = 0
    if 'last_result' not in st.session_state:
        st.session_state.last_result = None
    
    # Input method selection
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        input_method = st.radio(
            "Select Input Method",
            ["📷 Camera Scan", "⌨️ Manual Entry"],
            horizontal=True,
            label_visibility="collapsed"
        )
    
    qr_data = None
    
    if input_method == "📷 Camera Scan":
        st.markdown('<div class="scanner-container">', unsafe_allow_html=True)
        
        # Auto-scan indicator
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 12px; border-radius: 10px; 
                    text-align: center; margin-bottom: 15px;">
            <span style="font-size: 1.1rem;">⚡ Auto-scan mode active - QR codes processed instantly!</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Show scan counter
        if st.session_state.scan_count > 0:
            st.markdown(f"""
            <div style="text-align: right; margin-bottom: 10px;">
                <span class="status-badge" style="background: #e0f2fe;">
                    📊 Today's scans: {st.session_state.scan_count}
                </span>
            </div>
            """, unsafe_allow_html=True)
        
        # Camera input
        camera_image = st.camera_input("Position QR code in frame", key=f"camera_{st.session_state.scan_count}")
        
        if camera_image and not st.session_state.processing:
            try:
                st.session_state.processing = True
                
                # Decode QR code
                bytes_data = camera_image.getvalue()
                nparr = np.frombuffer(bytes_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(img)
                
                if data:
                    # Check for duplicate scan
                    if data != st.session_state.last_processed_qr:
                        st.session_state.last_processed_qr = data
                        st.session_state.scan_count += 1
                        
                        # Show detection notification
                        st.toast("✅ QR Code detected! Processing...", icon="🔍")
                        
                        # Process attendance
                        success, message, student_name, details = process_attendance(data, mode)
                        
                        if success:
                            st.session_state.last_result = {
                                'success': True,
                                'message': message,
                                'student_name': student_name,
                                'details': details
                            }
                            st.balloons()
                        else:
                            st.session_state.last_result = {
                                'success': False,
                                'message': message,
                                'student_name': student_name,
                                'details': details
                            }
                        
                        # Small delay to show result
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.info("⏳ Same QR code detected - waiting for new scan...")
                else:
                    st.warning("No QR code detected. Please ensure the QR code is clearly visible.")
                    
            except Exception as e:
                st.error(f"Camera error: {str(e)}")
            finally:
                st.session_state.processing = False
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Display last result
        if st.session_state.last_result:
            result = st.session_state.last_result
            if result['success']:
                if result['details']['type'] == 'check_in':
                    st.markdown(f"""
                    <div class="success-box" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                                color: white; padding: 20px; border-radius: 15px; 
                                text-align: center; margin: 20px 0;">
                        <h2 style="margin: 0;">✅ CHECK-IN SUCCESSFUL!</h2>
                        <p style="font-size: 1.5rem; margin: 10px 0;">{result['student_name']}</p>
                        <p style="font-size: 1rem; opacity: 0.9;">Time: {result['details']['time'].strftime('%I:%M:%S %p')}</p>
                        <p style="font-size: 0.9rem; margin-top: 10px;">
                            {'📧 Email sent' if result['details']['email_sent'] else '⚠️ Email failed - please inform admin'}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="success-box" style="background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); 
                                color: white; padding: 20px; border-radius: 15px; 
                                text-align: center; margin: 20px 0;">
                        <h2 style="margin: 0;">✅ CHECK-OUT SUCCESSFUL!</h2>
                        <p style="font-size: 1.5rem; margin: 10px 0;">{result['student_name']}</p>
                        <p style="font-size: 1rem; opacity: 0.9;">Duration: {result['details']['duration']}</p>
                        <p style="font-size: 0.9rem; margin-top: 10px;">
                            {'📧 Email sent' if result['details']['email_sent'] else '⚠️ Email failed - please inform admin'}
                        </p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: #fef3c7; padding: 20px; border-radius: 15px; 
                            border-left: 5px solid #f59e0b; margin: 20px 0;">
                    <h3 style="margin: 0; color: #92400e;">⚠️ {result['message']}</h3>
                    {'<p style="margin: 5px 0;"><strong>Student:</strong> ' + result['student_name'] + '</p>' if result['student_name'] else ''}
                </div>
                """, unsafe_allow_html=True)
            
            # Add reset button
            if st.button("🔄 Scan Another QR Code", use_container_width=True):
                st.session_state.last_result = None
                st.session_state.last_processed_qr = None
                st.rerun()
    
    else:  # Manual Entry
        st.markdown('<div class="instruction-card">', unsafe_allow_html=True)
        st.subheader("📝 Manual Code Entry")
        
        qr_data = st.text_input(
            "Enter your QR code:",
            placeholder="Paste or type your student code here...",
            key="manual_input"
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            process_button = st.button("🚀 Process Attendance", type="primary", use_container_width=True)
        
        if process_button and qr_data:
            with st.spinner("Processing..."):
                success, message, student_name, details = process_attendance(qr_data, mode)
                
                if success:
                    if details['type'] == 'check_in':
                        st.success(f"""
                        ✅ **CHECK-IN SUCCESSFUL!**
                        
                        **Student:** {student_name}
                        **Time:** {details['time'].strftime('%I:%M %p')}
                        **Email:** {'Sent' if details['email_sent'] else 'Failed'}
                        """)
                        st.balloons()
                    else:
                        st.success(f"""
                        ✅ **CHECK-OUT SUCCESSFUL!**
                        
                        **Student:** {student_name}
                        **Duration:** {details['duration']}
                        **Email:** {'Sent' if details['email_sent'] else 'Failed'}
                        """)
                        st.balloons()
                else:
                    st.error(message)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Instructions section
    st.markdown("---")
    st.markdown('<div class="instruction-card">', unsafe_allow_html=True)
    st.subheader("📋 How to Use")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **For Camera Scan:**
        1. Position your QR code in front of the camera
        2. Hold steady until detected
        3. System will auto-process
        4. Check your email for confirmation
        
        **For Manual Entry:**
        1. Copy your student code
        2. Paste in the text box
        3. Click "Process Attendance"
        4. Receive instant confirmation
        """)
    
    with col2:
        st.markdown("""
        **Operating Hours:**
        - 🟢 **Check-in:** 7:00 PM - 11:59 PM
        - 🟡 **Check-out:** 1:00 PM - 6:59 PM
        
        **Important Notes:**
        - Each QR code is unique to you
        - Don't share your QR code
        - Keep your student code safe
        - Check email for confirmations
        """)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Footer
    st.markdown("---")
    st.markdown(
        '<p style="text-align: center; font-size: 0.8rem; color: #999;">'
        'Student Attendance System | Need help? Contact your administrator'
        '</p>',
        unsafe_allow_html=True
    )

def main():
    """Main function for student attendance scanner."""
    scanner_page()

if __name__ == "__main__":
    main()