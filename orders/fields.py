from django.db import models
from django.core.exceptions import ValidationError
from .encryption import encrypt_field, decrypt_field, mask_phone_number, mask_card_number, mask_email


class EncryptedCharField(models.CharField):
    """Champ de caractères chiffré"""
    
    def __init__(self, *args, **kwargs):
        # Augmenter la taille pour accommoder les données chiffrées
        if 'max_length' in kwargs:
            kwargs['max_length'] = kwargs['max_length'] * 4  # Les données chiffrées sont plus longues
        super().__init__(*args, **kwargs)
    
    def from_db_value(self, value, expression, connection):
        """Déchiffre la valeur lors de la lecture depuis la base de données"""
        if value is None:
            return value
        return decrypt_field(value)
    
    def to_python(self, value):
        """Convertit la valeur en Python"""
        if value is None:
            return value
        return decrypt_field(value)
    
    def get_prep_value(self, value):
        """Prépare la valeur pour l'insertion en base de données"""
        if value is None:
            return value
        return encrypt_field(value)


class EncryptedTextField(models.TextField):
    """Champ de texte chiffré"""
    
    def from_db_value(self, value, expression, connection):
        """Déchiffre la valeur lors de la lecture depuis la base de données"""
        if value is None:
            return value
        return decrypt_field(value)
    
    def to_python(self, value):
        """Convertit la valeur en Python"""
        if value is None:
            return value
        return decrypt_field(value)
    
    def get_prep_value(self, value):
        """Prépare la valeur pour l'insertion en base de données"""
        if value is None:
            return value
        return encrypt_field(value)


class EncryptedPhoneField(EncryptedCharField):
    """Champ de téléphone chiffré avec masquage"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        super().__init__(*args, **kwargs)
    
    def value_to_string(self, obj):
        """Retourne la valeur masquée pour l'affichage"""
        value = self.value_from_object(obj)
        return mask_phone_number(value) if value else value


class EncryptedCardField(EncryptedCharField):
    """Champ de carte bancaire chiffré avec masquage"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 19)
        super().__init__(*args, **kwargs)
    
    def value_to_string(self, obj):
        """Retourne la valeur masquée pour l'affichage"""
        value = self.value_from_object(obj)
        return mask_card_number(value) if value else value


class EncryptedEmailField(EncryptedCharField):
    """Champ d'email chiffré avec masquage"""
    
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 254)
        super().__init__(*args, **kwargs)
    
    def value_to_string(self, obj):
        """Retourne la valeur masquée pour l'affichage"""
        value = self.value_from_object(obj)
        return mask_email(value) if value else value


class EncryptedDecimalField(models.DecimalField):
    """Champ décimal chiffré"""
    
    def from_db_value(self, value, expression, connection):
        """Déchiffre la valeur lors de la lecture depuis la base de données"""
        if value is None:
            return value
        try:
            return float(decrypt_field(str(value)))
        except (ValueError, TypeError):
            return value
    
    def to_python(self, value):
        """Convertit la valeur en Python"""
        if value is None:
            return value
        try:
            return float(decrypt_field(str(value)))
        except (ValueError, TypeError):
            return value
    
    def get_prep_value(self, value):
        """Prépare la valeur pour l'insertion en base de données"""
        if value is None:
            return value
        return encrypt_field(str(value))
