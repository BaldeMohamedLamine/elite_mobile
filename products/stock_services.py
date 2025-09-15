"""
Services pour la gestion des stocks et alertes
"""
from django.db import transaction, models
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from .models import Product, StockAlert, StockMovement
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class StockAlertService:
    """Service pour gérer les alertes de stock"""
    
    @staticmethod
    def check_stock_levels():
        """Vérifie les niveaux de stock et crée des alertes si nécessaire"""
        alerts_created = 0
        
        # Produits avec stock faible
        low_stock_products = Product.objects.filter(
            is_active=True,
            quantity__lte=models.F('min_stock_level')
        ).exclude(
            stock_alerts__status='active',
            stock_alerts__alert_type='low_stock'
        )
        
        for product in low_stock_products:
            StockAlertService.create_low_stock_alert(product)
            alerts_created += 1
        
        # Produits en rupture de stock
        out_of_stock_products = Product.objects.filter(
            is_active=True,
            quantity=0
        ).exclude(
            stock_alerts__status='active',
            stock_alerts__alert_type='out_of_stock'
        )
        
        for product in out_of_stock_products:
            StockAlertService.create_out_of_stock_alert(product)
            alerts_created += 1
        
        # Produits en surstock
        overstock_products = Product.objects.filter(
            is_active=True,
            quantity__gt=models.F('max_stock_level')
        ).exclude(
            stock_alerts__status='active',
            stock_alerts__alert_type='overstock'
        )
        
        for product in overstock_products:
            StockAlertService.create_overstock_alert(product)
            alerts_created += 1
        
        logger.info(f"Vérification des stocks terminée. {alerts_created} alertes créées.")
        return alerts_created
    
    @staticmethod
    def create_low_stock_alert(product):
        """Crée une alerte de stock faible"""
        message = f"Stock faible pour {product.name}. Quantité actuelle: {product.quantity}, Seuil minimum: {product.min_stock_level}"
        
        alert = StockAlert.objects.create(
            product=product,
            alert_type='low_stock',
            current_quantity=product.quantity,
            threshold_quantity=product.min_stock_level,
            message=message
        )
        
        # Envoyer notification email si configuré
        StockAlertService.send_alert_notification(alert)
        return alert
    
    @staticmethod
    def create_out_of_stock_alert(product):
        """Crée une alerte de rupture de stock"""
        message = f"Rupture de stock pour {product.name}. Le produit n'est plus disponible."
        
        alert = StockAlert.objects.create(
            product=product,
            alert_type='out_of_stock',
            current_quantity=product.quantity,
            threshold_quantity=0,
            message=message
        )
        
        # Désactiver le produit automatiquement
        product.is_active = False
        product.save(update_fields=['is_active'])
        
        # Envoyer notification email
        StockAlertService.send_alert_notification(alert)
        return alert
    
    @staticmethod
    def create_overstock_alert(product):
        """Crée une alerte de surstock"""
        message = f"Surstock pour {product.name}. Quantité actuelle: {product.quantity}, Stock maximum recommandé: {product.max_stock_level}"
        
        alert = StockAlert.objects.create(
            product=product,
            alert_type='overstock',
            current_quantity=product.quantity,
            threshold_quantity=product.max_stock_level,
            message=message
        )
        
        StockAlertService.send_alert_notification(alert)
        return alert
    
    @staticmethod
    def send_alert_notification(alert):
        """Envoie une notification email pour une alerte"""
        try:
            # Récupérer les utilisateurs managers
            managers = User.objects.filter(is_staff=True, is_active=True)
            
            if managers.exists():
                subject = f"🚨 Alerte Stock - {alert.get_alert_type_display()}"
                message = f"""
                {alert.message}
                
                Produit: {alert.product.name}
                SKU: {alert.product.sku or 'N/A'}
                Catégorie: {alert.product.category.name}
                Quantité actuelle: {alert.current_quantity}
                Seuil: {alert.threshold_quantity}
                
                Date de l'alerte: {alert.created_at.strftime('%d/%m/%Y %H:%M')}
                
                Connectez-vous à votre dashboard pour plus de détails.
                """
                
                recipient_list = [manager.email for manager in managers]
                
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=recipient_list,
                    fail_silently=False,
                )
                
                logger.info(f"Notification email envoyée pour l'alerte {alert.uid}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de notification email: {e}")
    
    @staticmethod
    def get_active_alerts():
        """Récupère toutes les alertes actives"""
        return StockAlert.objects.filter(status='active').select_related('product')
    
    @staticmethod
    def acknowledge_alert(alert, user):
        """Reconnaît une alerte"""
        alert.acknowledge(user)
        logger.info(f"Alerte {alert.uid} reconnue par {user.email}")
    
    @staticmethod
    def resolve_alert(alert, user):
        """Résout une alerte"""
        alert.resolve(user)
        logger.info(f"Alerte {alert.uid} résolue par {user.email}")
    
    @staticmethod
    def dismiss_alert(alert):
        """Ignore une alerte"""
        alert.dismiss()
        logger.info(f"Alerte {alert.uid} ignorée")


