from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone


class CompanySettings(models.Model):
    """Paramètres de l'entreprise"""
    
    # Informations de base
    company_name = models.CharField(
        max_length=200,
        verbose_name="Nom de l'entreprise",
        default="Mon Entreprise"
    )
    
    company_description = models.TextField(
        verbose_name="Description de l'entreprise",
        blank=True,
        help_text="Description courte de votre entreprise"
    )
    
    # Logo
    logo = models.ImageField(
        upload_to='company/logos/',
        verbose_name="Logo de l'entreprise",
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'svg', 'webp'])],
        help_text="Format recommandé: PNG ou SVG, taille optimale: 200x80px"
    )
    
    # Informations de contact
    address = models.TextField(
        verbose_name="Adresse complète",
        blank=True,
        help_text="Adresse complète de l'entreprise"
    )
    
    phone = models.CharField(
        max_length=20,
        verbose_name="Téléphone",
        blank=True
    )
    
    email = models.EmailField(
        verbose_name="Email",
        blank=True
    )
    
    website = models.URLField(
        verbose_name="Site web",
        blank=True
    )
    
    # Informations légales
    tax_number = models.CharField(
        max_length=50,
        verbose_name="Numéro de TVA/RC",
        blank=True,
        help_text="Numéro de TVA ou Registre de Commerce"
    )
    
    registration_number = models.CharField(
        max_length=50,
        verbose_name="Numéro d'enregistrement",
        blank=True
    )
    
    # Paramètres d'affichage
    show_logo_on_invoices = models.BooleanField(
        default=True,
        verbose_name="Afficher le logo sur les factures"
    )
    
    show_logo_on_receipts = models.BooleanField(
        default=True,
        verbose_name="Afficher le logo sur les reçus"
    )
    
    show_logo_on_reports = models.BooleanField(
        default=True,
        verbose_name="Afficher le logo sur les rapports"
    )
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Paramètres de l'entreprise"
        verbose_name_plural = "Paramètres de l'entreprise"
    
    def __str__(self):
        return f"Paramètres - {self.company_name}"
    
    def save(self, *args, **kwargs):
        # S'assurer qu'il n'y a qu'une seule instance
        if not self.pk and CompanySettings.objects.exists():
            # Si c'est une nouvelle instance et qu'il en existe déjà une, ne pas créer
            return
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Récupère les paramètres de l'entreprise (singleton)"""
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'company_name': 'Mon Entreprise',
                'company_description': 'Votre description d\'entreprise ici'
            }
        )
        return settings