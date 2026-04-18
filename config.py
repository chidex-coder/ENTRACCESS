
## **Updated config.py**


# config.py
from datetime import time

# Attendance windows - Configure these times
# Check-in window (evening/night)
CHECK_IN_START = time(19, 0)   # 7:00 PM
CHECK_IN_END = time(23, 59)    # 11:59 PM

# Check-out window (afternoon/evening)
CHECK_OUT_START = time(13, 0)  # 1:00 PM
CHECK_OUT_END = time(18, 59)   # 6:59 PM

# Email configuration
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USER = os.getenv('EMAIL_USER')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
