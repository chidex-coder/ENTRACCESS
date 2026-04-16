"""Standalone Admin Portal Application"""
import streamlit as st
from streamlit_option_menu import option_menu
from datetime import datetime, time, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CHECK_IN_START, CHECK_IN_END, CHECK_OUT_START, CHECK_OUT_END
from database import (
    init_database, get_statistics, get_attendance_records,
    get_all_students, get_student_by_id, delete_student,
    hard_delete_student, delete_attendance_record, clear_all_data,
    reset_database_completely, get_student_attendance_history,
    DB_PATH, get_connection
)

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
    
    # Quick actions
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📊 View Analytics", use_container_width=True):
            st.session_state.selected_menu = "Analytics"
            st.rerun()
    with col2:
        if st.button("👥 Manage Students", use_container_width=True):
            st.session_state.selected_menu = "Database"
            st.rerun()
    with col3:
        if st.button("📈 Export Reports", use_container_width=True):
            st.info("Export functionality available in Analytics tab")
    
    # Recent activity
    st.markdown("## 📋 Recent Activity")
    
    recent_records = get_attendance_records({'limit': 10})
    if recent_records:
        df = pd.DataFrame(recent_records)
        display_cols = ['full_name', 'attendance_date', 'check_in', 'check_out']
        available_cols = [col for col in display_cols if col in df.columns]
        
        if available_cols:
            st.dataframe(
                df[available_cols],
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("No recent activity")

def analytics_page():
    """Analytics dashboard."""
    st.markdown('<h1 class="main-header">📊 Analytics Dashboard</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Comprehensive attendance analytics</p>', unsafe_allow_html=True)
    
    # Filters
    with st.expander("🔍 Filters", expanded=False):
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
        
        with col3:
            status_filter = st.multiselect(
                "Status",
                ["All", "Checked In", "Checked Out"],
                default=["All"]
            )
    
    # Load data
    filters = {
        'date_from': start_date.strftime('%Y-%m-%d'),
        'date_to': end_date.strftime('%Y-%m-%d')
    }
    
    records = get_attendance_records(filters)
    
    if records:
        df = pd.DataFrame(records)
        
        # Convert dates
        if 'attendance_date' in df.columns:
            df['attendance_date'] = pd.to_datetime(df['attendance_date'])
        
        # Key metrics
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
                completion_rate = (completed / len(df)) * 100
                st.metric("Completion Rate", f"{completion_rate:.1f}%")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Daily trend
            if 'attendance_date' in df.columns:
                daily = df.groupby(df['attendance_date'].dt.date).size().reset_index(name='count')
                fig = px.line(daily, x='attendance_date', y='count', 
                             title='Daily Attendance Trend',
                             markers=True)
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Top students
            if 'full_name' in df.columns:
                top_students = df['full_name'].value_counts().head(10).reset_index()
                top_students.columns = ['Student', 'Sessions']
                fig = px.bar(top_students, x='Student', y='Sessions',
                            title='Top 10 Students by Attendance')
                st.plotly_chart(fig, use_container_width=True)
        
        # Data table
        st.markdown("## 📋 Attendance Records")
        
        display_df = df.copy()
        if 'registration_date' in display_df.columns:
            display_df['registration_date'] = pd.to_datetime(display_df['registration_date']).dt.strftime('%Y-%m-%d')
        if 'check_in' in display_df.columns:
            display_df['check_in'] = pd.to_datetime(display_df['check_in']).dt.strftime('%Y-%m-%d %H:%M')
        if 'check_out' in display_df.columns:
            display_df['check_out'] = pd.to_datetime(display_df['check_out']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Select columns to display
        display_cols = ['full_name', 'email', 'phone', 'attendance_date', 'check_in', 'check_out']
        available_cols = [col for col in display_cols if col in display_df.columns]
        
        st.dataframe(display_df[available_cols], use_container_width=True, hide_index=True)
        
        # Export
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Export to CSV",
            csv,
            f"attendance_report_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv"
        )
    else:
        st.info("No attendance records found for the selected period")

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
            
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export CSV", csv, f"students_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        else:
            st.info("No students found")
    
    with tab2:
        st.subheader("Delete Individual Records")
        
        delete_option = st.radio("Select:", ["Delete Student", "Delete Attendance Record"])
        
        if delete_option == "Delete Student":
            student_id = st.number_input("Student ID:", min_value=1, step=1)
            
            if student_id:
                student = get_student_by_id(student_id)
                if student:
                    st.write(f"**Student:** {student['full_name']} ({student['email']})")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🗑️ Soft Delete"):
                            if delete_student(student_id):
                                st.success(f"Student {student_id} marked as deleted")
                                st.rerun()
                    with col2:
                        confirm = st.checkbox("Confirm permanent deletion")
                        if confirm and st.button("💣 Hard Delete"):
                            if hard_delete_student(student_id):
                                st.success(f"Student {student_id} permanently deleted")
                                st.rerun()
                else:
                    st.error("Student not found")
        
        else:  # Delete attendance record
            attendance_id = st.number_input("Attendance ID:", min_value=1, step=1)
            if attendance_id and st.button("Delete"):
                if delete_attendance_record(attendance_id):
                    st.success(f"Record {attendance_id} deleted")
                    st.rerun()
    
    with tab3:
        st.subheader("Bulk Operations")
        st.markdown('<div class="danger-box">⚠️ DANGER ZONE - These actions cannot be undone!</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Clear All Data (Keep Structure)**")
            confirm_clear = st.text_input("Type 'CLEAR ALL':")
            if st.button("💣 Clear All Data"):
                if confirm_clear == "CLEAR ALL":
                    if clear_all_data(confirm=True):
                        st.success("All data cleared!")
                        st.rerun()
        
        with col2:
            st.markdown("**Complete Database Reset**")
            confirm_reset = st.text_input("Type 'RESET DB':")
            if st.button("🔥 Reset Database"):
                if confirm_reset == "RESET DB":
                    if reset_database_completely():
                        st.success("Database reset!")
                        st.rerun()
    
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
            st.metric("DB Size", f"{db_size / 1024:.2f} KB")

# Add this new function to admin_app.py

def settings_page():
    """Admin settings page for configuring system parameters"""
    st.markdown('<h1 class="main-header">⚙️ System Settings</h1>', unsafe_allow_html=True)
    
    st.markdown("### ⏰ Attendance Time Configuration")
    
    # Get current times from config
    from config import CHECK_IN_START, CHECK_IN_END, CHECK_OUT_START, CHECK_OUT_END
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Check-in Window")
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
        st.markdown("#### Check-out Window")
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
    st.markdown("### 📋 Current Configuration Preview")
    
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
    
    # Save button
    if st.button("💾 Save Configuration", type="primary", use_container_width=True):
        # Update config file
        try:
            with open('config.py', 'r') as file:
                config_content = file.read()
            
            # Replace time values
            import re
            config_content = re.sub(
                r'CHECK_IN_START = time\(\d+, \d+\)',
                f'CHECK_IN_START = time({new_check_in_start.hour}, {new_check_in_start.minute})',
                config_content
            )
            config_content = re.sub(
                r'CHECK_IN_END = time\(\d+, \d+\)',
                f'CHECK_IN_END = time({new_check_in_end.hour}, {new_check_in_end.minute})',
                config_content
            )
            config_content = re.sub(
                r'CHECK_OUT_START = time\(\d+, \d+\)',
                f'CHECK_OUT_START = time({new_check_out_start.hour}, {new_check_out_start.minute})',
                config_content
            )
            config_content = re.sub(
                r'CHECK_OUT_END = time\(\d+, \d+\)',
                f'CHECK_OUT_END = time({new_check_out_end.hour}, {new_check_out_end.minute})',
                config_content
            )
            
            with open('config.py', 'w') as file:
                file.write(config_content)
            
            st.success("✅ Configuration saved! Please restart the application for changes to take effect.")
            st.info("ℹ️ Both student scanner and admin portal need to be restarted.")
            
            if st.button("🔄 Restart Now"):
                st.rerun()
                
        except Exception as e:
            st.error(f"Failed to save configuration: {str(e)}")

# Then add this to your main() function in admin_app.py
# In the sidebar options, add "Settings" option

def main():
    """Main admin application."""
    with st.sidebar:
        st.markdown("## 🔒 Admin Portal")
        st.markdown("---")
        
        if 'selected_menu' not in st.session_state:
            st.session_state.selected_menu = "Home"
        
        selected = option_menu(
            menu_title="Navigation",
            options=["Home", "Analytics", "Database", "Settings"],  # Added Settings
            icons=["house", "graph-up", "gear", "sliders"],  # Added icon
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "0!important"},
                "icon": {"color": "#667eea", "font-size": "20px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px"},
                "nav-link-selected": {"background-color": "#667eea"},
            }
        )
        
        st.session_state.selected_menu = selected
        
        # Display current time
        st.markdown("---")
        st.markdown(f"**Current Time**\n{datetime.now().strftime('%I:%M %p')}")
        st.markdown(f"**Date**\n{datetime.now().strftime('%B %d, %Y')}")
    
    # Page routing
    if selected == "Home":
        home_page()
    elif selected == "Analytics":
        analytics_page()
    elif selected == "Database":
        database_management_page()
    elif selected == "Settings":  # Added Settings route
        settings_page()

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
            options=["Home", "Analytics", "Database"],
            icons=["house", "graph-up", "gear"],
            menu_icon="cast",
            default_index=0 if st.session_state.selected_menu == "Home" else 
                        (1 if st.session_state.selected_menu == "Analytics" else 2),
            styles={
                "container": {"padding": "0!important"},
                "icon": {"color": "#667eea", "font-size": "20px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px"},
                "nav-link-selected": {"background-color": "#667eea"},
            }
        )
        
        st.session_state.selected_menu = selected
        
        # Display current time
        st.markdown("---")
        st.markdown(f"**Current Time**\n{datetime.now().strftime('%I:%M %p')}")
        st.markdown(f"**Date**\n{datetime.now().strftime('%B %d, %Y')}")
    
    # Page routing
    if selected == "Home":
        home_page()
    elif selected == "Analytics":
        analytics_page()
    elif selected == "Database":
        database_management_page()

if __name__ == "__main__":
    main()