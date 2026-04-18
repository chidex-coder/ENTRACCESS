"""Complete Admin Portal Application"""
import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime, time, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
import re
import time as time_module

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import from existing modules
from database import (
    init_database, get_statistics, get_attendance_records,
    get_all_students, get_student_by_id, delete_student,
    hard_delete_student, delete_attendance_record, clear_all_data,
    reset_database_completely, get_student_attendance_history,
    DB_PATH, get_connection
)

# Import config
try:
    from config import CHECK_IN_START, CHECK_IN_END, CHECK_OUT_START, CHECK_OUT_END
except ImportError:
    # Default times if config doesn't exist
    CHECK_IN_START = time(19, 0)   # 7:00 PM
    CHECK_IN_END = time(23, 59)    # 11:59 PM
    CHECK_OUT_START = time(13, 0)  # 1:00 PM
    CHECK_OUT_END = time(18, 59)   # 6:59 PM

# Page configuration
st.set_page_config(
    page_title="Admin Portal - Attendance System",
    page_icon="🔒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database on startup
init_database()

# Custom CSS
st.markdown("""
<style>
    /* Main header */
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
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
    
    /* Stat cards */
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
    }
    
    .stat-card:hover {
        transform: translateY(-5px);
    }
    
    .stat-number {
        font-size: 2rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    
    /* Custom cards */
    .custom-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        margin-bottom: 1.5rem;
        border: 1px solid #e5e7eb;
    }
    
    /* Warning box */
    .warning-box {
        background: #fef3c7;
        border-left: 4px solid #f59e0b;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    /* Danger box */
    .danger-box {
        background: #fee2e2;
        border-left: 4px solid #ef4444;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    /* Success box */
    .success-box {
        background: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    /* Info box */
    .info-box {
        background: #d1ecf1;
        border-left: 4px solid #17a2b8;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    
    /* Time display */
    .time-badge {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 10px;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: 600;
        border: none;
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* Metric styling */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

def home_page():
    """Admin home page with dashboard."""
    st.markdown('<h1 class="main-header">🔒 Admin Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Student Attendance Management System</p>', unsafe_allow_html=True)
    
    # Get statistics
    stats = get_statistics()
    
    # Display metrics
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats['total_students']}</div>
            <div class="stat-label">Total Students</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats['today_check_ins']}</div>
            <div class="stat-label">Today's Check-ins</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats['today_check_outs']}</div>
            <div class="stat-label">Today's Check-outs</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats['avg_duration']:.1f}</div>
            <div class="stat-label">Avg Duration (hrs)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col5:
        st.markdown(f"""
        <div class="stat-card">
            <div class="stat-number">{stats['recent_duplicates']}</div>
            <div class="stat-label">Duplicate Attempts</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Current time and status
    now = datetime.now()
    current_time = now.time()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="info-box">
            <strong>🕐 Current Time:</strong><br>
            {now.strftime('%I:%M:%S %p')}<br>
            {now.strftime('%B %d, %Y')}
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if CHECK_IN_START <= current_time <= CHECK_IN_END:
            st.markdown(f"""
            <div class="success-box">
                <strong>✅ Check-in Window:</strong><br>
                ACTIVE<br>
                {CHECK_IN_START.strftime('%I:%M %p')} - {CHECK_IN_END.strftime('%I:%M %p')}
            </div>
            """, unsafe_allow_html=True)
        elif CHECK_OUT_START <= current_time <= CHECK_OUT_END:
            st.markdown(f"""
            <div class="success-box">
                <strong>✅ Check-out Window:</strong><br>
                ACTIVE<br>
                {CHECK_OUT_START.strftime('%I:%M %p')} - {CHECK_OUT_END.strftime('%I:%M %p')}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="warning-box">
                <strong>⏰ Scanner Status:</strong><br>
                INACTIVE<br>
                Next: Check-in at {CHECK_IN_START.strftime('%I:%M %p')}
            </div>
            """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="info-box">
            <strong>📊 Quick Stats:</strong><br>
            Completion Rate: {(stats['today_check_outs']/stats['today_check_ins']*100 if stats['today_check_ins'] > 0 else 0):.1f}%<br>
            Active Sessions: {stats['today_check_ins'] - stats['today_check_outs']}
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Quick actions
    st.markdown("### 🚀 Quick Actions")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("📊 View Analytics", use_container_width=True):
            st.session_state.selected_menu = "Analytics"
            st.rerun()
    
    with col2:
        if st.button("👥 Manage Students", use_container_width=True):
            st.session_state.selected_menu = "Database"
            st.rerun()
    
    with col3:
        if st.button("⚙️ Configure Times", use_container_width=True):
            st.session_state.selected_menu = "Settings"
            st.rerun()
    
    with col4:
        if st.button("📈 Export Reports", use_container_width=True):
            st.info("Export functionality available in Analytics tab")
    
    st.markdown("---")
    
    # Recent activity
    st.markdown("## 📋 Recent Activity")
    
    recent_records = get_attendance_records({'limit': 10})
    if recent_records:
        df = pd.DataFrame(recent_records)
        display_cols = ['full_name', 'attendance_date', 'check_in', 'check_out']
        available_cols = [col for col in display_cols if col in df.columns]
        
        if available_cols:
            # Format for display
            display_df = df[available_cols].copy()
            if 'attendance_date' in display_df.columns:
                display_df['attendance_date'] = pd.to_datetime(display_df['attendance_date']).dt.strftime('%Y-%m-%d')
            if 'check_in' in display_df.columns:
                display_df['check_in'] = pd.to_datetime(display_df['check_in']).dt.strftime('%I:%M %p') if pd.notna(display_df['check_in']).any() else '—'
            if 'check_out' in display_df.columns:
                display_df['check_out'] = pd.to_datetime(display_df['check_out']).dt.strftime('%I:%M %p') if pd.notna(display_df['check_out']).any() else '—'
            
            # Rename columns only if we have the expected number
            column_mapping = {
                'full_name': 'Student',
                'attendance_date': 'Date', 
                'check_in': 'Check-in',
                'check_out': 'Check-out'
            }
            display_df = display_df.rename(columns=column_mapping)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("No recent activity")

def analytics_page():
    """Analytics dashboard."""
    st.markdown('<h1 class="main-header">📊 Analytics Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Comprehensive attendance analytics</p>', unsafe_allow_html=True)
    
    # Filters
    with st.expander("🔍 Advanced Filters", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            date_range = st.selectbox(
                "Date Range",
                ["Last 7 Days", "Last 30 Days", "This Month", "Last Month", "Custom"]
            )
        
        with col2:
            if date_range == "Custom":
                start_date = st.date_input("Start Date", datetime.now().date() - timedelta(days=30))
                end_date = st.date_input("End Date", datetime.now().date())
            else:
                today = datetime.now().date()
                if date_range == "Last 7 Days":
                    start_date = today - timedelta(days=7)
                    end_date = today
                elif date_range == "Last 30 Days":
                    start_date = today - timedelta(days=30)
                    end_date = today
                elif date_range == "This Month":
                    start_date = today.replace(day=1)
                    end_date = today
                elif date_range == "Last Month":
                    last_month = today.replace(day=1) - timedelta(days=1)
                    start_date = last_month.replace(day=1)
                    end_date = last_month
                else:
                    start_date = today - timedelta(days=30)
                    end_date = today
        
        with col3:
            student_filter = st.text_input("Student Name", placeholder="Filter by student...")
    
    # Load data
    filters = {
        'date_from': start_date.strftime('%Y-%m-%d'),
        'date_to': end_date.strftime('%Y-%m-%d')
    }
    
    if student_filter:
        filters['full_name'] = student_filter
    
    records = get_attendance_records(filters)
    
    if records:
        df = pd.DataFrame(records)
        
        # Convert dates
        if 'attendance_date' in df.columns:
            df['attendance_date'] = pd.to_datetime(df['attendance_date'])
        if 'check_in' in df.columns:
            df['check_in'] = pd.to_datetime(df['check_in'])
        if 'check_out' in df.columns:
            df['check_out'] = pd.to_datetime(df['check_out'])
        
        # Calculate duration
        if 'check_in' in df.columns and 'check_out' in df.columns:
            df['duration_hours'] = (df['check_out'] - df['check_in']).dt.total_seconds() / 3600
        
        # Key metrics
        st.markdown("### 📈 Key Metrics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Sessions", len(df))
        with col2:
            unique_students = df['full_name'].nunique() if 'full_name' in df.columns else 0
            st.metric("Unique Students", unique_students)
        with col3:
            avg_sessions = len(df) / unique_students if unique_students > 0 else 0
            st.metric("Avg Sessions/Student", f"{avg_sessions:.1f}")
        with col4:
            if 'check_out' in df.columns:
                completed = len(df[df['check_out'].notna()])
                completion_rate = (completed / len(df)) * 100 if len(df) > 0 else 0
                st.metric("Completion Rate", f"{completion_rate:.1f}%")
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Daily Attendance Trend")
            if 'attendance_date' in df.columns:
                daily = df.groupby(df['attendance_date'].dt.date).size().reset_index(name='count')
                fig = px.line(daily, x='attendance_date', y='count', 
                             title='Daily Attendance Over Time',
                             markers=True,
                             labels={'attendance_date': 'Date', 'count': 'Number of Students'})
                fig.update_layout(showlegend=False, hovermode='x unified')
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 🏆 Top Students")
            if 'full_name' in df.columns:
                top_students = df['full_name'].value_counts().head(10).reset_index()
                top_students.columns = ['Student', 'Sessions']
                fig = px.bar(top_students, x='Student', y='Sessions',
                            title='Top 10 Students by Attendance',
                            color='Sessions',
                            color_continuous_scale='Viridis')
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
        
        # Additional charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### ⏰ Hourly Distribution")
            if 'check_in' in df.columns:
                df['hour'] = df['check_in'].dt.hour
                hourly = df[df['hour'].notna()].groupby('hour').size().reset_index(name='count')
                if not hourly.empty:
                    fig = px.bar(hourly, x='hour', y='count',
                                title='Attendance by Hour',
                                labels={'hour': 'Hour of Day', 'count': 'Number of Check-ins'})
                    fig.update_layout(xaxis=dict(tickmode='linear', tick0=0, dtick=2))
                    st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 📧 Email Statistics")
            email_data = []
            if 'check_in_email_sent' in df.columns:
                email_data.append({'Type': 'Check-in', 'Sent': df['check_in_email_sent'].sum()})
            if 'check_out_email_sent' in df.columns:
                email_data.append({'Type': 'Check-out', 'Sent': df['check_out_email_sent'].sum()})
            
            if email_data:
                email_df = pd.DataFrame(email_data)
                fig = px.pie(email_df, values='Sent', names='Type',
                            title='Email Notifications Sent',
                            color_discrete_sequence=['#667eea', '#764ba2'])
                st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        st.markdown("---")
        st.markdown("### 📋 Detailed Records")
        
        display_df = df.copy()
        
        # Format for display
        if 'attendance_date' in display_df.columns:
            display_df['attendance_date'] = display_df['attendance_date'].dt.strftime('%Y-%m-%d')
        if 'check_in' in display_df.columns:
            display_df['check_in'] = display_df['check_in'].dt.strftime('%I:%M %p')
        if 'check_out' in display_df.columns:
            display_df['check_out'] = display_df['check_out'].dt.strftime('%I:%M %p') if pd.notna(display_df['check_out']).any() else '—'
        if 'duration_hours' in display_df.columns:
            display_df['duration'] = display_df['duration_hours'].apply(lambda x: f"{x:.1f}h" if pd.notna(x) else '—')
        
        # Select columns to display
        display_cols = ['full_name', 'attendance_date', 'check_in', 'check_out', 'duration']
        available_cols = [col for col in display_cols if col in display_df.columns]
        
        if available_cols:
            st.dataframe(display_df[available_cols], use_container_width=True, hide_index=True)
            
            # Export buttons
            col1, col2 = st.columns(2)
            with col1:
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "📥 Export to CSV",
                    csv,
                    f"attendance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col2:
                # Summary statistics
                with st.expander("📊 View Summary Statistics"):
                    st.write("**Data Summary:**")
                    st.write(f"- Date Range: {start_date} to {end_date}")
                    st.write(f"- Total Records: {len(df)}")
                    st.write(f"- Unique Students: {unique_students}")
                    if 'duration_hours' in df.columns:
                        avg_dur = df['duration_hours'].mean()
                        st.write(f"- Average Duration: {avg_dur:.1f} hours" if pd.notna(avg_dur) else "-")
    else:
        st.info("No attendance records found for the selected period")
        st.markdown("""
        <div class="info-box">
            <strong>💡 Tips:</strong>
            <ul>
                <li>Try expanding your date range</li>
                <li>Check if students have registered</li>
                <li>Make sure attendance has been recorded</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

def database_management_page():
    """Database management page."""
    st.markdown('<h1 class="main-header">⚙️ Database Management</h1>', unsafe_allow_html=True)
    
    st.warning("⚠️ **Warning:** Actions on this page can permanently delete data.")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 View Students", "🗑️ Delete Records", "💣 Bulk Operations", "📊 Stats"])
    
    with tab1:
        st.subheader("All Registered Students")
        
        show_inactive = st.checkbox("Show deleted students", value=False)
        students = get_all_students(active_only=not show_inactive)
        
        if students:
            df = pd.DataFrame(students)
            if 'registration_date' in df.columns:
                df['registration_date'] = pd.to_datetime(df['registration_date']).dt.strftime('%Y-%m-%d %H:%M')
            if 'is_active' in df.columns:
                df['status'] = df['is_active'].map({1: '✅ Active', 0: '❌ Deleted'})
            
            # Select columns to display
            display_cols = ['id', 'full_name', 'email', 'phone', 'student_code', 'registration_date', 'status']
            available_cols = [col for col in display_cols if col in df.columns]
            
            st.dataframe(df[available_cols], use_container_width=True, hide_index=True)
            
            # Export button
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Export Students CSV",
                csv,
                f"students_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv"
            )
        else:
            st.info("No students found")
    
    with tab2:
        st.subheader("Delete Individual Records")
        
        delete_option = st.radio("Select:", ["Delete Student", "Delete Attendance Record"], horizontal=True)
        
        if delete_option == "Delete Student":
            student_id = st.number_input("Student ID:", min_value=1, step=1)
            
            if student_id:
                student = get_student_by_id(student_id)
                if student:
                    st.write(f"**Student:** {student['full_name']} ({student['email']})")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Soft Delete (Hide)", use_container_width=True):
                            if delete_student(student_id):
                                st.success(f"Student {student_id} marked as deleted")
                                st.rerun()
                            else:
                                st.error("Failed to delete")
                    
                    with col2:
                        confirm = st.checkbox("Confirm permanent deletion")
                        if confirm and st.button("💣 Hard Delete (Permanent)", use_container_width=True, type="primary"):
                            if hard_delete_student(student_id):
                                st.success(f"Student {student_id} permanently deleted")
                                st.rerun()
                            else:
                                st.error("Failed to delete")
                else:
                    st.error("Student not found")
        
        else:  # Delete attendance record
            attendance_id = st.number_input("Attendance ID:", min_value=1, step=1)
            if attendance_id and st.button("Delete Record", use_container_width=True, type="primary"):
                if delete_attendance_record(attendance_id):
                    st.success(f"Attendance record {attendance_id} deleted")
                    st.rerun()
                else:
                    st.error("Failed to delete")
    
    with tab3:
        st.subheader("Bulk Operations")
        st.markdown('<div class="danger-box">⚠️ DANGER ZONE - These actions cannot be undone!</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Clear All Data (Keep Structure)**")
            st.markdown("*Deletes all student and attendance records but keeps the database structure*")
            confirm_clear = st.text_input("Type 'CLEAR ALL' to confirm:")
            if st.button("💣 Clear All Data", type="primary", use_container_width=True):
                if confirm_clear == "CLEAR ALL":
                    if clear_all_data(confirm=True):
                        st.success("✅ All data cleared successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to clear data")
                else:
                    st.error("Please type 'CLEAR ALL' to confirm")
        
        with col2:
            st.markdown("**Complete Database Reset**")
            st.markdown("*Deletes everything and recreates the database from scratch*")
            confirm_reset = st.text_input("Type 'RESET DB' to confirm:")
            if st.button("🔥 Reset Database", type="primary", use_container_width=True):
                if confirm_reset == "RESET DB":
                    if reset_database_completely():
                        st.success("✅ Database reset successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to reset database")
                else:
                    st.error("Please type 'RESET DB' to confirm")
    
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
            
            cursor.execute('SELECT COUNT(*) FROM students WHERE is_active = 0')
            deleted_students = cursor.fetchone()[0]
        
        db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Students", total_students)
        with col2:
            st.metric("Deleted Students", deleted_students)
        with col3:
            st.metric("Attendance Records", total_attendance)
        with col4:
            st.metric("Scan Logs", total_logs)
        
        st.metric("Database Size", f"{db_size / 1024:.2f} KB")
        
        # Last backup info
        st.markdown("---")
        st.markdown("### 💾 Backup Information")
        st.info("""
        **Automatic backups are created when you reset the database.**
        Backup files are saved as `backup_YYYYMMDD_HHMMSS.db` in the data directory.
        """)

def settings_page():
    """Admin settings page for configuring system parameters"""
    st.markdown('<h1 class="main-header">⚙️ System Settings</h1>', unsafe_allow_html=True)
    
    st.markdown("### ⏰ Attendance Time Configuration")
    st.info("Configure the windows when students can check in and check out")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🌙 Check-in Window")
        new_check_in_start = st.time_input(
            "Check-in Start Time",
            value=CHECK_IN_START,
            help="When students can start checking in"
        )
        new_check_in_end = st.time_input(
            "Check-in End Time",
            value=CHECK_IN_END,
            help="When check-in window closes"
        )
        
        if new_check_in_start >= new_check_in_end:
            st.error("⚠️ Check-in start time must be before end time!")
    
    with col2:
        st.markdown("#### ☀️ Check-out Window")
        new_check_out_start = st.time_input(
            "Check-out Start Time",
            value=CHECK_OUT_START,
            help="When students can start checking out"
        )
        new_check_out_end = st.time_input(
            "Check-out End Time",
            value=CHECK_OUT_END,
            help="When check-out window closes"
        )
        
        if new_check_out_start >= new_check_out_end:
            st.error("⚠️ Check-out start time must be before end time!")
    
    st.markdown("---")
    
    # Preview current configuration
    st.markdown("### 📋 Configuration Preview")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"""
        **Check-in Window:**  
        {new_check_in_start.strftime('%I:%M %p')} - {new_check_in_end.strftime('%I:%M %p')}
        """)
    with col2:
        st.info(f"""
        **Check-out Window:**  
        {new_check_out_start.strftime('%I:%M %p')} - {new_check_out_end.strftime('%I:%M %p')}
        """)
    
    # Current time indicator
    now = datetime.now()
    current_time = now.time()
    st.markdown(f"**Current Time:** {current_time.strftime('%I:%M:%S %p')}")
    st.markdown(f"**Current Date:** {now.strftime('%B %d, %Y')}")
    
    # Status indicator
    if new_check_in_start <= current_time <= new_check_in_end:
        st.success("✅ Check-in window is currently ACTIVE")
    elif new_check_out_start <= current_time <= new_check_out_end:
        st.success("✅ Check-out window is currently ACTIVE")
    else:
        next_window = "Check-in" if current_time < new_check_in_start else "Check-in tomorrow"
        st.warning(f"⏰ No attendance window is currently active. Next: {next_window}")
    
    st.markdown("---")
    
    # Email configuration section
    st.markdown("### 📧 Email Configuration")
    
    try:
        from email_service import email_service
        
        if email_service.is_configured:
            st.success(f"✅ Email configured for: {email_service.smtp_user}")
        else:
            st.warning("⚠️ Email not configured")
            with st.expander("📧 How to Configure Email"):
                st.markdown("""
                **For Gmail:**
                1. Enable 2-Factor Authentication on your Google account
                2. Generate an App Password:
                   - Go to https://myaccount.google.com/apppasswords
                   - Select "Mail" as the app
                   - Select "Other" as the device
                   - Copy the 16-character password
                3. Add to `.streamlit/secrets.toml`:
                ```toml
                [email]
                user = "your-email@gmail.com"
                password = "your-16-digit-app-password"
                            """)
    except:
        st.warning("⚠️ Email service not available")

        st.markdown("---")

        # Save button

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💾 Save Configuration", type="primary", use_container_width=True):
                try:

                    # Read current config file

                    config_path = os.path.join(os.path.dirname(__file__), 'config.py')

                    if os.path.exists(config_path):
                        with open(config_path, 'r') as file:
                            config_content = file.read()

                           # Update check-in times

                            config_content = re.sub(r'CHECK_IN_START = time\d+, \d+',f'CHECK_IN_START = time({new_check_in_start.hour}, {new_check_in_start.minute})',config_content)
                            config_content = re.sub(r'CHECK_IN_END = time\d+, \d+',f'CHECK_IN_END = time({new_check_in_end.hour}, {new_check_in_end.minute})',config_content)
                            config_content = re.sub(r'CHECK_OUT_START = time\d+, \d+',f'CHECK_OUT_START = time({new_check_out_start.hour}, {new_check_out_start.minute})',config_content)
                            config_content = re.sub(r'CHECK_OUT_END = time\d+, \d+',f'CHECK_OUT_END = time({new_check_out_end.hour}, {new_check_out_end.minute})',config_content)

                        with open(config_path, 'w') as file:
                            file.write(config_content)
                            st.success("✅ Configuration saved successfully!")
                            st.info("ℹ️ Changes will take effect immediately")
                            time_module.sleep(1)
                            st.rerun()
                    else:
                        st.error("Config file not found. Please create config.py first.")

                except Exception as e:
                    st.error(f"Failed to save configuration: {str(e)}")

    # Reset to defaults button

    st.markdown("---")
    with st.expander("🔄 Reset to Default Times"):
        st.warning("This will reset attendance times to default values (7 PM - 11:59 PM for check-in, 1 PM - 6:59 PM for check-out)")

        if st.button("Reset to Defaults", type="secondary"):
            try:
                config_path = os.path.join(os.path.dirname(__file__), 'config.py')

                with open(config_path, 'r') as file:
                    config_content = file.read()

                    # Reset to defaults

                    config_content = re.sub(r'CHECK_IN_START = time\d+, \d+','CHECK_IN_START = time(19, 0)',config_content)
                    config_content = re.sub(r'CHECK_IN_END = time\d+, \d+','CHECK_IN_END = time(23, 59)',config_content)
                    config_content = re.sub(r'CHECK_OUT_START = time\d+, \d+','CHECK_OUT_START = time(13, 0)',config_content)
                    config_content = re.sub(r'CHECK_OUT_END = time\d+, \d+','CHECK_OUT_END = time(18, 59)',config_content)

                with open(config_path, 'w') as file:
                    file.write(config_content)

                    st.success("✅ Reset to default times successful!")
                    time_module.sleep(1)
                    st.rerun()

            except Exception as e:
                st.error(f"Failed to reset: {str(e)}")

def main():
    """Main admin application."""

    # Sidebar navigation
    with st.sidebar:
        st.markdown("## 🔒 Admin Portal")
        st.markdown("---")

        # Initialize session state for menu
        if 'selected_menu' not in st.session_state:
            st.session_state.selected_menu = "Home"

        selected = option_menu(
            menu_title="Navigation",
            options=["Home", "Analytics", "Database", "Settings"],
            icons=["house", "graph-up", "gear", "sliders"],
            menu_icon="cast",
            default_index=0 if st.session_state.selected_menu == "Home" else
            (1 if st.session_state.selected_menu == "Analytics" else
            (2 if st.session_state.selected_menu == "Database" else 3)),
            styles={
                "container": {"padding": "0!important"},
                "icon": {"color": "#667eea", "font-size": "20px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px"},
                "nav-link-selected": {"background-color": "#667eea"},
            }
        )

        st.session_state.selected_menu = selected

        # Display current time and status
        st.markdown("---")
        st.markdown("### 📊 System Status")

        now = datetime.now()
        current_time = now.time()

        st.markdown(f"🕐 Time{now.strftime('%I:%M %p')}")
        st.markdown(f"📅 Date{now.strftime('%B %d, %Y')}")

        # Show current window status
        if CHECK_IN_START <= current_time <= CHECK_IN_END:
            st.success("🟢 Check-in Active")
        elif CHECK_OUT_START <= current_time <= CHECK_OUT_END:
            st.success("🟢 Check-out Active")
        else:
            st.warning("🔴 Scanner Inactive")

        st.markdown("---")
        st.markdown("### ℹ️ Info")
        st.markdown(f"Version: 2.0.0")
        st.markdown(f"Students: {get_statistics()['total_students']}")

    # Page routing
    if selected == "Home":
        home_page()
    elif selected == "Analytics":
        analytics_page()
    elif selected == "Database":
        database_management_page()
    elif selected == "Settings":
        settings_page()

if __name__ == "__main__":
    main()
