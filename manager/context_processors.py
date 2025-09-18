from .models import CompanySettings


def company_settings(request):
    """Context processor pour rendre les paramètres de l'entreprise disponibles dans tous les templates"""
    try:
        settings = CompanySettings.get_settings()
        return {
            'company_settings': settings,
            'company_name': settings.company_name,
            'company_description': settings.company_description,
            'company_logo': settings.logo,
            'company_address': settings.address,
            'company_phone': settings.phone,
            'company_email': settings.email,
            'company_website': settings.website,
            'company_tax_number': settings.tax_number,
            'company_registration_number': settings.registration_number,
        }
    except Exception:
        # En cas d'erreur, retourner des valeurs par défaut
        return {
            'company_settings': None,
            'company_name': 'Mon Entreprise',
            'company_description': '',
            'company_logo': None,
            'company_address': '',
            'company_phone': '',
            'company_email': '',
            'company_website': '',
            'company_tax_number': '',
            'company_registration_number': '',
        }
