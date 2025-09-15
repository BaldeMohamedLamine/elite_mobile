import uuid
from django.db import models
from django.utils import timezone
from django.db.models import Sum, F
from .fields import EncryptedCharField, EncryptedTextField, EncryptedPhoneField, EncryptedCardField, EncryptedDecimalField
from .validators import validate_phone_number, validate_card_number, validate_positive_decimal, validate_quantity


class Cart(models.Model):
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    owner = models.OneToOneField(
        'users.User', on_delete=models.CASCADE, related_name='cart'
    )
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def amount(self):
        return self.items.aggregate(
            total_amont=Sum(F('quantity')*F('product__price'))
        )['total_amont']

    @property
    def nb_cart_items(self):
        return self.items.count()


class CartItem(models.Model):
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    cart = models.ForeignKey(
        'Cart', on_delete=models.CASCADE, related_name='items',
    )
    quantity = models.IntegerField()

    class Meta:
        unique_together = ['product', 'cart']


# Nouveaux modèles pour le système de commandes et paiements

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('paid', 'Payée'),
        ('processing', 'En cours de traitement'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
        ('refunded', 'Remboursée'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('orange_money', 'Orange Money'),
        ('visa', 'Carte Visa/Mastercard'),
        ('cash_on_delivery', 'Paiement à la livraison'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    order_number = models.CharField(max_length=20, unique=True, blank=True, null=True)
    customer = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=[
        ('pending', 'En attente'),
        ('paid', 'Payé'),
        ('failed', 'Échoué'),
        ('refunded', 'Remboursé'),
    ], default='pending')
    
    # Informations de livraison
    delivery_address = EncryptedTextField()
    delivery_phone = EncryptedPhoneField(validators=[validate_phone_number])
    delivery_notes = EncryptedTextField(blank=True, null=True)
    
    # Montants
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, validators=[validate_positive_decimal])
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[validate_positive_decimal])
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[validate_positive_decimal])
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[validate_positive_decimal])
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Pour paiement à la livraison
    cash_payment_confirmed = models.BooleanField(default=False)
    cash_payment_confirmed_by = models.ForeignKey(
        'users.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='confirmed_orders'
    )
    cash_payment_confirmed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        order_ref = self.order_number or str(self.uid)[:8]
        return f"Commande {order_ref} - {self.customer.first_name} - {self.total_amount} GNF"
    
    @property
    def is_paid(self):
        return self.payment_status == 'paid' or self.cash_payment_confirmed
    
    @property
    def can_be_cancelled(self):
        return self.status in ['pending', 'paid', 'processing']
    
    def update_stock_quantities(self):
        """Met à jour les quantités en stock pour tous les articles de la commande"""
        for item in self.items.all():
            try:
                # Récupérer le stock du produit
                stock = item.product.stock
                if stock:
                    # Diminuer la quantité disponible
                    stock.available_quantity = max(0, stock.available_quantity - item.quantity)
                    stock.current_quantity = max(0, stock.current_quantity - item.quantity)
                    stock.save()
            except Exception as e:
                # Log l'erreur mais ne pas faire échouer la commande
                print(f"Erreur lors de la mise à jour du stock pour {item.product.name}: {e}")
    
    def restore_stock_quantities(self):
        """Restaure les quantités en stock si la commande est annulée"""
        for item in self.items.all():
            try:
                # Récupérer le stock du produit
                stock = item.product.stock
                if stock:
                    # Restaurer la quantité disponible
                    stock.available_quantity += item.quantity
                    stock.current_quantity += item.quantity
                    stock.save()
            except Exception as e:
                # Log l'erreur mais ne pas faire échouer l'annulation
                print(f"Erreur lors de la restauration du stock pour {item.product.name}: {e}")
    
    def generate_order_number(self):
        """Génère un numéro de commande séquentiel basé sur l'année et le mois"""
        from django.db import transaction
        from datetime import datetime
        
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # Format: CMD-YYYY-MM-XXXX (ex: CMD-2025-09-0001)
        prefix = f"CMD-{current_year}-{current_month:02d}"
        
        with transaction.atomic():
            # Trouver le dernier numéro pour ce mois
            last_order = Order.objects.filter(
                order_number__startswith=prefix
            ).order_by('-order_number').first()
            
            if last_order and last_order.order_number:
                # Extraire le numéro séquentiel
                try:
                    last_number = int(last_order.order_number.split('-')[-1])
                    next_number = last_number + 1
                except (ValueError, IndexError):
                    next_number = 1
            else:
                next_number = 1
            
            # Formater le numéro avec des zéros à gauche
            self.order_number = f"{prefix}-{next_number:04d}"
            return self.order_number
    
    def save(self, *args, **kwargs):
        # Générer le numéro de commande si ce n'est pas déjà fait
        if not self.order_number:
            self.generate_order_number()
        super().save(*args, **kwargs)


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.IntegerField(validators=[validate_quantity])
    price_at_time = models.DecimalField(max_digits=10, decimal_places=2, validators=[validate_positive_decimal])  # Prix au moment de la commande
    
    def __str__(self):
        return f"{self.product.name} x{self.quantity} - {self.order.uid}"


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Order.PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Pour Orange Money
    orange_money_transaction_id = EncryptedCharField(max_length=100, blank=True, null=True)
    orange_money_phone = EncryptedPhoneField(blank=True, null=True)
    
    # Pour Carte Visa
    card_last_four = EncryptedCharField(max_length=4, blank=True, null=True)
    card_brand = EncryptedCharField(max_length=20, blank=True, null=True)
    transaction_id = EncryptedCharField(max_length=100, blank=True, null=True)
    
    # Pour paiement à la livraison
    cash_received = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cash_change = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Paiement {self.uid} - {self.amount} GNF - {self.get_method_display()}"


