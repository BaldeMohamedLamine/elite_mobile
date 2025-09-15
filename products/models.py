import uuid
from django.db import models
from django.utils import timezone


class Category(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, unique=True, null=True)
    name = models.CharField(
        max_length=100,
        verbose_name='Nom de la catégorie',
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, unique=True, null=True)
    name = models.CharField(
        max_length=200,
        verbose_name='Nom du produit'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Description du produit'
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Prix du produit'
    )
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Prix d\'achat'
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name='Catégorie'
    )
    image = models.ImageField(
        upload_to='products/',
        null=True,
        blank=True,
        verbose_name='Image du produit'
    )
    
    # Codes et identification
    sku = models.CharField(
        max_length=100,
        unique=True,
        default='',
        verbose_name='Code SKU'
    )
    barcode = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Code-barres'
    )
    
    # Informations physiques
    weight = models.DecimalField(
        max_digits=8,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name='Poids (kg)'
    )
    dimensions = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Dimensions (L x l x H)'
    )
    
    # Statut
    is_active = models.BooleanField(
        default=True,
        verbose_name='Produit actif'
    )
    
    # Le stock est maintenant géré séparément via le modèle Stock
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


# Import des modèles de dropshipping
from .dropshipping_models import Supplier, DropshipProduct, SupplierSale, SupplierInvoice, SupplierInvoiceItem


class Stock(models.Model):
    """Modèle pour gérer le stock des produits"""
    STATUS_CHOICES = [
        ('available', 'Disponible'),
        ('low_stock', 'Stock faible'),
        ('out_of_stock', 'Rupture de stock'),
        ('discontinued', 'Discontinué'),
    ]
    
    MOVEMENT_TYPES = [
        ('in', 'Entrée'),
        ('out', 'Sortie'),
        ('adjustment', 'Ajustement'),
        ('transfer', 'Transfert'),
        ('return', 'Retour'),
    ]
    
    product = models.OneToOneField(
        Product, 
        on_delete=models.CASCADE, 
        related_name='stock',
        verbose_name='Produit'
    )
    
    # Quantités
    current_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Quantité actuelle'
    )
    reserved_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Quantité réservée'
    )
    available_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name='Quantité disponible'
    )
    
    # Seuils
    min_quantity = models.PositiveIntegerField(
        default=5,
        verbose_name='Quantité minimum' 
    )
    max_quantity = models.PositiveIntegerField(
        default=1000,
        verbose_name='Quantité maximum'
    )
    reorder_quantity = models.PositiveIntegerField(
        default=10,
        verbose_name='Quantité de réapprovisionnement'
    )
    
    # Statut et métadonnées
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='out_of_stock',
        verbose_name='Statut du stock'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Stock actif'
    )
    auto_reorder = models.BooleanField(
        default=False,
        verbose_name='Réapprovisionnement automatique'
    )
    
    # Dates
    last_updated = models.DateTimeField(auto_now=True)
    last_movement = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Stock'
        verbose_name_plural = 'Stocks'
        ordering = ['-last_updated']
    
    def __str__(self):
        return f"Stock de {self.product.name} - {self.current_quantity} unités"
    
    def save(self, *args, **kwargs):
        # Calculer la quantité disponible
        self.available_quantity = max(0, self.current_quantity - self.reserved_quantity)
        
        # Mettre à jour le statut
        self.update_status()
        
        super().save(*args, **kwargs)
    
    def update_status(self):
        """Met à jour le statut du stock basé sur la quantité actuelle"""
        if not self.is_active:
            self.status = 'discontinued'
        elif self.current_quantity == 0:
            self.status = 'out_of_stock'
        elif self.current_quantity <= self.min_quantity:
            self.status = 'low_stock'
        else:
            self.status = 'available'
    
    @property
    def is_low_stock(self):
        """Vérifie si le stock est faible"""
        return self.current_quantity <= self.min_quantity and self.current_quantity > 0
    
    @property
    def is_out_of_stock(self):
        """Vérifie si le produit est en rupture"""
        return self.current_quantity == 0
    
    @property
    def needs_reorder(self):
        """Vérifie si le produit a besoin d'être réapprovisionné"""
        return self.auto_reorder and self.current_quantity <= self.reorder_quantity
    
    def add_stock(self, quantity, reason='Ajustement'):
        """Ajoute de la quantité au stock"""
        if quantity <= 0:
            raise ValueError("La quantité doit être positive")
        
        quantity_before = self.current_quantity
        self.current_quantity += quantity
        self.last_movement = timezone.now()
        self.save()
        
        # Créer un mouvement de stock
        StockMovement.objects.create(
            stock=self,
            movement_type='in',
            quantity=quantity,
            reason=reason,
            quantity_before=quantity_before,
            quantity_after=self.current_quantity
        )
    
    def remove_stock(self, quantity, reason='Sortie'):
        """Retire de la quantité du stock"""
        if quantity <= 0:
            raise ValueError("La quantité doit être positive")
        
        if quantity > self.available_quantity:
            raise ValueError("Quantité insuffisante en stock")
        
        quantity_before = self.current_quantity
        self.current_quantity -= quantity
        self.last_movement = timezone.now()
        self.save()
        
        # Créer un mouvement de stock
        StockMovement.objects.create(
            stock=self,
            movement_type='out',
            quantity=quantity,
            reason=reason,
            quantity_before=quantity_before,
            quantity_after=self.current_quantity
        )
    
    def adjust_stock(self, new_quantity, reason='Ajustement'):
        """Ajuste le stock à une nouvelle quantité"""
        old_quantity = self.current_quantity
        difference = new_quantity - old_quantity
        
        self.current_quantity = new_quantity
        self.last_movement = timezone.now()
        self.save()
        
        # Créer un mouvement de stock
        if difference != 0:
            StockMovement.objects.create(
                stock=self,
                movement_type='adjustment',
                quantity=abs(difference),
                reason=f"{reason} (Ajustement de {old_quantity} à {new_quantity})",
                quantity_before=old_quantity,
                quantity_after=new_quantity
            )


class StockMovement(models.Model):
    """Modèle pour tracer les mouvements de stock"""
    stock = models.ForeignKey(
        Stock,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name='Stock'
    )
    
    movement_type = models.CharField(
        max_length=20,
        choices=Stock.MOVEMENT_TYPES,
        verbose_name='Type de mouvement'
    )
    quantity = models.PositiveIntegerField(verbose_name='Quantité')
    reason = models.CharField(
        max_length=200,
        verbose_name='Raison du mouvement'
    )
    
    # Quantités avant et après
    quantity_before = models.PositiveIntegerField(verbose_name='Quantité avant')
    quantity_after = models.PositiveIntegerField(verbose_name='Quantité après')
    
    # Utilisateur qui a effectué le mouvement
    user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Utilisateur'
    )
    
    # Date
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Mouvement de stock'
        verbose_name_plural = 'Mouvements de stock'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.stock.product.name} - {self.quantity} unités"