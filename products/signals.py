"""
Signaux pour la gestion automatique du stock
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, Stock


@receiver(post_save, sender=Product)
def create_stock_for_product(sender, instance, created, **kwargs):
    """
    Crée automatiquement un stock à 0 pour chaque nouveau produit
    """
    if created:
        # Créer un stock avec quantité 0 pour le nouveau produit
        Stock.objects.create(
            product=instance,
            current_quantity=0,
            available_quantity=0,
            status='out_of_stock'
        )
        print(f"✅ Stock créé automatiquement pour le produit: {instance.name}")


@receiver(post_save, sender=Stock)
def create_stock_movement(sender, instance, created, **kwargs):
    """
    Crée un mouvement de stock lors de la création initiale
    """
    if created:
        from .models import StockMovement
        StockMovement.objects.create(
            stock=instance,
            movement_type='adjustment',
            quantity=0,
            reason='Création initiale du stock',
            quantity_before=0,
            quantity_after=0
        )
