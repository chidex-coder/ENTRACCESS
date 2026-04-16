# config.py
from datetime import time

# Attendance windows - MODIFY THESE TIMES
CHECK_IN_START = time(23, 15)   # 7:00 PM (change hour, minute)
CHECK_IN_END = time(23, 55)    # 11:59 PM
CHECK_OUT_START = time(23, 56)  # 1:00 PM (change hour, minute)
CHECK_OUT_END = time(23, 59)   # 6:59 PM

# Email configuration
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'