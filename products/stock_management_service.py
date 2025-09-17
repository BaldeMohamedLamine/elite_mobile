"""
Service de gestion des stocks hybrides (physique + virtuel)
Implémente la logique FIFO (First In, First Out)
"""
from django.db import transaction, models
from django.core.exceptions import ValidationError
from .models import Product, Stock
from .dropshipping_models import DropshipProduct, SupplierSale
from orders.models import Order, OrderItem
import logging

logger = logging.getLogger(__name__)


class StockManagementService:
    """Service pour gérer les stocks hybrides avec logique FIFO"""
    
    @staticmethod
    def get_available_stock(product):
        """
        Retourne le stock total disponible pour un produit
        (stock physique + stock virtuel de tous les fournisseurs)
        """
        try:
            # Stock physique
            physical_stock = 0
            if hasattr(product, 'stock'):
                physical_stock = product.stock.available_quantity
            
            # Stock virtuel (somme de tous les fournisseurs actifs)
            virtual_stock = DropshipProduct.objects.filter(
                product=product,
                is_active=True
            ).aggregate(
                total=models.Sum('virtual_stock')
            )['total'] or 0
            
            return {
                'physical': physical_stock,
                'virtual': virtual_stock,
                'total': physical_stock + virtual_stock
            }
        except Exception as e:
            logger.error(f"Erreur lors du calcul du stock pour {product.name}: {e}")
            return {'physical': 0, 'virtual': 0, 'total': 0}
    
    @staticmethod
    def can_sell_quantity(product, quantity):
        """
        Vérifie si on peut vendre la quantité demandée
        """
        stock_info = StockManagementService.get_available_stock(product)
        return stock_info['total'] >= quantity
    
    @staticmethod
    @transaction.atomic
    def sell_quantity(product, quantity, order_item, reason='Vente'):
        """
        Vendre une quantité en respectant la logique FIFO :
        1. D'abord le stock physique
        2. Ensuite le stock virtuel (par ordre de création)
        """
        if not StockManagementService.can_sell_quantity(product, quantity):
            raise ValidationError(f"Stock insuffisant pour {product.name}. Demandé: {quantity}")
        
        remaining_quantity = quantity
        sales_records = []
        
        # 1. Vendre d'abord le stock physique
        if hasattr(product, 'stock') and product.stock.available_quantity > 0:
            physical_available = product.stock.available_quantity
            physical_to_sell = min(remaining_quantity, physical_available)
            
            if physical_to_sell > 0:
                # Diminuer le stock physique
                product.stock.remove_stock(physical_to_sell, f"{reason} - Stock physique")
                remaining_quantity -= physical_to_sell
                
                logger.info(f"Vendu {physical_to_sell} unités du stock physique pour {product.name}")
        
        # 2. Vendre ensuite le stock virtuel (FIFO)
        if remaining_quantity > 0:
            # Récupérer les produits dropship par ordre de création (FIFO)
            dropship_products = DropshipProduct.objects.filter(
                product=product,
                is_active=True,
                virtual_stock__gt=0
            ).order_by('created_at')
            
            for dropship_product in dropship_products:
                if remaining_quantity <= 0:
                    break
                
                virtual_available = dropship_product.virtual_stock
                virtual_to_sell = min(remaining_quantity, virtual_available)
                
                if virtual_to_sell > 0:
                    # Diminuer le stock virtuel
                    dropship_product.decrease_virtual_stock(virtual_to_sell, reason)
                    remaining_quantity -= virtual_to_sell
                    
                    # Créer un enregistrement de vente fournisseur
                    supplier_sale = SupplierSale.objects.create(
                        supplier=dropship_product.supplier,
                        dropship_product=dropship_product,
                        order=order_item.order,
                        order_item=order_item,
                        quantity=virtual_to_sell,
                        supplier_price=dropship_product.supplier_price,
                        selling_price=dropship_product.selling_price,
                        commission_earned=virtual_to_sell * (dropship_product.selling_price - dropship_product.supplier_price),
                        status='pending'
                    )
                    sales_records.append(supplier_sale)
                    
                    logger.info(f"Vendu {virtual_to_sell} unités du stock virtuel ({dropship_product.supplier.name}) pour {product.name}")
        
        if remaining_quantity > 0:
            raise ValidationError(f"Erreur dans la logique de vente. Reste {remaining_quantity} unités non vendues")
        
        return sales_records
    
    @staticmethod
    @transaction.atomic
    def restore_quantity(product, quantity, reason='Annulation'):
        """
        Restaurer une quantité en respectant la logique inverse :
        1. D'abord le stock virtuel (par ordre inverse de création)
        2. Ensuite le stock physique
        """
        remaining_quantity = quantity
        
        # 1. Restaurer d'abord le stock virtuel (LIFO - Last In, First Out)
        dropship_products = DropshipProduct.objects.filter(
            product=product,
            is_active=True
        ).order_by('-created_at')  # Ordre inverse pour LIFO
        
        for dropship_product in dropship_products:
            if remaining_quantity <= 0:
                break
            
            # Augmenter le stock virtuel
            dropship_product.increase_virtual_stock(remaining_quantity, reason)
            remaining_quantity = 0
            
            logger.info(f"Restauré {quantity} unités du stock virtuel ({dropship_product.supplier.name}) pour {product.name}")
            break  # On restaure tout dans le premier fournisseur trouvé
        
        # 2. Si il reste encore des quantités, restaurer le stock physique
        if remaining_quantity > 0 and hasattr(product, 'stock'):
            product.stock.increase_stock(remaining_quantity, f"{reason} - Stock physique")
            logger.info(f"Restauré {remaining_quantity} unités du stock physique pour {product.name}")
    
    @staticmethod
    def get_stock_breakdown(product):
        """
        Retourne une répartition détaillée du stock
        """
        breakdown = {
            'physical': 0,
            'virtual_by_supplier': [],
            'total': 0
        }
        
        # Stock physique
        if hasattr(product, 'stock'):
            breakdown['physical'] = product.stock.available_quantity
        
        # Stock virtuel par fournisseur
        dropship_products = DropshipProduct.objects.filter(
            product=product,
            is_active=True
        ).select_related('supplier')
        
        for dp in dropship_products:
            if dp.stock_virtuel > 0:
                breakdown['virtual_by_supplier'].append({
                    'supplier_name': dp.supplier.name,
                    'supplier_uid': dp.supplier.uid,
                    'quantity': dp.stock_virtuel,
                    'supplier_price': dp.supplier_price,
                    'selling_price': dp.selling_price,
                    'margin': dp.selling_price - dp.supplier_price
                })
        
        # Total
        breakdown['total'] = breakdown['physical'] + sum(
            item['quantity'] for item in breakdown['virtual_by_supplier']
        )
        
        return breakdown
    
    @staticmethod
    def update_virtual_stock_from_form(dropship_product, virtual_stock_quantity):
        """
        Met à jour le stock virtuel depuis un formulaire
        Si le stock virtuel est renseigné, met automatiquement la quantité du produit dans le stock
        """
        if virtual_stock_quantity and virtual_stock_quantity > 0:
            # Mettre à jour le stock virtuel
            dropship_product.update_virtual_stock(virtual_stock_quantity, 'Mise à jour depuis formulaire')
            
            # Optionnel : Mettre à jour aussi le stock physique si nécessaire
            # (selon votre logique métier)
            logger.info(f"Stock virtuel mis à jour pour {dropship_product.product.name}: {virtual_stock_quantity} unités")
        
        return dropship_product
