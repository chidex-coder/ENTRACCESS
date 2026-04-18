"""Standalone Student Attendance Scanner App"""
import streamlit as st
from datetime import datetime
import sys
import os
import time
import io
from PIL import Image
import numpy as np

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CHECK_IN_START, CHECK_IN_END, CHECK_OUT_START, CHECK_OUT_END
from database import (
    get_student_by_qr, process_check_in, process_check_out,
    update_email_status, get_connection
)
from email_service import email_service

# Try to import QR code reader (fallback to manual entry if not available)
try:
    from pyzbar.pyzbar import decode
    QR_SCANNER_AVAILABLE = True
except ImportError:
    QR_SCANNER_AVAILABLE = False
    st.warning("QR scanner not available. Using manual entry mode.")

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
    
    .success-box {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        margin: 20px 0;
        animation: successPulse 0.5s ease;
    }
    
    @keyframes successPulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.02); }
        100% { transform: scale(1); }
    }
    
    .warning-box {
        background: #fef3c7;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #f59e0b;
        margin: 20px 0;
    }
    
    .info-box {
        background: #e0f2fe;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #0ea5e9;
        margin: 20px 0;
    }
    
    .qr-upload-container {
        border: 2px dashed #667eea;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        background: #f8f9ff;
    }
    
    .instruction-card {
        background: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin: 15px 0;
    }
</style>
""", unsafe_allow_html=True)

def get_current_mode():
    """Determine current operating mode."""
    now = datetime.now().time()
    
    if CHECK_IN_START <= now <= CHECK_IN_END:
        return "check_in", "✅ CHECK-IN MODE", "#10b981", "You can check in now"
    elif CHECK_OUT_START <= now <= CHECK_OUT_END:
        return "check_out", "✅ CHECK-OUT MODE", "#f59e0b", "You can check out now"
    else:
        next_mode = "Check-in at 7:00 PM" if now < CHECK_IN_START else "Check-in tomorrow at 7:00 PM"
        return "inactive", "⏰ SCANNER INACTIVE", "#6b7280", f"Scanner closed. {next_mode}"

def decode_qr_from_image(image):
    """Decode QR code from uploaded image using pyzbar"""
    if not QR_SCANNER_AVAILABLE:
        return None
    
    try:
        # Convert PIL image to numpy array
        if isinstance(image, Image.Image):
            image = np.array(image)
        
        # Decode QR code
        decoded_objects = decode(image)
        
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
        return None
    except Exception as e:
        st.error(f"Error decoding QR code: {str(e)}")
        return None

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
    <div style="text-align: center; font-size: 1.2rem; font-weight: 600; padding: 10px;">
        🕐 {current_time.strftime('%I:%M:%S %p')} | 📅 {current_time.strftime('%B %d, %Y')}
    </div>
    """, unsafe_allow_html=True)
    
    if mode == "inactive":
        st.warning("⚠️ Scanner is currently closed. Please check back during operating hours.")
        st.info(f"""
        **Operating Hours:**
        - **Check-in:** {CHECK_IN_START.strftime('%I:%M %p')} - {CHECK_IN_END.strftime('%I:%M %p')}
        - **Check-out:** {CHECK_OUT_START.strftime('%I:%M %p')} - {CHECK_OUT_END.strftime('%I:%M %p')}
        
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
    input_method = st.radio(
        "Select Input Method",
        ["📷 Upload QR Code Image", "⌨️ Manual Entry"],
        horizontal=True
    )
    
    qr_data = None
    
    if input_method == "📷 Upload QR Code Image":
        st.markdown('<div class="qr-upload-container">', unsafe_allow_html=True)
        
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 12px; border-radius: 10px; 
                    text-align: center; margin-bottom: 15px;">
            <span style="font-size: 1.1rem;">📸 Upload a photo of your QR code</span>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader(
            "Choose a QR code image",
            type=['png', 'jpg', 'jpeg', 'bmp'],
            help="Upload a clear photo of your QR code"
        )
        
        if uploaded_file and not st.session_state.processing:
            try:
                st.session_state.processing = True
                
                # Read image
                image = Image.open(uploaded_file)
                
                # Display preview
                st.image(image, caption="Uploaded QR Code", use_container_width=True, width=200)
                
                # Decode QR code
                with st.spinner("🔍 Decoding QR code..."):
                    if QR_SCANNER_AVAILABLE:
                        qr_data = decode_qr_from_image(image)
                    else:
                        st.warning("QR scanner not available. Please use manual entry.")
                        qr_data = None
                
                if qr_data:
                    # Check for duplicate
                    if qr_data != st.session_state.last_processed_qr:
                        st.session_state.last_processed_qr = qr_data
                        st.session_state.scan_count += 1
                        
                        # Process attendance
                        success, message, student_name, details = process_attendance(qr_data, mode)
                        
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
                        
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.info("⏳ Same QR code detected - waiting for new scan...")
                else:
                    st.error("No QR code detected in the image. Please try again or use manual entry.")
                    
            except Exception as e:
                st.error(f"Error processing image: {str(e)}")
            finally:
                st.session_state.processing = False
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Display last result
        if st.session_state.last_result:
            result = st.session_state.last_result
            if result['success']:
                if result['details']['type'] == 'check_in':
                    st.markdown(f"""
                    <div class="success-box">
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
                    <div class="success-box" style="background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%);">
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
                <div class="warning-box">
                    <h3 style="margin: 0; color: #92400e;">⚠️ {result['message']}</h3>
                    {f'<p style="margin: 5px 0;"><strong>Student:</strong> {result["student_name"]}</p>' if result['student_name'] else ''}
                </div>
                """, unsafe_allow_html=True)
            
            if st.button("🔄 Scan Another QR Code", use_container_width=True):
                st.session_state.last_result = None
                st.session_state.last_processed_qr = None
                st.rerun()
    
    else:  # Manual Entry
        st.markdown('<div class="instruction-card">', unsafe_allow_html=True)
        st.subheader("📝 Manual Code Entry")
        
        qr_data = st.text_input(
            "Enter your student code:",
            placeholder="Paste or type your student code here...",
            help="You can find your student code on your QR code or in your registration email",
            key="manual_input"
        )
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            process_button = st.button("🚀 Process Attendance", type="primary", use_container_width=True)
        
        if process_button and qr_data:
            with st.spinner("Processing..."):
                success, message, student_name, details = process_attendance(qr_data.upper(), mode)
                
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
        **📷 Using QR Code Upload:**
        1. Take a clear photo of your QR code
        2. Upload the image
        3. System will auto-detect and process
        4. Check your email for confirmation
        
        **⌨️ Using Manual Entry:**
        1. Find your student code
        2. Type or paste it in the box
        3. Click "Process Attendance"
        4. Receive instant confirmation
        """)
    
    with col2:
        st.markdown(f"""
        **🕐 Operating Hours:**
        - 🟢 **Check-in:** {CHECK_IN_START.strftime('%I:%M %p')} - {CHECK_IN_END.strftime('%I:%M %p')}
        - 🟡 **Check-out:** {CHECK_OUT_START.strftime('%I:%M %p')} - {CHECK_OUT_END.strftime('%I:%M %p')}
        
        **⚠️ Important Notes:**
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