class Refund(models.Model):
    REFUND_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé'),
    ]
    
    REFUND_REASON_CHOICES = [
        ('customer_request', 'Demande du client'),
        ('defective_product', 'Produit défectueux'),
        ('wrong_item', 'Mauvais article'),
        ('late_delivery', 'Livraison tardive'),
        ('order_cancelled', 'Commande annulée'),
        ('other', 'Autre'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='refunds')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=20, choices=REFUND_REASON_CHOICES)
    reason_description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending')
    
    # Informations de remboursement
    refund_method = models.CharField(max_length=20, choices=Order.PAYMENT_METHOD_CHOICES)
    refund_transaction_id = EncryptedCharField(max_length=100, blank=True, null=True)
    
    # Gestion
    requested_by = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='refund_requests')
    processed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds')
    
    created_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Remboursement {self.uid} - {self.amount} GNF - {self.get_status_display()}"
    
    @property
    def can_be_cancelled(self):
        return self.status in ['pending', 'processing']


class SupportTicket(models.Model):
    """Modèle pour les tickets de support client"""
    
    TICKET_STATUS_CHOICES = [
        ('open', 'Ouvert'),
        ('in_progress', 'En cours'),
        ('waiting_customer', 'En attente client'),
        ('resolved', 'Résolu'),
        ('closed', 'Fermé'),
    ]
    
    TICKET_PRIORITY_CHOICES = [
        ('low', 'Faible'),
        ('medium', 'Moyen'),
        ('high', 'Élevé'),
        ('urgent', 'Urgent'),
    ]
    
    TICKET_CATEGORY_CHOICES = [
        ('technical', 'Problème technique'),
        ('delivery', 'Problème de livraison'),
        ('product', 'Problème produit'),
        ('payment', 'Problème de paiement'),
        ('account', 'Problème de compte'),
        ('other', 'Autre'),
    ]
    
    uid = models.UUIDField(default=uuid.uuid4, unique=True)
    customer = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='support_tickets')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='support_tickets', null=True, blank=True)
    
    subject = EncryptedCharField(max_length=200)
    description = EncryptedTextField()
    category = models.CharField(max_length=20, choices=TICKET_CATEGORY_CHOICES)
    priority = models.CharField(max_length=10, choices=TICKET_PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=TICKET_STATUS_CHOICES, default='open')
    
    # Gestion
    assigned_to = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Ticket #{self.uid} - {self.subject} - {self.get_status_display()}"
    
    @property
    def is_open(self):
        return self.status in ['open', 'in_progress', 'waiting_customer']


class SupportMessage(models.Model):
    """Modèle pour les messages dans un ticket de support"""
    
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name='messages')
    author = models.ForeignKey('users.User', on_delete=models.CASCADE)
    message = EncryptedTextField()
    is_internal = models.BooleanField(default=False)  # Message interne (non visible par le client)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Message de {self.author.first_name} - {self.ticket.uid}"


# Import des modèles d'audit
from .audit import AuditLog, SecurityEvent
