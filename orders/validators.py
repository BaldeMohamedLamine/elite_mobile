"""
Validateurs personnalisés pour les formulaires et modèles
"""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


def validate_phone_number(value):
    """
    Valide un numéro de téléphone guinéen
    Format accepté: +224XXXXXXXX ou 6XXXXXXXX
    """
    if not value:
        return
    
    # Nettoyer le numéro
    phone = re.sub(r'[^\d+]', '', str(value))
    
    # Vérifier les formats acceptés
    if phone.startswith('+224'):
        if len(phone) != 13:  # +224 + 9 chiffres
            raise ValidationError(_('Numéro de téléphone invalide. Format: +224XXXXXXXX'))
    elif phone.startswith('6'):
        if len(phone) != 9:  # 6 + 8 chiffres
            raise ValidationError(_('Numéro de téléphone invalide. Format: 6XXXXXXXX'))
    else:
        raise ValidationError(_('Numéro de téléphone invalide. Commencez par +224 ou 6'))


def validate_card_number(value):
    """
    Valide un numéro de carte bancaire
    """
    if not value:
        return
    
    # Nettoyer le numéro
    card_number = re.sub(r'[^\d]', '', str(value))
    
    # Vérifier la longueur (13-19 chiffres)
    if len(card_number) < 13 or len(card_number) > 19:
        raise ValidationError(_('Numéro de carte invalide'))
    
    # Algorithme de Luhn pour vérifier la validité
    def luhn_check(card_num):
        def digits_of(n):
            return [int(d) for d in str(n)]
        
        digits = digits_of(card_num)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10 == 0
    
    if not luhn_check(card_number):
        raise ValidationError(_('Numéro de carte invalide'))


def validate_positive_decimal(value):
    """
    Valide qu'une valeur décimale est positive
    """
    if value is not None and value <= 0:
        raise ValidationError(_('La valeur doit être positive'))


def validate_quantity(value):
    """
    Valide une quantité (entier positif)
    """
    if not isinstance(value, int) or value <= 0:
        raise ValidationError(_('La quantité doit être un entier positif'))


def validate_email_domain(value):
    """
    Valide le domaine d'un email (optionnel - pour bloquer certains domaines)
    """
    if not value:
        return
    
    # Domaines bloqués (exemple)
    blocked_domains = ['tempmail.com', '10minutemail.com']
    
    domain = value.split('@')[-1].lower()
    if domain in blocked_domains:
        raise ValidationError(_('Ce domaine email n\'est pas autorisé'))


def validate_password_strength(value):
    """
    Valide la force d'un mot de passe
    """
    if not value:
        return
    
    if len(value) < 8:
        raise ValidationError(_('Le mot de passe doit contenir au moins 8 caractères'))
    
    if not re.search(r'[A-Z]', value):
        raise ValidationError(_('Le mot de passe doit contenir au moins une majuscule'))
    
    if not re.search(r'[a-z]', value):
        raise ValidationError(_('Le mot de passe doit contenir au moins une minuscule'))
    
    if not re.search(r'\d', value):
        raise ValidationError(_('Le mot de passe doit contenir au moins un chiffre'))
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
        raise ValidationError(_('Le mot de passe doit contenir au moins un caractère spécial'))


def validate_guinean_address(value):
    """
    Valide une adresse guinéenne (basique)
    """
    if not value:
        return
    
    # Mots-clés typiques d'adresses guinéennes
    guinean_keywords = [
        'conakry', 'kindia', 'kankan', 'nzérékoré', 'labé', 'mamou', 'boké', 'faranah',
        'commune', 'quartier', 'rue', 'avenue', 'boulevard', 'cité', 'zone'
    ]
    
    value_lower = value.lower()
    if not any(keyword in value_lower for keyword in guinean_keywords):
        # Avertissement mais pas d'erreur bloquante
        pass  # On peut ajouter un warning ici si nécessaire