class StockMovementService:
    """Service pour gérer les mouvements de stock"""
    
    @staticmethod
    @transaction.atomic
    def record_movement(product, movement_type, quantity, reason="", reference="", notes="", user=None):
        """Enregistre un mouvement de stock"""
        quantity_before = product.quantity
        
        # Effectuer le mouvement selon le type
        if movement_type == 'in':
            product.add_stock(quantity)
        elif movement_type == 'out':
            if not product.consume_stock(quantity):
                raise ValueError(f"Stock insuffisant pour {product.name}")
        elif movement_type == 'adjustment':
            product.quantity = quantity
            product.save(update_fields=['quantity', 'last_stock_update'])
        elif movement_type == 'reserved':
            if not product.reserve_stock(quantity):
                raise ValueError(f"Stock insuffisant pour réserver {product.name}")
        elif movement_type == 'released':
            product.release_stock(quantity)
        
        quantity_after = product.quantity
        
        # Créer l'enregistrement du mouvement
        movement = StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=quantity,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            reason=reason,
            reference=reference,
            notes=notes,
            created_by=user
        )
        
        # Vérifier les alertes après le mouvement
        StockAlertService.check_product_alerts(product)
        
        logger.info(f"Mouvement de stock enregistré: {movement}")
        return movement
    
    @staticmethod
    def get_product_movements(product, days=30):
        """Récupère les mouvements d'un produit sur une période"""
        from datetime import timedelta
        start_date = timezone.now() - timedelta(days=days)
        
        return StockMovement.objects.filter(
            product=product,
            created_at__gte=start_date
        ).order_by('-created_at')
    
    @staticmethod
    def get_stock_summary():
        """Récupère un résumé des stocks"""
        from django.db.models import Count, Sum
        
        summary = {
            'total_products': Product.objects.filter(is_active=True).count(),
            'low_stock_products': Product.objects.filter(
                is_active=True,
                quantity__lte=models.F('min_stock_level')
            ).count(),
            'out_of_stock_products': Product.objects.filter(
                is_active=True,
                quantity=0
            ).count(),
            'overstock_products': Product.objects.filter(
                is_active=True,
                quantity__gt=models.F('max_stock_level')
            ).count(),
            'total_stock_value': Product.objects.filter(
                is_active=True
            ).aggregate(
                total=Sum(models.F('quantity') * models.F('price'))
            )['total'] or 0,
            'active_alerts': StockAlert.objects.filter(status='active').count(),
        }
        
        return summary


    @staticmethod
    def check_product_alerts(product):
        """Vérifie et crée des alertes pour un produit spécifique"""
        # Fermer les alertes actives si le problème est résolu
        if product.quantity > product.min_stock_level:
            StockAlert.objects.filter(
                product=product,
                status='active',
                alert_type__in=['low_stock', 'out_of_stock']
            ).update(status='resolved', resolved_at=timezone.now())
        
        # Créer de nouvelles alertes si nécessaire
        if product.quantity <= 0:
            StockAlertService.create_out_of_stock_alert(product)
        elif product.quantity <= product.min_stock_level:
            StockAlertService.create_low_stock_alert(product)
        elif product.quantity > product.max_stock_level:
            StockAlertService.create_overstock_alert(product)
