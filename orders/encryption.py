from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os
from django.core.exceptions import ImproperlyConfigured


class DataEncryption:
    """Classe pour chiffrer et déchiffrer les données sensibles"""
    
    def __init__(self):
        self.key = self._get_encryption_key()
        self.cipher = Fernet(self.key)
    
    def _get_encryption_key(self):
        """Récupère ou génère la clé de chiffrement"""
        key = getattr(settings, 'ENCRYPTION_KEY', None)
        
        if not key:
            # En production, la clé doit être définie
            if not settings.DEBUG:
                raise ImproperlyConfigured(
                    "ENCRYPTION_KEY must be set in production. "
                    "Add it to your environment variables."
                )
            
            # Générer une nouvelle clé seulement en développement
            key = Fernet.generate_key()
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"ATTENTION: Nouvelle clé de chiffrement générée: {key.decode()}")
            logger.warning("Ajoutez cette clé à vos variables d'environnement: ENCRYPTION_KEY")
        
        if isinstance(key, str):
            key = key.encode()
        
        return key
    
    def encrypt(self, data):
        """Chiffre une donnée"""
        if data is None:
            return None
        
        if isinstance(data, str):
            data = data.encode()
        
        try:
            encrypted_data = self.cipher.encrypt(data)
            return base64.b64encode(encrypted_data).decode()
        except Exception as e:
            raise ValueError(f"Erreur lors du chiffrement: {e}")
    
    def decrypt(self, encrypted_data):
        """Déchiffre une donnée"""
        if encrypted_data is None:
            return None
        
        try:
            # Décoder depuis base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode())
            # Déchiffrer
            decrypted_data = self.cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            raise ValueError(f"Erreur lors du déchiffrement: {e}")


# Instance globale
encryption = DataEncryption()


def encrypt_field(value):
    """Fonction utilitaire pour chiffrer un champ"""
    if value:
        return encryption.encrypt(value)
    return value


def decrypt_field(value):
    """Fonction utilitaire pour déchiffrer un champ"""
    if value:
        try:
            return encryption.decrypt(value)
        except (ValueError, TypeError) as e:
            # Si le déchiffrement échoue, logger l'erreur et retourner la valeur originale
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to decrypt field value: {e}")
            # En production, on pourrait vouloir lever une exception
            if not settings.DEBUG:
                logger.error("Decryption failed in production - this may indicate data corruption")
            return value
    return value


class EncryptedField:
    """Classe pour créer des champs chiffrés personnalisés"""
    
    def __init__(self, max_length=255):
        self.max_length = max_length
    
    def encrypt_value(self, value):
        """Chiffre une valeur"""
        return encrypt_field(value)
    
    def decrypt_value(self, value):
        """Déchiffre une valeur"""
        return decrypt_field(value)


def mask_sensitive_data(data, mask_char='*', visible_chars=4):
    """Masque les données sensibles pour l'affichage"""
    if not data or len(data) <= visible_chars:
        return data
    
    return data[:visible_chars] + mask_char * (len(data) - visible_chars)


def mask_phone_number(phone):
    """Masque un numéro de téléphone"""
    if not phone:
        return phone
    
    # Format: +224 6XX XXX XXX -> +224 6XX *** ***
    if phone.startswith('+224'):
        return phone[:8] + '*** ***'
    elif len(phone) >= 9:
        return phone[:3] + '*** ***'
    
    return phone


def mask_card_number(card_number):
    """Masque un numéro de carte"""
    if not card_number:
        return card_number
    
    # Supprimer les espaces
    clean_number = card_number.replace(' ', '')
    
    if len(clean_number) >= 8:
        return '**** **** **** ' + clean_number[-4:]
    
    return '****'


def mask_email(email):
    """Masque un email"""
    if not email or '@' not in email:
        return email
    
    local, domain = email.split('@', 1)
    
    if len(local) <= 2:
        masked_local = local[0] + '*'
    else:
        masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
    
    return f"{masked_local}@{domain}"
