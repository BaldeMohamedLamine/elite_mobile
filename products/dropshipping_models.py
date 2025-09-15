"""
Modèles pour le système de dropshipping et gestion des fournisseurs
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, EmailValidator
from django.contrib.auth import get_user_model
from decimal import Decimal

User = get_user_model()


class Supplier(models.Model):
    """Modèle pour les fournisseurs/dropshippers"""
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('suspended', 'Suspendu'),
        ('pending', 'En attente'),
    ]
    
    PAYMENT_TERMS_CHOICES = [
        ('net_15', 'Net 15 jours'),
        ('net_30', 'Net 30 jours'),
        ('net_45', 'Net 45 jours'),
        ('net_60', 'Net 60 jours'),
        ('prepaid', 'Prépayé'),
        ('cod', 'Paiement à la livraison'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    name = models.CharField(max_length=200, help_text="Nom du fournisseur")
    company_name = models.CharField(max_length=200, blank=True, help_text="Nom de l'entreprise")
    contact_person = models.CharField(max_length=100, blank=True, help_text="Personne de contact")
    
    # Informations de contact
    email = models.EmailField(validators=[EmailValidator()], help_text="Email principal")
    phone = models.CharField(max_length=20, blank=True, help_text="Téléphone principal")
    website = models.URLField(blank=True, help_text="Site web")
    
    # Adresse
    address_line1 = models.CharField(max_length=200, blank=True)
    address_line2 = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default="Guinée")
    
    # Informations commerciales
    tax_id = models.CharField(max_length=50, blank=True, help_text="Numéro de TVA/Impôt")
    business_license = models.CharField(max_length=100, blank=True, help_text="Numéro de licence")
    
    # Conditions commerciales
    payment_terms = models.CharField(max_length=20, choices=PAYMENT_TERMS_CHOICES, default='net_30')
    credit_limit = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0,
        help_text="Limite de crédit en GNF"
    )
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        help_text="Remise standard en %"
    )
    
    # Statut et métadonnées
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_verified = models.BooleanField(default=False, help_text="Fournisseur vérifié")
    notes = models.TextField(blank=True, help_text="Notes internes")
    
    # Dates
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_suppliers'
    )
    
    def __str__(self):
        return f"{self.name} ({self.company_name})" if self.company_name else self.name
    
    @property
    def full_address(self):
        """Adresse complète formatée"""
        parts = [self.address_line1, self.address_line2, self.city, self.state_province, self.postal_code, self.country]
        return ', '.join(filter(None, parts))
    
    @property
    def total_products(self):
        """Nombre total de produits de ce fournisseur"""
        return self.dropship_products.count()
    
    @property
    def active_products(self):
        """Nombre de produits actifs de ce fournisseur"""
        return self.dropship_products.filter(is_active=True).count()
    
    @property
    def total_sales_value(self):
        """Valeur totale des ventes de ce fournisseur"""
        from django.db.models import Sum, F
        return self.supplier_sales.aggregate(
            total=Sum(F('quantity') * F('supplier_price'))
        )['total'] or Decimal('0')
    
    @property
    def total_commission_earned(self):
        """Commission totale gagnée sur ce fournisseur"""
        from django.db.models import Sum, F
        return self.supplier_sales.aggregate(
            total=Sum(F('quantity') * (F('selling_price') - F('supplier_price')))
        )['total'] or Decimal('0')
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['status', 'is_verified']),
            models.Index(fields=['name']),
            models.Index(fields=['email']),
        ]


class DropshipProduct(models.Model):
    """Produits fournis par un fournisseur (dropshipping)"""
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='dropship_products')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='dropship_suppliers')
    
    # Prix et conditions
    supplier_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Prix d'achat au fournisseur"
    )
    selling_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Prix de vente au client"
    )
    margin_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Marge en pourcentage"
    )
    
    # Stock virtuel
    virtual_stock = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Stock virtuel (disponible chez le fournisseur)"
    )
    min_order_quantity = models.IntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Quantité minimum de commande"
    )
    max_order_quantity = models.IntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Quantité maximum de commande"
    )
    
    # Informations de livraison
    estimated_delivery_days = models.IntegerField(
        default=7,
        validators=[MinValueValidator(1)],
        help_text="Délai de livraison estimé en jours"
    )
    shipping_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Coût de livraison"
    )
    
    # Statut
    is_active = models.BooleanField(default=True, help_text="Produit actif pour la vente")
    is_featured = models.BooleanField(default=False, help_text="Produit mis en avant")
    auto_reorder = models.BooleanField(default=False, help_text="Réapprovisionnement automatique")
    reorder_threshold = models.IntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Seuil de réapprovisionnement"
    )
    
    # Métadonnées
    supplier_sku = models.CharField(max_length=100, blank=True, help_text="SKU du fournisseur")
    supplier_url = models.URLField(blank=True, help_text="URL du produit chez le fournisseur")
    notes = models.TextField(blank=True, help_text="Notes sur ce produit")
    
    # Dates
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_sync_at = models.DateTimeField(null=True, blank=True, help_text="Dernière synchronisation avec le fournisseur")
    
    def __str__(self):
        return f"{self.product.name} - {self.supplier.name}"
    
    @property
    def margin_amount(self):
        """Marge en montant"""
        return self.selling_price - self.supplier_price
    
    @property
    def is_low_stock(self):
        """Vérifie si le stock virtuel est faible"""
        return self.virtual_stock <= self.reorder_threshold
    
    @property
    def is_out_of_stock(self):
        """Vérifie si le produit est en rupture"""
        return self.virtual_stock <= 0
    
    @property
    def stock_status(self):
        """Statut du stock"""
        if self.is_out_of_stock:
            return "Rupture"
        elif self.is_low_stock:
            return "Stock faible"
        else:
            return "Disponible"
    
    def calculate_margin_percentage(self):
        """Calcule le pourcentage de marge"""
        if self.supplier_price > 0:
            return ((self.selling_price - self.supplier_price) / self.supplier_price) * 100
        return 0
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement la marge
        self.margin_percentage = self.calculate_margin_percentage()
        super().save(*args, **kwargs)
    
    class Meta:
        unique_together = ['supplier', 'product']
        indexes = [
            models.Index(fields=['supplier', 'is_active']),
            models.Index(fields=['product', 'is_active']),
            models.Index(fields=['virtual_stock']),
            models.Index(fields=['margin_percentage']),
        ]


class SupplierSale(models.Model):
    """Ventes de produits fournisseur"""
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
        ('refunded', 'Remboursée'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplier_sales')
    dropship_product = models.ForeignKey(DropshipProduct, on_delete=models.CASCADE, related_name='sales')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='supplier_sales')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='supplier_sales')
    
    # Quantités et prix
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    supplier_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    commission_earned = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Statut
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Informations de livraison
    tracking_number = models.CharField(max_length=100, blank=True)
    estimated_delivery_date = models.DateTimeField(null=True, blank=True)
    actual_delivery_date = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    notes = models.TextField(blank=True)
    
    # Dates
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Vente {self.dropship_product.product.name} - {self.supplier.name} - {self.quantity} unités"
    
    @property
    def total_supplier_amount(self):
        """Montant total à payer au fournisseur"""
        return self.quantity * self.supplier_price
    
    @property
    def total_selling_amount(self):
        """Montant total de la vente"""
        return self.quantity * self.selling_price
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['supplier', 'status']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['created_at']),
        ]


class SupplierInvoice(models.Model):
    """Factures fournisseur"""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('sent', 'Envoyée'),
        ('paid', 'Payée'),
        ('overdue', 'En retard'),
        ('cancelled', 'Annulée'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True, help_text="Numéro de facture")
    
    # Montants
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dates
    invoice_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateTimeField()
    paid_date = models.DateTimeField(null=True, blank=True)
    
    # Statut
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # Métadonnées
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Dates système
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Facture {self.invoice_number} - {self.supplier.name}"
    
    @property
    def is_overdue(self):
        """Vérifie si la facture est en retard"""
        return self.status not in ['paid', 'cancelled'] and timezone.now() > self.due_date
    
    @property
    def remaining_amount(self):
        """Montant restant à payer"""
        return self.total_amount - self.paid_amount
    
    class Meta:
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['supplier', 'status']),
            models.Index(fields=['invoice_date']),
            models.Index(fields=['due_date']),
        ]


class SupplierInvoiceItem(models.Model):
    """Articles des factures fournisseur"""
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.CASCADE, related_name='items')
    supplier_sale = models.ForeignKey(SupplierSale, on_delete=models.CASCADE, related_name='invoice_items')
    
    # Détails
    description = models.CharField(max_length=200)
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.description} - {self.quantity} x {self.unit_price}"
    
    def save(self, *args, **kwargs):
        # Calculer automatiquement le prix total
        self.total_price = self.quantity * self.unit_price
        super().save(*args, **kwargs)
    
    class Meta:
        unique_together = ['invoice', 'supplier_sale']
