"""Main admin application."""
import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime, time, timedelta
import cv2
import numpy as np
import pandas as pd
import plotly.express as px
import time
import os

from config import CHECK_IN_START, CHECK_IN_END, CHECK_OUT_START, CHECK_OUT_END
from database import (
    init_database, register_student, get_student_by_qr, 
    process_check_in, process_check_out, update_email_status, 
    get_attendance_records, get_statistics, delete_student,
    hard_delete_student, delete_attendance_record, clear_all_data,
    reset_database_completely, get_all_students, get_student_attendance_history,
    get_student_by_id, DB_PATH, get_connection
)
from qr_generator import qr_generator
from email_service import email_service

# Initialize database on startup
init_database()

# Page configuration
st.set_page_config(
    page_title="Admin Portal - Student Attendance System",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

def get_current_mode():
    """Determine current operating mode."""
    now = datetime.now().time()
    if CHECK_IN_START <= now <= CHECK_IN_END:
        return "check_in", "🌙 CHECK-IN MODE", "#28a745"
    elif CHECK_OUT_START <= now <= CHECK_OUT_END:
        return "check_out", "☀️ CHECK-OUT MODE", "#fd7e14"
    else:
        return "inactive", "⛔ SCANNER INACTIVE", "#dc3545"

def home_page():
    """Admin home page."""
    st.markdown('<h1 class="main-header">🔒 Admin Portal</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Student Attendance Management System</p>', unsafe_allow_html=True)
    
    stats = get_statistics()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total Students", stats['total_students'])
    with col2:
        st.metric("Today's Check-ins", stats['today_check_ins'])
    with col3:
        st.metric("Today's Check-outs", stats['today_check_outs'])
    with col4:
        st.metric("Avg Duration (hrs)", f"{stats['avg_duration']:.1f}")
    with col5:
        st.metric("Duplicate Attempts", stats['recent_duplicates'])
    
    st.markdown("---")
    
    

def scanner_page():
    """Admin scanner page with auto-scan capability."""
    st.title("📱 Attendance Scanner")
    
    mode, mode_text, mode_color = get_current_mode()
    
    st.markdown(f"""
    <div style="background: {mode_color}; color: white; padding: 20px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h2 style="margin: 0;">{mode_text}</h2>
    </div>
    """, unsafe_allow_html=True)
    
    if mode == "inactive":
        st.warning("Scanner is currently closed. Operating hours: 1:00 PM - 11:59 PM")
        return
    
    # Initialize session state for tracking processed QR codes
    if 'last_processed_qr' not in st.session_state:
        st.session_state.last_processed_qr = None
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    if 'scan_count' not in st.session_state:
        st.session_state.scan_count = 0
    
    input_method = st.radio("Input Method:", ["📷 Camera Scan", "⌨️ Manual Entry"], horizontal=True)
    
    qr_data = None
    
    if input_method == "📷 Camera Scan":
        # Auto-scan mode indicator
        st.markdown("""
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    color: white; padding: 10px; border-radius: 10px; 
                    text-align: center; margin-bottom: 15px;">
            <span style="font-size: 1.1rem;">⚡ Auto-scan mode active - QR codes processed instantly!</span>
        </div>
        """, unsafe_allow_html=True)
        
        # Show scan counter
        if st.session_state.scan_count > 0:
            st.markdown(f"""
            <div style="text-align: right; margin-bottom: 10px;">
                <span style="background: #e0f2fe; padding: 5px 10px; border-radius: 20px; font-size: 0.9rem;">
                    📊 Today's scans: {st.session_state.scan_count}
                </span>
            </div>
            """, unsafe_allow_html=True)
        
        # Camera input
        camera_image = st.camera_input("Capture QR Code", key=f"camera_{st.session_state.scan_count}")
        
        if camera_image and not st.session_state.processing:
            try:
                st.session_state.processing = True
                
                bytes_data = camera_image.getvalue()
                nparr = np.frombuffer(bytes_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(img)
                
                if data:
                    # Check if this QR code was just processed (prevent duplicates in same session)
                    if data != st.session_state.last_processed_qr:
                        st.session_state.last_processed_qr = data
                        st.session_state.scan_count += 1
                        
                        # Show instant detection notification
                        st.toast("✅ QR Code detected! Processing...", icon="🔍")
                        
                        # Auto-process the attendance
                        process_attendance_auto(data, mode)
                    else:
                        st.info("⏳ Same QR code detected - waiting for new scan...")
                else:
                    st.warning("No QR code detected in the image. Please try again.")
                    
            except Exception as e:
                st.error(f"Camera error: {str(e)}")
            finally:
                st.session_state.processing = False
                
    else:  # Manual Entry
        qr_data = st.text_input("Enter QR Code Data", placeholder="Paste QR code string here...", key="manual_input")
        
        # Auto-clear button for manual mode
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🔄 Clear", use_container_width=True):
                st.session_state.last_processed_qr = None
                st.rerun()
        
        if qr_data and st.button("🚀 Process Attendance", type="primary", use_container_width=True):
            with st.spinner("Processing..."):
                process_attendance_manual(qr_data, mode)

def process_attendance_auto(qr_data, mode):
    """Auto-process attendance when QR code is detected."""
    with st.spinner("⚡ Auto-processing attendance..."):
        student = get_student_by_qr(qr_data)
        
        if not student:
            st.error("❌ Invalid QR Code! Student not found.")
            return
        
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
                
                st.balloons()
                # Show success in a prominent box
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                            color: white; padding: 20px; border-radius: 15px; 
                            text-align: center; margin: 10px 0; animation: slideIn 0.5s;">
                    <h2 style="margin: 0;">✅ CHECK-IN SUCCESSFUL!</h2>
                    <p style="font-size: 1.2rem; margin: 10px 0;">{student_name}</p>
                    <p style="font-size: 1rem; opacity: 0.9;">{result['timestamp'].strftime('%I:%M:%S %p')}</p>
                </div>
                
                <style>
                @keyframes slideIn {{
                    from {{ transform: translateY(-20px); opacity: 0; }}
                    to {{ transform: translateY(0); opacity: 1; }}
                }}
                </style>
                """, unsafe_allow_html=True)
            
            elif result['status'] == 'duplicate':
                st.warning(f"""
                <div style="background: #fef3c7; padding: 15px; border-radius: 10px; border-left: 5px solid #f59e0b;">
                    <h3 style="margin: 0; color: #92400e;">⚠️ Already Signed In</h3>
                    <p style="margin: 5px 0;"><strong>{student_name}</strong> - {result['details']}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(f"❌ {result['message']}")
        
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
                
                st.balloons()
                # Show success in a prominent box
                st.markdown(f"""
                <div style="background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); 
                            color: white; padding: 20px; border-radius: 15px; 
                            text-align: center; margin: 10px 0; animation: slideIn 0.5s;">
                    <h2 style="margin: 0;">✅ CHECK-OUT SUCCESSFUL!</h2>
                    <p style="font-size: 1.2rem; margin: 10px 0;">{student_name}</p>
                    <p style="font-size: 1rem; opacity: 0.9;">Duration: {str(result['duration']).split('.')[0]}</p>
                </div>
                """, unsafe_allow_html=True)
            
            elif result['status'] == 'duplicate':
                st.warning(f"""
                <div style="background: #fef3c7; padding: 15px; border-radius: 10px; border-left: 5px solid #f59e0b;">
                    <h3 style="margin: 0; color: #92400e;">⚠️ Already Signed Out</h3>
                    <p style="margin: 5px 0;"><strong>{student_name}</strong> - {result['details']}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(f"❌ {result['message']}")
    
    # Small delay to ensure user sees the result
    time.sleep(2)
    st.rerun()

def process_attendance_manual(qr_data, mode):
    """Process attendance for manual entry mode."""
    student = get_student_by_qr(qr_data)
    
    if not student:
        st.error("❌ Invalid QR Code!")
        return
    
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
            
            st.balloons()
            st.success(f"""
            ✅ **CHECK-IN SUCCESSFUL**
            
            **Student:** {student_name}  
            **Time:** {result['timestamp'].strftime('%I:%M %p')}
            """)
        
        elif result['status'] == 'duplicate':
            st.warning(f"""
            ⚠️ **ALREADY SIGNED IN**
            
            **Student:** {student_name}  
            **Previous:** {result['details']}
            """)
        else:
            st.error(result['message'])
    
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
            
            st.balloons()
            st.success(f"""
            ✅ **CHECK-OUT SUCCESSFUL**
            
            **Student:** {student_name}  
            **Duration:** {str(result['duration']).split('.')[0]}
            """)
        
        elif result['status'] == 'duplicate':
            st.warning(f"""
            ⚠️ **ALREADY SIGNED OUT**
            
            **Student:** {student_name}  
            **Details:** {result['details']}
            """)
        else:
            st.error(f"{result['message']}\n\n{result['details']}")

# Add this helper function to reset scanner
def reset_scanner():
    """Reset the scanner session state."""
    st.session_state.last_processed_qr = None
    st.session_state.processing = False
    st.rerun()

def analytics_page():
    """Admin analytics page with comprehensive data analysis and visualization."""
    st.title("📊 Analytics Dashboard")
    
    # Initialize session state for filters
    if 'analytics_filters' not in st.session_state:
        st.session_state.analytics_filters = {}
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    
    # Sidebar with advanced filters
    with st.sidebar:
        st.markdown("## 🔍 Advanced Filters")
        
        # Quick date range presets
        st.markdown("### 📅 Date Range")
        date_preset = st.selectbox(
            "Quick Select",
            ["Custom Range", "Today", "Last 7 Days", "Last 30 Days", "This Month", "Last Month", "This Year"],
            index=3
        )
        
        today = datetime.now().date()
        if date_preset == "Today":
            date_from = today
            date_to = today
        elif date_preset == "Last 7 Days":
            date_from = today - timedelta(days=7)
            date_to = today
        elif date_preset == "Last 30 Days":
            date_from = today - timedelta(days=30)
            date_to = today
        elif date_preset == "This Month":
            date_from = today.replace(day=1)
            date_to = today
        elif date_preset == "Last Month":
            last_month = today.replace(day=1) - timedelta(days=1)
            date_from = last_month.replace(day=1)
            date_to = last_month
        elif date_preset == "This Year":
            date_from = today.replace(month=1, day=1)
            date_to = today
        else:
            date_from = today - timedelta(days=30)
            date_to = today
        
        col1, col2 = st.columns(2)
        with col1:
            date_from = st.date_input("From", date_from, key="date_from")
        with col2:
            date_to = st.date_input("To", date_to, key="date_to")
        
        st.markdown("### 👤 Student Information")
        name_filter = st.text_input("Full Name", placeholder="Enter name...")
        email_filter = st.text_input("Email", placeholder="Enter email...")
        phone_filter = st.text_input("Phone", placeholder="Enter phone...")
        
        st.markdown("### 📍 Attendance Status")
        status_filter = st.multiselect(
            "Status",
            ["Checked In", "Checked Out", "Active Sessions"],
            default=["Checked In", "Checked Out"]
        )
        
        st.markdown("### ⏱️ Session Duration")
        duration_range = st.slider(
            "Duration (hours)",
            min_value=0.0,
            max_value=24.0,
            value=(0.0, 24.0),
            step=0.5
        )
        
        st.markdown("### 📧 Email Status")
        email_status = st.multiselect(
            "Email Confirmation",
            ["Check-in Sent", "Check-in Not Sent", "Check-out Sent", "Check-out Not Sent"],
            default=[]
        )
        
        # Filter actions
        col1, col2 = st.columns(2)
        with col1:
            apply_filters = st.button("🎯 Apply Filters", use_container_width=True, type="primary")
        with col2:
            reset_filters = st.button("🔄 Reset", use_container_width=True)
        
        if reset_filters:
            st.session_state.analytics_filters = {}
            st.rerun()
    
    # Build filters dictionary
    filters = {}
    if apply_filters or st.session_state.analytics_filters:
        filters['date_from'] = date_from.strftime('%Y-%m-%d')
        filters['date_to'] = date_to.strftime('%Y-%m-%d')
        
        if name_filter:
            filters['full_name'] = name_filter
        if email_filter:
            filters['email'] = email_filter
        if phone_filter:
            filters['phone'] = phone_filter
        
        if status_filter:
            filters['status'] = status_filter
        
        filters['duration_min'] = duration_range[0]
        filters['duration_max'] = duration_range[1]
        
        if email_status:
            filters['email_status'] = email_status
        
        st.session_state.analytics_filters = filters
    
    # Load data with caching
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def load_attendance_data(filter_dict):
        """Load and cache attendance data."""
        try:
            records = get_attendance_records(filter_dict if filter_dict else None)
            if records:
                df = pd.DataFrame(records)
                # Convert date columns
                date_columns = ['registration_date', 'check_in', 'check_out', 'attendance_date']
                for col in date_columns:
                    if col in df.columns:
                        df[col] = pd.to_datetime(df[col], errors='coerce')
                return df
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return pd.DataFrame()
    
    # Load data
    with st.spinner("📊 Loading analytics data..."):
        df = load_attendance_data(st.session_state.analytics_filters if st.session_state.analytics_filters else None)
    
    # Main content area
    if not df.empty:
        # Calculate metrics with safe column access
        total_sessions = len(df)
        active_sessions = len(df[df['check_out'].isna()]) if 'check_out' in df.columns else 0
        completed_sessions = len(df[df['check_out'].notna()]) if 'check_out' in df.columns else 0
        
        # Calculate durations for completed sessions
        if 'check_in' in df.columns and 'check_out' in df.columns:
            df['duration_hours'] = (df['check_out'] - df['check_in']).dt.total_seconds() / 3600
            valid_durations = df[df['duration_hours'].notna()]
            avg_duration = valid_durations['duration_hours'].mean() if not valid_durations.empty else 0
            total_hours = valid_durations['duration_hours'].sum() if not valid_durations.empty else 0
        else:
            avg_duration = 0
            total_hours = 0
        
        # Email metrics - safely check if columns exist
        check_in_emails_sent = df['check_in_email_sent'].sum() if 'check_in_email_sent' in df.columns else 0
        check_out_emails_sent = df['check_out_email_sent'].sum() if 'check_out_email_sent' in df.columns else 0
        
        # KPI Cards
        st.markdown("## 📈 Key Performance Indicators")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Sessions",
                f"{total_sessions:,}",
                delta=f"{active_sessions} active",
                help="Total number of attendance sessions"
            )
        
        with col2:
            completion_rate = (completed_sessions/total_sessions*100) if total_sessions > 0 else 0
            st.metric(
                "Completed Sessions",
                f"{completed_sessions:,}",
                delta=f"{completion_rate:.1f}%",
                help="Sessions with check-out completed"
            )
        
        with col3:
            st.metric(
                "Avg Duration",
                f"{avg_duration:.1f} hrs" if avg_duration > 0 else "N/A",
                delta=f"{total_hours:.0f} total hrs" if total_hours > 0 else "0 hrs",
                help="Average session duration"
            )
        
        with col4:
            total_emails = check_in_emails_sent + check_out_emails_sent
            total_possible_emails = (completed_sessions * 2) + (active_sessions * 1) if total_sessions > 0 else 0
            email_rate = (total_emails / total_possible_emails * 100) if total_possible_emails > 0 else 0
            st.metric(
                "Email Success Rate",
                f"{email_rate:.1f}%",
                delta=f"{total_emails} sent",
                help="Percentage of confirmation emails sent successfully"
            )
        
        st.markdown("---")
        
        # Tabs for different analytics views
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📋 Data Table", 
            "📈 Trends", 
            "👥 Student Analytics",
            "⏱️ Duration Analysis",
            "📧 Email Analytics"
        ])
        
        with tab1:
            st.subheader("📋 Attendance Records")
            
            # Prepare display dataframe
            display_df = df.copy()
            
            # Format datetime columns
            for col in ['registration_date', 'check_in', 'check_out']:
                if col in display_df.columns:
                    display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%Y-%m-%d %H:%M').fillna('—')
            
            # Add duration column
            if 'duration_hours' in df.columns:
                display_df['Duration'] = df['duration_hours'].apply(
                    lambda x: f"{x:.2f} hrs" if pd.notna(x) and x > 0 else 'Active'
                )
            
            # Email status icons
            if 'check_in_email_sent' in display_df.columns:
                display_df['Check-in Email'] = display_df['check_in_email_sent'].map({1: '✅', 0: '❌'}).fillna('—')
            if 'check_out_email_sent' in display_df.columns:
                display_df['Check-out Email'] = display_df['check_out_email_sent'].map({1: '✅', 0: '❌'}).fillna('—')
            
            # Select columns to display (only those that exist)
            available_cols = ['full_name', 'email', 'phone', 'attendance_date', 'check_in', 'check_out', 
                             'Duration', 'Check-in Email', 'Check-out Email']
            display_cols = [c for c in available_cols if c in display_df.columns]
            
            # Add search functionality
            search_term = st.text_input("🔍 Search in table", placeholder="Enter name, email, or phone...")
            if search_term and display_cols:
                mask = display_df[display_cols].astype(str).apply(
                    lambda x: x.str.contains(search_term, case=False, na=False)
                ).any(axis=1)
                filtered_display_df = display_df[mask]
                st.write(f"Found {len(filtered_display_df)} records")
            else:
                filtered_display_df = display_df
            
            # Display dataframe with styling
            if not filtered_display_df.empty and display_cols:
                st.dataframe(
                    filtered_display_df[display_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "check_in": "Check-in Time",
                        "check_out": "Check-out Time",
                        "attendance_date": "Date"
                    }
                )
            else:
                st.info("No records to display")
            
            # Export options
            col1, col2, col3 = st.columns([1, 1, 2])
            with col1:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Export CSV",
                    csv,
                    f"attendance_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            with col2:
                if st.button("📋 Copy to Clipboard", use_container_width=True):
                    df.to_clipboard(index=False)
                    st.success("Copied to clipboard!")
        
        with tab2:
            st.subheader("📈 Attendance Trends")
            
            if 'attendance_date' in df.columns and 'check_in' in df.columns:
                # Daily attendance trend
                daily_attendance = df.groupby(df['attendance_date'].dt.date).size().reset_index(name='count')
                daily_attendance.columns = ['Date', 'Sessions']
                
                fig_daily = px.line(
                    daily_attendance, 
                    x='Date', 
                    y='Sessions',
                    title='Daily Attendance Trend',
                    markers=True
                )
                fig_daily.update_layout(
                    xaxis_title="Date",
                    yaxis_title="Number of Sessions",
                    hovermode='x unified'
                )
                st.plotly_chart(fig_daily, use_container_width=True)
                
                # Hourly distribution
                df['hour'] = df['check_in'].dt.hour
                hourly_dist = df[df['hour'].notna()].groupby('hour').size().reset_index(name='count')
                
                if not hourly_dist.empty:
                    fig_hourly = px.bar(
                        hourly_dist,
                        x='hour',
                        y='count',
                        title='Attendance by Hour of Day',
                        labels={'hour': 'Hour', 'count': 'Number of Sessions'}
                    )
                    fig_hourly.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=1))
                    st.plotly_chart(fig_hourly, use_container_width=True)
                
                # Weekday distribution
                df['weekday'] = df['check_in'].dt.day_name()
                weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                weekday_dist = df[df['weekday'].notna()].groupby('weekday').size().reindex(weekday_order).reset_index(name='count')
                weekday_dist.columns = ['Weekday', 'Sessions']
                
                if not weekday_dist.empty:
                    fig_weekday = px.bar(
                        weekday_dist,
                        x='Weekday',
                        y='Sessions',
                        title='Attendance by Day of Week',
                        color='Sessions',
                        color_continuous_scale='Viridis'
                    )
                    st.plotly_chart(fig_weekday, use_container_width=True)
            else:
                st.info("Insufficient data for trend analysis")
        
        with tab3:
            st.subheader("👥 Student Analytics")
            
            if 'full_name' in df.columns:
                # Fix: Proper aggregation without column name conflicts
                student_stats = df.groupby('full_name').agg(
                    total_sessions=('full_name', 'count'),
                    total_hours=('duration_hours', 'sum') if 'duration_hours' in df.columns else ('full_name', 'count')
                ).round(2).reset_index()
                
                # Rename columns for display
                student_stats.columns = ['Student Name', 'Total Sessions', 'Total Hours']
                top_students = student_stats.sort_values('Total Sessions', ascending=False).head(10)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if not top_students.empty:
                        fig_top = px.bar(
                            top_students,
                            x='Student Name',
                            y='Total Sessions',
                            title='Top 10 Students by Attendance',
                            color='Total Sessions',
                            color_continuous_scale='Blues'
                        )
                        fig_top.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig_top, use_container_width=True)
                
                with col2:
                    if 'Total Hours' in top_students.columns and top_students['Total Hours'].sum() > 0:
                        fig_hours = px.bar(
                            top_students,
                            x='Student Name',
                            y='Total Hours',
                            title='Top 10 Students by Total Hours',
                            color='Total Hours',
                            color_continuous_scale='Greens'
                        )
                        fig_hours.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig_hours, use_container_width=True)
                
                # Student retention/returning rate
                student_visits = df.groupby('full_name').size().reset_index(name='visits')
                visit_distribution = student_visits['visits'].value_counts().sort_index().reset_index()
                visit_distribution.columns = ['Number of Visits', 'Student Count']
                
                if not visit_distribution.empty:
                    fig_visits = px.bar(
                        visit_distribution,
                        x='Number of Visits',
                        y='Student Count',
                        title='Student Visit Frequency Distribution',
                        text='Student Count'
                    )
                    st.plotly_chart(fig_visits, use_container_width=True)
            else:
                st.info("No student data available")
        
        with tab4:
            st.subheader("⏱️ Duration Analysis")
            
            if 'duration_hours' in df.columns and len(df[df['duration_hours'].notna()]) > 0:
                valid_durations = df[df['duration_hours'].notna()]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Duration histogram
                    fig_duration = px.histogram(
                        valid_durations,
                        x='duration_hours',
                        nbins=30,
                        title='Session Duration Distribution',
                        labels={'duration_hours': 'Duration (hours)', 'count': 'Number of Sessions'},
                        marginal='box'
                    )
                    st.plotly_chart(fig_duration, use_container_width=True)
                
                with col2:
                    # Duration by student (top 10)
                    if 'full_name' in valid_durations.columns:
                        student_avg_duration = valid_durations.groupby('full_name')['duration_hours'].mean().round(2).sort_values(ascending=False).head(10).reset_index()
                        student_avg_duration.columns = ['Student', 'Avg Duration (hrs)']
                        
                        if not student_avg_duration.empty:
                            fig_avg_duration = px.bar(
                                student_avg_duration,
                                x='Student',
                                y='Avg Duration (hrs)',
                                title='Top 10 Average Session Duration by Student',
                                color='Avg Duration (hrs)',
                                color_continuous_scale='Oranges'
                            )
                            fig_avg_duration.update_layout(xaxis_tickangle=-45)
                            st.plotly_chart(fig_avg_duration, use_container_width=True)
                
                # Duration statistics
                st.markdown("### 📊 Duration Statistics")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Mean Duration", f"{valid_durations['duration_hours'].mean():.2f} hrs")
                with col2:
                    st.metric("Median Duration", f"{valid_durations['duration_hours'].median():.2f} hrs")
                with col3:
                    st.metric("Min Duration", f"{valid_durations['duration_hours'].min():.2f} hrs")
                with col4:
                    st.metric("Max Duration", f"{valid_durations['duration_hours'].max():.2f} hrs")
                
                # Duration by weekday
                if 'weekday' in valid_durations.columns:
                    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                    duration_by_weekday = valid_durations.groupby('weekday')['duration_hours'].mean().reindex(weekday_order).reset_index()
                    duration_by_weekday.columns = ['Weekday', 'Avg Duration']
                    
                    if not duration_by_weekday.empty:
                        fig_duration_weekday = px.line(
                            duration_by_weekday,
                            x='Weekday',
                            y='Avg Duration',
                            title='Average Session Duration by Day of Week',
                            markers=True
                        )
                        st.plotly_chart(fig_duration_weekday, use_container_width=True)
            else:
                st.info("No completed sessions available for duration analysis")
        
        with tab5:
            st.subheader("📧 Email Analytics")
            
            # Email success rates
            col1, col2 = st.columns(2)
            
            with col1:
                # Check-in email success
                if 'check_in_email_sent' in df.columns:
                    check_in_success = df['check_in_email_sent'].value_counts().reset_index()
                    if not check_in_success.empty:
                        check_in_success.columns = ['Status', 'Count']
                        check_in_success['Status'] = check_in_success['Status'].map({1: 'Sent', 0: 'Failed'})
                        
                        fig_checkin = px.pie(
                            check_in_success,
                            values='Count',
                            names='Status',
                            title='Check-in Email Status',
                            color='Status',
                            color_discrete_map={'Sent': '#10b981', 'Failed': '#ef4444'}
                        )
                        st.plotly_chart(fig_checkin, use_container_width=True)
            
            with col2:
                # Check-out email success
                if 'check_out_email_sent' in df.columns:
                    check_out_success = df['check_out_email_sent'].value_counts().reset_index()
                    if not check_out_success.empty:
                        check_out_success.columns = ['Status', 'Count']
                        check_out_success['Status'] = check_out_success['Status'].map({1: 'Sent', 0: 'Failed'})
                        
                        fig_checkout = px.pie(
                            check_out_success,
                            values='Count',
                            names='Status',
                            title='Check-out Email Status',
                            color='Status',
                            color_discrete_map={'Sent': '#10b981', 'Failed': '#ef4444'}
                        )
                        st.plotly_chart(fig_checkout, use_container_width=True)
            
            # Email timeline
            st.markdown("### 📧 Email Sending Timeline")
            
            # Create email timeline data
            email_timeline = []
            if 'check_in' in df.columns and 'check_in_email_sent' in df.columns:
                checkin_emails = df[df['check_in_email_sent'] == 1][['check_in']].copy()
                if not checkin_emails.empty:
                    checkin_emails['type'] = 'Check-in'
                    checkin_emails.columns = ['timestamp', 'type']
                    email_timeline.append(checkin_emails)
            
            if 'check_out' in df.columns and 'check_out_email_sent' in df.columns:
                checkout_emails = df[df['check_out_email_sent'] == 1][['check_out']].copy()
                if not checkout_emails.empty:
                    checkout_emails['type'] = 'Check-out'
                    checkout_emails.columns = ['timestamp', 'type']
                    email_timeline.append(checkout_emails)
            
            if email_timeline:
                email_df = pd.concat(email_timeline, ignore_index=True)
                email_df['date'] = email_df['timestamp'].dt.date
                email_trend = email_df.groupby(['date', 'type']).size().reset_index(name='count')
                
                fig_email = px.bar(
                    email_trend,
                    x='date',
                    y='count',
                    color='type',
                    title='Daily Email Sending Activity',
                    barmode='group',
                    color_discrete_map={'Check-in': '#3b82f6', 'Check-out': '#8b5cf6'}
                )
                st.plotly_chart(fig_email, use_container_width=True)
            
            # Failed emails details
            st.markdown("### ❌ Failed Emails")
            failed_conditions = []
            if 'check_in_email_sent' in df.columns:
                failed_conditions.append(df['check_in_email_sent'] == 0)
            if 'check_out_email_sent' in df.columns:
                failed_conditions.append(df['check_out_email_sent'] == 0)
            
            if failed_conditions:
                failed_emails = df[pd.concat(failed_conditions, axis=1).any(axis=1)] if len(failed_conditions) > 1 else df[failed_conditions[0]]
                
                if not failed_emails.empty:
                    display_failed = failed_emails[['full_name', 'email', 'attendance_date']].copy() if all(col in failed_emails.columns for col in ['full_name', 'email', 'attendance_date']) else failed_emails
                    
                    if 'check_in_email_sent' in failed_emails.columns:
                        display_failed['Check-in Status'] = failed_emails['check_in_email_sent'].map({1: '✅', 0: '❌'})
                    if 'check_out_email_sent' in failed_emails.columns:
                        display_failed['Check-out Status'] = failed_emails['check_out_email_sent'].map({1: '✅', 0: '❌'})
                    
                    cols_to_show = ['full_name', 'email', 'attendance_date']
                    if 'Check-in Status' in display_failed.columns:
                        cols_to_show.append('Check-in Status')
                    if 'Check-out Status' in display_failed.columns:
                        cols_to_show.append('Check-out Status')
                    
                    st.dataframe(
                        display_failed[cols_to_show],
                        use_container_width=True,
                        hide_index=True
                    )
                else:
                    st.success("✅ No failed emails in selected period!")
            else:
                st.info("No email data available")
        
        # Summary statistics at the bottom
        with st.expander("📊 Detailed Statistics Summary"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📈 Overall Statistics")
                unique_students = df['full_name'].nunique() if 'full_name' in df.columns else 0

                if unique_students > 0:
                    avg_sessions = len(df) / unique_students
                    avg_sessions_str = f"{avg_sessions:.1f}"
                else:
                    avg_sessions_str = "0"

                st.markdown(f"""
                - **Total Unique Students:** {unique_students}
                - **Total Sessions:** {len(df)}
                - **Average Sessions per Student:** {avg_sessions_str}
                """)
                
                if 'attendance_date' in df.columns and not df.empty:
                    peak_day = df.groupby(df['attendance_date'].dt.date).size().idxmax()
                    st.markdown(f"- **Peak Attendance Day:** {peak_day}")
                
                if 'hour' in df.columns and not df['hour'].mode().empty:
                    st.markdown(f"- **Peak Hour:** {int(df['hour'].mode()[0])}:00")
            
            with col2:
                st.markdown("### 📧 Email Statistics")
                if 'check_in_email_sent' in df.columns and 'check_in' in df.columns:
                    checkin_success_rate = (df['check_in_email_sent'].sum() / len(df[df['check_in'].notna()]) * 100) if len(df[df['check_in'].notna()]) > 0 else 0
                    st.markdown(f"- **Check-in Email Success Rate:** {checkin_success_rate:.1f}%")
                
                if 'check_out_email_sent' in df.columns and 'check_out' in df.columns:
                    checkout_success_rate = (df['check_out_email_sent'].sum() / len(df[df['check_out'].notna()]) * 100) if len(df[df['check_out'].notna()]) > 0 else 0
                    st.markdown(f"- **Check-out Email Success Rate:** {checkout_success_rate:.1f}%")
                
                st.markdown(f"- **Total Emails Sent:** {check_in_emails_sent + check_out_emails_sent}")
    
    else:
        # Empty state with helpful message
        st.info("📭 No attendance records found for the selected filters.")
        
        # Show sample of what filters to try
        with st.expander("💡 Tips for getting data"):
            st.markdown("""
            - Try expanding your date range
            - Clear any text filters you've applied
            - Check if attendance has been recorded for the selected period
            - Make sure the scanner has been used during this time
            """)
        
        # Quick actions
        col1, col2, col3 = st.columns(3)
        with col2:
            if st.button("📊 View All Records", use_container_width=True):
                st.session_state.analytics_filters = {}
                st.rerun()

def database_management_page():
    """Database management page."""
    st.title("⚙️ Database Management")
    
    st.warning("⚠️ **Warning:** Actions on this page can permanently delete data.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 View All Students", "🗑️ Delete Individual", "💣 Bulk Operations", "📊 Database Stats"])
    
    with tab1:
        st.subheader("All Registered Students")
        
        show_inactive = st.checkbox("Show deleted (inactive) students", value=False)
        students = get_all_students(active_only=not show_inactive)
        
        if students:
            df = pd.DataFrame(students)
            
            if 'registration_date' in df.columns:
                df['registration_date'] = pd.to_datetime(df['registration_date'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M')
            
            if 'is_active' in df.columns:
                df['status'] = df['is_active'].map({1: '✅ Active', 0: '❌ Deleted'})
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export Students CSV", csv, f"students_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        else:
            st.info("No students found.")
    
    with tab2:
        st.subheader("Delete Individual Records")
        
        delete_option = st.radio("Select what to delete:", 
                                ["Delete Student", "Delete Attendance Record", "View & Delete Student History"])
        
        if delete_option == "Delete Student":
            student_id = st.number_input("Enter Student ID to delete:", min_value=1, step=1)
            
            if student_id:
                student = get_student_by_id(student_id)
                if student:
                    st.write(f"**Student:** {student['full_name']} ({student['email']})")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Soft Delete", type="secondary"):
                            if delete_student(student_id):
                                st.success(f"✅ Student {student_id} marked as deleted")
                                st.rerun()
                            else:
                                st.error("Failed to delete")
                    
                    with col2:
                        confirm = st.checkbox("Confirm permanent deletion")
                        if confirm and st.button("💣 Hard Delete", type="primary"):
                            if hard_delete_student(student_id):
                                st.success(f"✅ Student {student_id} permanently deleted")
                                st.rerun()
                            else:
                                st.error("Failed to delete")
                else:
                    st.error("Student not found")
        
        elif delete_option == "Delete Attendance Record":
            attendance_id = st.number_input("Enter Attendance ID to delete:", min_value=1, step=1)
            
            if attendance_id:
                if st.button("🗑️ Delete", type="primary"):
                    if delete_attendance_record(attendance_id):
                        st.success(f"✅ Attendance record {attendance_id} deleted")
                        st.rerun()
                    else:
                        st.error("Failed to delete")
        
        elif delete_option == "View & Delete Student History":
            student_id = st.number_input("Enter Student ID:", min_value=1, step=1)
            
            if student_id:
                history = get_student_attendance_history(student_id)
                if history:
                    st.write(f"**Found {len(history)} attendance records**")
                    df = pd.DataFrame(history)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    confirm_text = st.text_input("Type 'DELETE' to delete all history:")
                    if st.button("🗑️ Delete All History", type="primary"):
                        if confirm_text == "DELETE":
                            with get_connection() as conn:
                                cursor = conn.cursor()
                                cursor.execute('DELETE FROM attendance WHERE student_id = ?', (student_id,))
                                conn.commit()
                            st.success("All history deleted")
                            st.rerun()
                else:
                    st.info("No attendance history found")
    
    with tab3:
        st.subheader("Bulk Operations")
        st.error("⚠️ **DANGER ZONE** - These actions cannot be undone!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Clear All Data (Keep Structure)**")
            confirm_clear = st.text_input("Type 'CLEAR ALL':")
            if st.button("💣 Clear All Data", type="primary"):
                if confirm_clear == "CLEAR ALL":
                    if clear_all_data(confirm=True):
                        st.success("✅ All data cleared!")
                        st.rerun()
        
        with col2:
            st.markdown("**Complete Database Reset**")
            confirm_reset = st.text_input("Type 'RESET DB':")
            if st.button("🔥 Reset Database", type="primary"):
                if confirm_reset == "RESET DB":
                    if reset_database_completely():
                        st.success("✅ Database reset!")
                        st.rerun()
        
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        st.info(f"**Database file:** `{DB_PATH}`\n\n**Size:** {db_size / 1024:.2f} KB")
    
    with tab4:
        st.subheader("Database Statistics")
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM students')
            total_students = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM attendance')
            total_attendance = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM scan_log')
            total_logs = cursor.fetchone()[0]
        
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Students", total_students)
        with col2:
            st.metric("Attendance Records", total_attendance)
        with col3:
            st.metric("Scan Logs", total_logs)
        with col4:
            st.metric("DB Size (KB)", f"{db_size / 1024:.2f}")

def main():
    """Main admin application."""
    with st.sidebar:
        st.markdown("## 🔒 Admin Portal")
        
        selected = option_menu(
            menu_title="Navigation",
            options=["Home", "Scanner", "Analytics", "Database"],
            icons=["house", "upc-scan", "graph-up", "gear"],
            menu_icon="cast",
            default_index=0,
        )
        
        
    
    if selected == "Home":
        home_page()
    elif selected == "Scanner":
        scanner_page()
    elif selected == "Analytics":
        analytics_page()
    elif selected == "Database":
        database_management_page()


if __name__ == "__main__":
    main()