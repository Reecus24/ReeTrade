from cryptography.fernet import Fernet
import os
import base64

class CryptoManager:
    """Handle encryption/decryption of sensitive data"""
    
    def __init__(self):
        encryption_key = os.environ.get('ENCRYPTION_KEY', '')
        
        # Generate key if not exists
        if not encryption_key or encryption_key == 'generate-with-fernet-key-generation':
            encryption_key = Fernet.generate_key().decode()
            print(f"⚠️  ENCRYPTION_KEY not set! Generated new key: {encryption_key}")
            print("   Add this to your .env file: ENCRYPTION_KEY={}".format(encryption_key))
        
        self.cipher = Fernet(encryption_key.encode())
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext to encrypted string"""
        if not plaintext:
            return ""
        encrypted_bytes = self.cipher.encrypt(plaintext.encode())
        return base64.b64encode(encrypted_bytes).decode()
    
    def decrypt(self, encrypted: str) -> str:
        """Decrypt encrypted string to plaintext"""
        if not encrypted:
            return ""
        encrypted_bytes = base64.b64decode(encrypted.encode())
        decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
        return decrypted_bytes.decode()

# Global instance
crypto_manager = CryptoManager()
