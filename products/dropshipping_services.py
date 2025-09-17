"""
Services pour la gestion du dropshipping
"""
from django.db import transaction
from django.utils import timezone
from .dropshipping_models import Supplier, DropshipProduct, SupplierSale, SupplierInvoice
from decimal import Decimal
import uuid


class DropshippingService:
    """Service pour gérer les opérations de dropshipping"""
    
    @staticmethod
    def confirm_dropship_sale(supplier_sale):
        """
        Confirme une vente dropshipping
        """
        try:
            with transaction.atomic():
                supplier_sale.status = 'confirmed'
                supplier_sale.confirmed_at = timezone.now()
                supplier_sale.save()
                
                # Mettre à jour le stock du fournisseur si nécessaire
                if supplier_sale.dropship_product:
                    dropship_product = supplier_sale.dropship_product
                    if dropship_product.auto_reorder:
                        # Logique de réapprovisionnement automatique
                        pass
                
                return True
        except Exception as e:
            print(f"Erreur lors de la confirmation de la vente dropshipping: {e}")
            return False
    
    @staticmethod
    def ship_dropship_sale(supplier_sale, tracking_number):
        """
        Marque une vente dropshipping comme expédiée
        """
        try:
            with transaction.atomic():
                supplier_sale.status = 'shipped'
                supplier_sale.shipped_at = timezone.now()
                supplier_sale.tracking_number = tracking_number
                supplier_sale.save()
                
                return True
        except Exception as e:
            print(f"Erreur lors de l'expédition de la vente dropshipping: {e}")
            return False
    
    @staticmethod
    def deliver_dropship_sale(supplier_sale):
        """
        Marque une vente dropshipping comme livrée
        """
        try:
            with transaction.atomic():
                supplier_sale.status = 'delivered'
                supplier_sale.delivered_at = timezone.now()
                supplier_sale.save()
                
                # Mettre à jour les statistiques du fournisseur
                if supplier_sale.supplier:
                    supplier = supplier_sale.supplier
                    # Incrémenter le nombre de ventes réussies
                    supplier.total_sales = (supplier.total_sales or 0) + 1
                    supplier.save()
                
                return True
        except Exception as e:
            print(f"Erreur lors de la livraison de la vente dropshipping: {e}")
            return False
    
    @staticmethod
    def cancel_dropship_sale(supplier_sale, reason):
        """
        Annule une vente dropshipping
        """
        try:
            with transaction.atomic():
                supplier_sale.status = 'cancelled'
                supplier_sale.cancelled_at = timezone.now()
                supplier_sale.cancellation_reason = reason
                supplier_sale.save()
                
                return True
        except Exception as e:
            print(f"Erreur lors de l'annulation de la vente dropshipping: {e}")
            return False
    
    @staticmethod
    def generate_supplier_invoice(supplier, start_date, end_date):
        """
        Génère une facture pour un fournisseur sur une période donnée
        """
        try:
            with transaction.atomic():
                # Récupérer les ventes de la période
                sales = SupplierSale.objects.filter(
                    supplier=supplier,
                    status='delivered',
                    delivered_at__date__range=[start_date, end_date]
                )
                
                if not sales.exists():
                    return None
                
                # Calculer le montant total
                total_amount = sum(sale.total_amount for sale in sales if sale.total_amount)
                
                # Créer la facture
                invoice = SupplierInvoice.objects.create(
                    supplier=supplier,
                    invoice_number=f"INV-{supplier.uid[:8]}-{timezone.now().strftime('%Y%m%d')}",
                    period_start=start_date,
                    period_end=end_date,
                    total_amount=Decimal(str(total_amount)),
                    status='pending',
                    due_date=timezone.now().date() + timezone.timedelta(days=30)
                )
                
                # Associer les ventes à la facture
                sales.update(invoice=invoice)
                
                return invoice
                
        except Exception as e:
            print(f"Erreur lors de la génération de la facture: {e}")
            return None
    
    @staticmethod
    def calculate_supplier_commission(supplier_sale):
        """
        Calcule la commission du fournisseur pour une vente
        """
        try:
            if not supplier_sale.dropship_product:
                return Decimal('0.00')
            
            dropship_product = supplier_sale.dropship_product
            supplier = supplier_sale.supplier
            
            # Commission de base du produit
            base_commission = dropship_product.commission_percentage or Decimal('0.00')
            
            # Commission supplémentaire du fournisseur
            supplier_commission = supplier.commission_percentage or Decimal('0.00')
            
            # Commission totale
            total_commission = base_commission + supplier_commission
            
            # Calculer le montant de la commission
            if supplier_sale.total_amount:
                commission_amount = (supplier_sale.total_amount * total_commission) / 100
                return commission_amount
            
            return Decimal('0.00')
            
        except Exception as e:
            print(f"Erreur lors du calcul de la commission: {e}")
            return Decimal('0.00')
    
    @staticmethod
    def update_supplier_rating(supplier):
        """
        Met à jour la note du fournisseur basée sur ses performances
        """
        try:
            # Récupérer les statistiques du fournisseur
            total_sales = SupplierSale.objects.filter(supplier=supplier).count()
            successful_sales = SupplierSale.objects.filter(
                supplier=supplier, 
                status='delivered'
            ).count()
            
            if total_sales == 0:
                return
            
            # Calculer le taux de réussite
            success_rate = (successful_sales / total_sales) * 100
            
            # Calculer la note (sur 5)
            if success_rate >= 95:
                rating = 5.0
            elif success_rate >= 90:
                rating = 4.5
            elif success_rate >= 80:
                rating = 4.0
            elif success_rate >= 70:
                rating = 3.5
            elif success_rate >= 60:
                rating = 3.0
            else:
                rating = 2.5
            
            # Mettre à jour la note du fournisseur
            supplier.rating = rating
            supplier.save()
            
        except Exception as e:
            print(f"Erreur lors de la mise à jour de la note: {e}")
    
    @staticmethod
    def get_supplier_performance_stats(supplier, days=30):
        """
        Récupère les statistiques de performance d'un fournisseur
        """
        try:
            end_date = timezone.now().date()
            start_date = end_date - timezone.timedelta(days=days)
            
            sales = SupplierSale.objects.filter(
                supplier=supplier,
                created_at__date__range=[start_date, end_date]
            )
            
            stats = {
                'total_sales': sales.count(),
                'confirmed_sales': sales.filter(status='confirmed').count(),
                'shipped_sales': sales.filter(status='shipped').count(),
                'delivered_sales': sales.filter(status='delivered').count(),
                'cancelled_sales': sales.filter(status='cancelled').count(),
                'total_revenue': sum(sale.total_amount for sale in sales if sale.total_amount),
                'success_rate': 0,
                'average_delivery_time': 0
            }
            
            if stats['total_sales'] > 0:
                stats['success_rate'] = (stats['delivered_sales'] / stats['total_sales']) * 100
            
            return stats
            
        except Exception as e:
            print(f"Erreur lors du calcul des statistiques: {e}")
            return {}
