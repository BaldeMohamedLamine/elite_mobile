import random
import string
import time
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class TwoFactorAuth:
    """
    Classe pour gérer l'authentification à deux facteurs
    """
    
    def __init__(self):
        self.code_length = 6
        self.code_expiry = 300  # 5 minutes
        self.max_attempts = 3
        self.lockout_duration = 900  # 15 minutes
    
    def generate_code(self):
        """Génère un code de vérification aléatoire"""
        return ''.join(random.choices(string.digits, k=self.code_length))
    
    def send_email_code(self, user, code):
        """Envoie le code de vérification par email"""
        try:
            subject = 'Code de vérification - Authentification à deux facteurs'
            message = f"""
            Bonjour {user.first_name},
            
            Votre code de vérification pour l'authentification à deux facteurs est : {code}
            
            Ce code est valide pendant 5 minutes.
            
            Si vous n'avez pas demandé ce code, ignorez cet email.
            
            Cordialement,
            L'équipe de votre boutique en ligne
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du code 2FA par email: {e}")
            return False
    
    def send_sms_code(self, phone_number, code):
        """
        Envoie le code de vérification par SMS
        Note: Cette méthode nécessite l'intégration d'un service SMS
        """
        try:
            # Ici, vous intégreriez un service SMS comme Twilio, Orange SMS API, etc.
            # Pour l'instant, on simule l'envoi
            logger.info(f"Code SMS envoyé à {phone_number}: {code}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du code 2FA par SMS: {e}")
            return False
    
    def store_code(self, user, code, method='email'):
        """Stocke le code de vérification dans le cache"""
        cache_key = f"2fa_code_{user.id}_{method}"
        cache_data = {
            'code': code,
            'created_at': time.time(),
            'attempts': 0,
            'method': method
        }
        cache.set(cache_key, cache_data, self.code_expiry)
        return cache_key
    
    def verify_code(self, user, code, method='email'):
        """Vérifie le code de vérification"""
        cache_key = f"2fa_code_{user.id}_{method}"
        cache_data = cache.get(cache_key)
        
        if not cache_data:
            return False, "Code expiré ou invalide"
        
        # Vérifier le nombre de tentatives
        if cache_data['attempts'] >= self.max_attempts:
            return False, "Trop de tentatives. Veuillez demander un nouveau code."
        
        # Vérifier le code
        if cache_data['code'] == code:
            # Code correct, supprimer du cache
            cache.delete(cache_key)
            return True, "Code vérifié avec succès"
        else:
            # Code incorrect, incrémenter les tentatives
            cache_data['attempts'] += 1
            cache.set(cache_key, cache_data, self.code_expiry)
            remaining_attempts = self.max_attempts - cache_data['attempts']
            return False, f"Code incorrect. {remaining_attempts} tentative(s) restante(s)."
    
    def is_code_valid(self, user, method='email'):
        """Vérifie si un code est valide pour l'utilisateur"""
        cache_key = f"2fa_code_{user.id}_{method}"
        cache_data = cache.get(cache_key)
        return cache_data is not None
    
    def clear_code(self, user, method='email'):
        """Supprime le code de vérification du cache"""
        cache_key = f"2fa_code_{user.id}_{method}"
        cache.delete(cache_key)
    
    def is_user_locked(self, user):
        """Vérifie si l'utilisateur est verrouillé pour 2FA"""
        lockout_key = f"2fa_lockout_{user.id}"
        return cache.get(lockout_key) is not None
    
    def lock_user(self, user):
        """Verrouille l'utilisateur pour 2FA"""
        lockout_key = f"2fa_lockout_{user.id}"
        cache.set(lockout_key, True, self.lockout_duration)
    
    def unlock_user(self, user):
        """Déverrouille l'utilisateur pour 2FA"""
        lockout_key = f"2fa_lockout_{user.id}"
        cache.delete(lockout_key)
    
    def get_remaining_time(self, user, method='email'):
        """Récupère le temps restant avant expiration du code"""
        cache_key = f"2fa_code_{user.id}_{method}"
        cache_data = cache.get(cache_key)
        
        if not cache_data:
            return 0
        
        elapsed_time = time.time() - cache_data['created_at']
        remaining_time = self.code_expiry - elapsed_time
        return max(0, int(remaining_time))


class TwoFactorBackupCodes:
    """
    Classe pour gérer les codes de sauvegarde 2FA
    """
    
    def __init__(self):
        self.code_length = 8
        self.num_codes = 10
    
    def generate_backup_codes(self):
        """Génère des codes de sauvegarde"""
        codes = []
        for _ in range(self.num_codes):
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=self.code_length))
            codes.append(code)
        return codes
    
    def store_backup_codes(self, user, codes):
        """Stocke les codes de sauvegarde (chiffrés)"""
        # Dans un vrai projet, vous chiffreriez ces codes avant de les stocker
        cache_key = f"2fa_backup_codes_{user.id}"
        cache.set(cache_key, codes, 86400 * 30)  # 30 jours
        return cache_key
    
    def verify_backup_code(self, user, code):
        """Vérifie un code de sauvegarde"""
        cache_key = f"2fa_backup_codes_{user.id}"
        backup_codes = cache.get(cache_key, [])
        
        if code.upper() in backup_codes:
            # Supprimer le code utilisé
            backup_codes.remove(code.upper())
            cache.set(cache_key, backup_codes, 86400 * 30)
            return True, "Code de sauvegarde valide"
        
        return False, "Code de sauvegarde invalide"
    
    def get_remaining_backup_codes(self, user):
        """Récupère le nombre de codes de sauvegarde restants"""
        cache_key = f"2fa_backup_codes_{user.id}"
        backup_codes = cache.get(cache_key, [])
        return len(backup_codes)
