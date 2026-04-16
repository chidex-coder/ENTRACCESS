"""QR Code Generator Module"""
import qrcode
from PIL import Image
import io

class QRGenerator:
    def __init__(self):
        pass
    
    def generate(self, data, name=None, student_id=None):
        """Generate QR code from data"""
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
        
        # Add label if name provided
        if name:
            # You can add text overlay if needed
            pass
        
        return qr_img
    
    def to_bytes(self, qr_img):
        """Convert PIL image to bytes"""
        img_bytes = io.BytesIO()
        qr_img.save(img_bytes, format='PNG')
        return img_bytes.getvalue()

# Global instance
qr_generator = QRGenerator()