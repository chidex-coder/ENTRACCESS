"""Email Service Module"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
import os
from pathlib import Path

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class EmailService:
    def __init__(self):
        # Email configuration - can be set via environment variables or directly
        self.smtp_host = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('EMAIL_PORT', 587))
        self.smtp_user = os.getenv('EMAIL_USER', '')
        self.smtp_password = os.getenv('EMAIL_PASSWORD', '')
        self.use_tls = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
        
        # Check if email is configured
        self.is_configured = bool(self.smtp_user and self.smtp_password)
        
        if not self.is_configured:
            print("Warning: Email not configured. Please set EMAIL_USER and EMAIL_PASSWORD in .env file")
    
    def send_email(self, to_email, subject, html_body, attachments=None):
        """Generic email sending function"""
        if not self.is_configured:
            print(f"Email not configured. Would have sent to {to_email}: {subject}")
            return False, "Email service not configured"
        
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Attach HTML body
            msg.attach(MIMEText(html_body, 'html'))
            
            # Attach files if any
            if attachments:
                for attachment in attachments:
                    if attachment['data'] and attachment['name']:
                        img = MIMEImage(attachment['data'], name=attachment['name'])
                        img.add_header('Content-Disposition', 'attachment', filename=attachment['name'])
                        msg.attach(img)
            
            # Send email
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            if self.use_tls:
                server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            print(f"Email sent successfully to {to_email}")
            return True, "Email sent successfully"
            
        except smtplib.SMTPAuthenticationError:
            error_msg = "Authentication failed. Check your email credentials."
            print(f"Email error: {error_msg}")
            return False, error_msg
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            print(f"Email error: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            print(f"Email error: {error_msg}")
            return False, error_msg
    
    def send_registration_confirmation(self, email, name, student_id, qr_bytes):
        """Send registration confirmation email with QR code"""
        subject = f"🎓 Welcome {name}! Your Attendance QR Code"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; padding: 30px; text-align: center; border-radius: 10px; }}
                .content {{ padding: 20px; }}
                .details {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; color: #666; font-size: 12px; }}
                .badge {{ display: inline-block; background: #4CAF50; color: white; 
                         padding: 5px 10px; border-radius: 5px; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎓 Welcome to Attendance System!</h1>
                </div>
                
                <div class="content">
                    <h2>Hello {name}!</h2>
                    <p>Your registration has been successful. Here are your details:</p>
                    
                    <div class="details">
                        <p><strong>📋 Student ID:</strong> #{student_id}</p>
                        <p><strong>📅 Registration Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><strong>📧 Email:</strong> {email}</p>
                    </div>
                    
                    <p><strong>Your QR code is attached to this email.</strong></p>
                    <p>📱 <strong>How to use:</strong></p>
                    <ul>
                        <li>Save the QR code on your phone</li>
                        <li>Present it at the scanner during attendance hours</li>
                        <li>You'll receive email confirmations for each check-in/out</li>
                    </ul>
                    
                    <div class="badge">
                        ⚠️ Important: Do not share your QR code with others
                    </div>
                </div>
                
                <div class="footer">
                    <p>This is an automated message. Please do not reply to this email.</p>
                    <p>&copy; 2024 Student Attendance System</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        attachments = [{'data': qr_bytes, 'name': f'QR_Code_{student_id}.png'}]
        
        return self.send_email(email, subject, html_body, attachments)
    
    def send_check_in_confirmation(self, email, name, timestamp):
        """Send check-in confirmation email"""
        subject = f"✅ Check-in Confirmation - {name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                          color: white; padding: 30px; text-align: center; border-radius: 10px; }}
                .content {{ padding: 20px; }}
                .details {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Check-in Confirmation</h1>
                </div>
                
                <div class="content">
                    <h2>Hello {name}!</h2>
                    <p>Your check-in has been recorded successfully.</p>
                    
                    <div class="details">
                        <p><strong>⏰ Time:</strong> {timestamp.strftime('%I:%M %p')}</p>
                        <p><strong>📅 Date:</strong> {timestamp.strftime('%B %d, %Y')}</p>
                        <p><strong>✅ Status:</strong> Successfully checked in</p>
                    </div>
                    
                    <p>Thank you for using the attendance system!</p>
                </div>
                
                <div class="footer">
                    <p>This is an automated message. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return self.send_email(email, subject, html_body)
    
    def send_check_out_confirmation(self, email, name, check_in_time, check_out_time, duration):
        """Send check-out confirmation email"""
        subject = f"✅ Check-out Confirmation - {name}"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); 
                          color: white; padding: 30px; text-align: center; border-radius: 10px; }}
                .content {{ padding: 20px; }}
                .details {{ background: #f5f5f5; padding: 15px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Check-out Confirmation</h1>
                </div>
                
                <div class="content">
                    <h2>Hello {name}!</h2>
                    <p>Your check-out has been recorded successfully.</p>
                    
                    <div class="details">
                        <p><strong>⏰ Check-in Time:</strong> {check_in_time.strftime('%I:%M %p')}</p>
                        <p><strong>⏰ Check-out Time:</strong> {check_out_time.strftime('%I:%M %p')}</p>
                        <p><strong>📊 Duration:</strong> {duration}</p>
                        <p><strong>📅 Date:</strong> {check_out_time.strftime('%B %d, %Y')}</p>
                    </div>
                    
                    <p>Thank you for using the attendance system!</p>
                </div>
                
                <div class="footer">
                    <p>This is an automated message. Please do not reply.</p>
                </div>
            </div>
        </html>
        """
        
        return self.send_email(email, subject, html_body)

# Global instance
email_service = EmailService()