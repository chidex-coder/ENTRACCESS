"""Standalone student registration page."""
import streamlit as st
from datetime import datetime
import sys
import os
import qrcode
from PIL import Image
import io
import base64

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from existing modules
try:
    from database import register_student
    from email_service import email_service
except ImportError as e:
    st.error(f"Import error: {str(e)}. Please ensure all required files exist.")
    st.stop()

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Student Registration",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Hide the default menu and navigation
hide_menu_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stDeployButton {display: none;}
    </style>
"""
st.markdown(hide_menu_style, unsafe_allow_html=True)

# Custom styling for student page
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
        margin-bottom: 1.5rem;
        padding: 0.5rem;
        animation: gradient 8s ease infinite;
    }
    
    @keyframes gradient {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Modern student card */
    .student-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9ff 100%);
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        margin-bottom: 1.5rem;
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    
    /* Success box */
    .success-box {
        background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 5px solid #28a745;
        margin: 1rem 0;
    }
    
    /* Info box */
    .info-box {
        background: linear-gradient(135deg, #d1ecf1 0%, #bee5eb 100%);
        padding: 1.2rem;
        border-radius: 15px;
        border-left: 5px solid #17a2b8;
        margin: 1rem 0;
    }
    
    /* Warning box */
    .warning-box {
        background: linear-gradient(135deg, #fff3cd 0%, #ffeeba 100%);
        padding: 1rem;
        border-radius: 10px;
        border-left: 5px solid #ffc107;
        margin: 1rem 0;
    }
    
    /* Custom button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
    }
    
    /* QR code container */
    .qr-container {
        background: white;
        padding: 1rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

def generate_qr_code(data):
    """Generate QR code from data and return as bytes"""
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=5,
        error_correction=qrcode.constants.ERROR_CORRECT_H
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    # Create QR code image
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to bytes
    img_bytes = io.BytesIO()
    qr_img.save(img_bytes, format='PNG')
    img_bytes = img_bytes.getvalue()
    
    return img_bytes, qr_img

def pil_to_bytes(pil_image):
    """Convert PIL image to bytes"""
    img_bytes = io.BytesIO()
    pil_image.save(img_bytes, format='PNG')
    return img_bytes.getvalue()

def main():
    """Student registration page."""
    st.markdown('<h1 class="main-header">🎓 Student Registration</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; color: #666;">Register to get your attendance QR code</p>', unsafe_allow_html=True)
    
    # Initialize session state
    if 'registration_complete' not in st.session_state:
        st.session_state.registration_complete = False
        st.session_state.registration_data = None
    
    # Registration form
    if not st.session_state.registration_complete:
        with st.container():
            st.markdown('<div class="student-card">', unsafe_allow_html=True)
            
            with st.form("student_registration_form"):
                st.subheader("📝 Your Information")
                
                full_name = st.text_input(
                    "Full Name *",
                    placeholder="Enter your full name",
                    help="As it appears on official documents"
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    email = st.text_input(
                        "Email Address *",
                        placeholder="your@email.com",
                        help="Valid email for QR code delivery"
                    )
                with col2:
                    phone = st.text_input(
                        "Phone Number *",
                        placeholder="+1234567890",
                        help="Include country code"
                    )
                
                # Terms checkbox
                agree = st.checkbox("✅ I agree to receive attendance notifications via email")
                
                submitted = st.form_submit_button(
                    "🚀 Generate My QR Code",
                    type="primary",
                    use_container_width=True
                )
                
                if submitted:
                    if not all([full_name, email, phone]):
                        st.error("⚠️ Please fill in all required fields!")
                    elif "@" not in email or "." not in email:
                        st.error("⚠️ Please enter a valid email address!")
                    elif len(phone) < 10:
                        st.error("⚠️ Please enter a valid phone number!")
                    elif not agree:
                        st.error("⚠️ Please agree to receive email notifications!")
                    else:
                        with st.spinner("🔄 Generating your QR code..."):
                            try:
                                # Create unique student code
                                import hashlib
                                import secrets
                                
                                unique_string = f"{email}{phone}{datetime.now().timestamp()}{secrets.token_hex(4)}"
                                student_code = hashlib.sha256(unique_string.encode()).hexdigest()[:12].upper()
                                
                                # Register student
                                success, result, student_id = register_student(full_name, email, phone, student_code)
                                
                                if not success:
                                    st.error(f"❌ Registration failed: {result}")
                                else:
                                    # Generate QR code as bytes
                                    qr_bytes, qr_img = generate_qr_code(student_code)
                                    
                                    # Try to send email
                                    email_sent = False
                                    try:
                                        email_sent = email_service.send_registration_confirmation(
                                            email, full_name, student_id, qr_bytes
                                        )
                                    except Exception as e:
                                        st.warning(f"Email notification failed: {str(e)}")
                                    
                                    # Store in session state
                                    st.session_state.registration_complete = True
                                    st.session_state.registration_data = {
                                        'student_id': student_id,
                                        'student_code': student_code,
                                        'full_name': full_name,
                                        'email': email,
                                        'phone': phone,
                                        'qr_bytes': qr_bytes,
                                        'qr_img': qr_img,
                                        'email_sent': email_sent
                                    }
                                    st.rerun()
                                    
                            except Exception as e:
                                st.error(f"❌ Registration error: {str(e)}")
            
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Instructions
            st.markdown("""
            <div class="info-box">
                <h4>📋 What happens next?</h4>
                <ol>
                    <li>Fill in your details above</li>
                    <li>Click "Generate My QR Code"</li>
                    <li>Download your QR code (or check your email)</li>
                    <li>Use the QR code for check-in and check-out</li>
                </ol>
            </div>
            """, unsafe_allow_html=True)
    
    # Show success page after registration
    else:
        data = st.session_state.registration_data
        
        st.markdown(f"""
        <div class="success-box">
            <h3>✅ Registration Successful!</h3>
            <p>Welcome <strong>{data['full_name']}</strong>! Your QR code has been generated.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="student-card">', unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="qr-container">', unsafe_allow_html=True)
            # Display QR code from bytes
            st.image(data['qr_bytes'], caption="Your QR Code", use_container_width=True)
            
            # Download button
            st.download_button(
                "📥 Download QR Code",
                data=data['qr_bytes'],
                file_name=f"QR_{data['student_code']}.png",
                mime="image/png",
                use_container_width=True
            )
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            ### 📋 Your Details
            
            | Field | Value |
            |-------|-------|
            | **Student ID** | #{data['student_id']} |
            | **Student Code** | `{data['student_code']}` |
            | **Name** | {data['full_name']} |
            | **Email** | {data['email']} |
            | **Phone** | {data['phone']} |
            
            **Email Status:** {'✅ Sent' if data['email_sent'] else '❌ Failed'}
            """)
            
            if not data['email_sent']:
                st.markdown("""
                <div class="warning-box">
                    ⚠️ Email failed to send. Please download your QR code now!
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Important information - Get times from config
        try:
            from config import CHECK_IN_START, CHECK_IN_END, CHECK_OUT_START, CHECK_OUT_END
            
            check_in_start_str = CHECK_IN_START.strftime('%I:%M %p')
            check_in_end_str = CHECK_IN_END.strftime('%I:%M %p')
            check_out_start_str = CHECK_OUT_START.strftime('%I:%M %p')
            check_out_end_str = CHECK_OUT_END.strftime('%I:%M %p')
        except:
            check_in_start_str = "7:00 PM"
            check_in_end_str = "11:59 PM"
            check_out_start_str = "1:00 PM"
            check_out_end_str = "6:59 PM"
        
        st.markdown(f"""
        <div class="info-box">
            <h4>⚠️ Important Information</h4>
            <ul>
                <li><strong>Check-in:</strong> {check_in_start_str} - {check_in_end_str}</li>
                <li><strong>Check-out:</strong> {check_out_start_str} - {check_out_end_str}</li>
                <li>Present your QR code at the scanner</li>
                <li>Each QR code is unique - do not share</li>
                <li>Save this QR code on your phone for easy access</li>
                <li>You'll receive email confirmations for each attendance</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Register another button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📝 Register Another Student", use_container_width=True):
                st.session_state.registration_complete = False
                st.session_state.registration_data = None
                st.rerun()
        
        # Quick links
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                '<p style="text-align: center;">'
                '<a href="http://localhost:8501" target="_blank">📱 Go to Scanner</a>'
                '</p>',
                unsafe_allow_html=True
            )
        with col2:
            st.markdown(
                '<p style="text-align: center;">'
                '<a href="http://localhost:8502" target="_blank">🔒 Admin Portal</a>'
                '</p>',
                unsafe_allow_html=True
            )

if __name__ == "__main__":
    main()