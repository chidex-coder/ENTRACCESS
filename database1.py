# database.py - Fixed version with correct SQL syntax
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path

# Get the directory where the script is located
BASE_DIR = Path(__file__).resolve().parent

# Define database path - ensure directory exists
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "attendance_system.db"

# Create data directory if it doesn't exist
DB_DIR.mkdir(exist_ok=True)

# Make sure DATABASE_PATH is defined for backward compatibility
DATABASE_PATH = DB_PATH

class DatabaseManager:
    """Database manager for attendance system"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DB_PATH)
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def init_database(self):
        """Initialize database schema"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Students table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS students (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        full_name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        phone TEXT NOT NULL,
                        qr_code TEXT UNIQUE NOT NULL,
                        registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Attendance table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS attendance (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id INTEGER NOT NULL,
                        qr_code TEXT NOT NULL,
                        check_in_time TIMESTAMP,
                        check_out_time TIMESTAMP,
                        attendance_date DATE DEFAULT CURRENT_DATE,
                        check_in_email_sent INTEGER DEFAULT 0,
                        check_out_email_sent INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'active',
                        FOREIGN KEY (student_id) REFERENCES students(id),
                        UNIQUE(student_id, attendance_date)
                    )
                ''')
                
                # Scan logs table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS scan_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        qr_code TEXT NOT NULL,
                        scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        action TEXT,
                        status TEXT,
                        details TEXT
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_students_qr ON students(qr_code)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(attendance_date)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_scan_log_time ON scan_log(scan_time)')
                
                print(f"Database initialized successfully at: {self.db_path}")
                
        except Exception as e:
            print(f"Error initializing database: {str(e)}")
            raise

# Global database instance
db_manager = DatabaseManager()

# Helper functions for backward compatibility
def init_database():
    """Initialize database - for backward compatibility"""
    return db_manager.init_database()

def get_connection():
    """Get database connection - for backward compatibility"""
    return db_manager.get_connection()

def register_student(full_name, email, phone, qr_code=None):
    """Register a new student"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if student already exists
            cursor.execute('SELECT id FROM students WHERE email = ? OR phone = ?', (email, phone))
            existing = cursor.fetchone()
            if existing:
                return False, "Student with this email or phone already exists", None
            
            # Insert new student
            cursor.execute('''
                INSERT INTO students (full_name, email, phone, qr_code)
                VALUES (?, ?, ?, ?)
            ''', (full_name, email, phone, qr_code or f"STU_{datetime.now().strftime('%Y%m%d%H%M%S')}"))
            
            student_id = cursor.lastrowid
            
            return True, qr_code, student_id
    except Exception as e:
        return False, f"Database error: {str(e)}", None

def get_student_by_qr(qr_code):
    """Get student by QR code"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, full_name, email, phone, qr_code, is_active
                FROM students
                WHERE qr_code = ? AND is_active = 1
            ''', (qr_code,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        print(f"Error getting student: {str(e)}")
        return None

def get_student_by_id(student_id):
    """Get student by ID"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, full_name, email, phone, qr_code, registration_date, is_active
                FROM students
                WHERE id = ?
            ''', (student_id,))
            
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        print(f"Error getting student: {str(e)}")
        return None

def process_check_in(student_id, qr_code):
    """Process student check-in"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().date()
            current_time = datetime.now()
            
            # Check if already checked in today
            cursor.execute('''
                SELECT id, check_in_time, check_out_time
                FROM attendance
                WHERE student_id = ? AND attendance_date = ?
            ''', (student_id, today))
            
            existing = cursor.fetchone()
            
            if existing:
                if existing['check_in_time']:
                    return {
                        'success': False,
                        'status': 'duplicate',
                        'details': existing['check_in_time'][:19] if existing['check_in_time'] else 'earlier'
                    }
                else:
                    # Update existing record
                    cursor.execute('''
                        UPDATE attendance
                        SET check_in_time = ?, status = 'checked_in'
                        WHERE id = ?
                    ''', (current_time, existing['id']))
                    attendance_id = existing['id']
            else:
                # Create new attendance record
                cursor.execute('''
                    INSERT INTO attendance (student_id, qr_code, check_in_time, attendance_date, status)
                    VALUES (?, ?, ?, ?, 'checked_in')
                ''', (student_id, qr_code, current_time, today))
                attendance_id = cursor.lastrowid
            
            # Log the scan
            cursor.execute('''
                INSERT INTO scan_log (qr_code, action, status, details)
                VALUES (?, 'check_in', 'success', ?)
            ''', (qr_code, f"Student {student_id} checked in at {current_time}"))
            
            return {
                'success': True,
                'attendance_id': attendance_id,
                'timestamp': current_time,
                'status': 'success'
            }
    except Exception as e:
        return {
            'success': False,
            'status': 'error',
            'message': str(e)
        }

def process_check_out(student_id, qr_code):
    """Process student check-out"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().date()
            current_time = datetime.now()
            
            # Find today's attendance record
            cursor.execute('''
                SELECT id, check_in_time, check_out_time
                FROM attendance
                WHERE student_id = ? AND attendance_date = ?
            ''', (student_id, today))
            
            record = cursor.fetchone()
            
            if not record:
                return {
                    'success': False,
                    'status': 'error',
                    'message': 'No check-in record found for today',
                    'details': 'Please check in first'
                }
            
            if record['check_out_time']:
                return {
                    'success': False,
                    'status': 'duplicate',
                    'details': record['check_out_time'][:19] if record['check_out_time'] else 'earlier'
                }
            
            # Calculate duration
            check_in_time = datetime.fromisoformat(record['check_in_time']) if isinstance(record['check_in_time'], str) else record['check_in_time']
            duration = current_time - check_in_time
            
            # Update attendance record
            cursor.execute('''
                UPDATE attendance
                SET check_out_time = ?, status = 'checked_out'
                WHERE id = ?
            ''', (current_time, record['id']))
            
            # Log the scan
            cursor.execute('''
                INSERT INTO scan_log (qr_code, action, status, details)
                VALUES (?, 'check_out', 'success', ?)
            ''', (qr_code, f"Student {student_id} checked out at {current_time}, duration: {duration}"))
            
            return {
                'success': True,
                'attendance_id': record['id'],
                'timestamp': current_time,
                'check_in_time': check_in_time,
                'duration': duration,
                'status': 'success'
            }
    except Exception as e:
        return {
            'success': False,
            'status': 'error',
            'message': str(e)
        }

def update_email_status(attendance_id, email_type):
    """Update email sent status"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            if email_type == 'check_in':
                cursor.execute('UPDATE attendance SET check_in_email_sent = 1 WHERE id = ?', (attendance_id,))
            elif email_type == 'check_out':
                cursor.execute('UPDATE attendance SET check_out_email_sent = 1 WHERE id = ?', (attendance_id,))
            return True
    except Exception as e:
        print(f"Error updating email status: {str(e)}")
        return False

def get_attendance_records(filters=None):
    """Get attendance records with filters - FIXED SQL SYNTAX"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Base query - note the space before ORDER BY
            query = '''
                SELECT 
                    s.id as student_id,
                    s.full_name,
                    s.email,
                    s.phone,
                    a.id as attendance_id,
                    a.attendance_date,
                    a.check_in_time,
                    a.check_out_time,
                    a.check_in_email_sent,
                    a.check_out_email_sent,
                    a.status
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE 1=1
            '''
            params = []
            
            # Add filters
            if filters:
                if 'date_from' in filters and filters['date_from']:
                    query += ' AND a.attendance_date >= ?'
                    params.append(filters['date_from'])
                if 'date_to' in filters and filters['date_to']:
                    query += ' AND a.attendance_date <= ?'
                    params.append(filters['date_to'])
                if 'full_name' in filters and filters['full_name']:
                    query += ' AND s.full_name LIKE ?'
                    params.append(f"%{filters['full_name']}%")
                if 'email' in filters and filters['email']:
                    query += ' AND s.email LIKE ?'
                    params.append(f"%{filters['email']}%")
                if 'phone' in filters and filters['phone']:
                    query += ' AND s.phone LIKE ?'
                    params.append(f"%{filters['phone']}%")
            
            # Add ORDER BY - with proper spacing
            query += ' ORDER BY a.attendance_date DESC, a.check_in_time DESC'
            
            # Add LIMIT if specified
            if filters and 'limit' in filters and filters['limit']:
                query += ' LIMIT ?'
                params.append(filters['limit'])
            
            # Execute query
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                result.append(dict(row))
            
            return result
            
    except Exception as e:
        print(f"Error getting attendance records: {str(e)}")
        print(f"Query was: {query if 'query' in locals() else 'N/A'}")
        return []

def get_statistics():
    """Get system statistics"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Total students
            cursor.execute('SELECT COUNT(*) as count FROM students WHERE is_active = 1')
            total_students = cursor.fetchone()['count']
            
            # Today's check-ins
            today = datetime.now().date()
            cursor.execute('''
                SELECT COUNT(*) as count FROM attendance 
                WHERE attendance_date = ? AND check_in_time IS NOT NULL
            ''', (today,))
            today_check_ins = cursor.fetchone()['count']
            
            # Today's check-outs
            cursor.execute('''
                SELECT COUNT(*) as count FROM attendance 
                WHERE attendance_date = ? AND check_out_time IS NOT NULL
            ''', (today,))
            today_check_outs = cursor.fetchone()['count']
            
            # Average duration for completed sessions in last 7 days
            cursor.execute('''
                SELECT AVG(
                    (julianday(check_out_time) - julianday(check_in_time)) * 24
                ) as avg_duration
                FROM attendance
                WHERE check_in_time IS NOT NULL 
                AND check_out_time IS NOT NULL
                AND attendance_date >= date('now', '-7 days')
            ''')
            avg_result = cursor.fetchone()
            avg_duration = avg_result['avg_duration'] if avg_result and avg_result['avg_duration'] else 0
            
            # Recent duplicate attempts (last 24 hours)
            cursor.execute('''
                SELECT COUNT(*) as count FROM scan_log
                WHERE scan_time >= datetime('now', '-1 day')
                AND status = 'duplicate'
            ''')
            recent_duplicates = cursor.fetchone()['count']
            
            return {
                'total_students': total_students,
                'today_check_ins': today_check_ins,
                'today_check_outs': today_check_outs,
                'avg_duration': avg_duration if avg_duration else 0,
                'recent_duplicates': recent_duplicates
            }
    except Exception as e:
        print(f"Error getting statistics: {str(e)}")
        return {
            'total_students': 0,
            'today_check_ins': 0,
            'today_check_outs': 0,
            'avg_duration': 0,
            'recent_duplicates': 0
        }

def get_all_students(active_only=True):
    """Get all students"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute('SELECT * FROM students WHERE is_active = 1 ORDER BY registration_date DESC')
            else:
                cursor.execute('SELECT * FROM students ORDER BY registration_date DESC')
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting students: {str(e)}")
        return []

def delete_student(student_id):
    """Soft delete a student"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE students SET is_active = 0 WHERE id = ?', (student_id,))
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting student: {str(e)}")
        return False

def hard_delete_student(student_id):
    """Permanently delete a student and all related records"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # Delete attendance records first
            cursor.execute('DELETE FROM attendance WHERE student_id = ?', (student_id,))
            # Delete scan logs
            cursor.execute('DELETE FROM scan_log WHERE qr_code IN (SELECT qr_code FROM students WHERE id = ?)', (student_id,))
            # Delete student
            cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error hard deleting student: {str(e)}")
        return False

def delete_attendance_record(attendance_id):
    """Delete an attendance record"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM attendance WHERE id = ?', (attendance_id,))
            return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting attendance record: {str(e)}")
        return False

def clear_all_data(confirm=False):
    """Clear all data from tables"""
    if not confirm:
        return False
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM attendance')
            cursor.execute('DELETE FROM scan_log')
            cursor.execute('DELETE FROM students')
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('students', 'attendance', 'scan_log')")
            return True
    except Exception as e:
        print(f"Error clearing data: {str(e)}")
        return False

def reset_database_completely():
    """Completely reset the database"""
    try:
        # Close any existing connections
        global db_manager
        db_manager = None
        
        # Delete the database file
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        
        # Reinitialize
        db_manager = DatabaseManager()
        return True
    except Exception as e:
        print(f"Error resetting database: {str(e)}")
        return False

def get_student_attendance_history(student_id):
    """Get attendance history for a student"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM attendance
                WHERE student_id = ?
                ORDER BY attendance_date DESC
            ''', (student_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error getting student history: {str(e)}")
        return []

# Create a function to test database connection
def test_database_connection():
    """Test if database is accessible"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1')
            return True
    except Exception as e:
        print(f"Database connection test failed: {str(e)}")
        return False

# Run test on import
if __name__ != "__main__":
    # Test database connection when imported
    if not test_database_connection():
        print("Warning: Database connection failed. Check permissions and path.")