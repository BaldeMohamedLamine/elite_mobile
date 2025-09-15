"""
Services métier pour la gestion des commandes
"""
from django.db import transaction, models
from django.core.exceptions import ValidationError
from decimal import Decimal
from typing import Dict, List, Optional
import logging

from .models import Order, OrderItem, Cart, CartItem, Payment
from products.models import Product
from users.models import User

logger = logging.getLogger(__name__)


class OrderService:
    """Service de gestion des commandes"""
    
    @classmethod
    def create_order_from_cart(cls, user: User, delivery_data: Dict) -> Order:
        """
        Crée une commande à partir du panier de l'utilisateur
        
        Args:
            user: Utilisateur propriétaire du panier
            delivery_data: Données de livraison
            
        Returns:
            Commande créée
            
        Raises:
            ValidationError: Si les données sont invalides
        """
        try:
            with transaction.atomic():
                # Récupérer le panier
                try:
                    cart = Cart.objects.get(owner=user)
                except Cart.DoesNotExist:
                    raise ValidationError("Panier vide")
                
                cart_items = cart.items.select_related('product').all()
                if not cart_items.exists():
                    raise ValidationError("Panier vide")
                
                # Calculer les montants
                subtotal = Decimal('0.00')
                for item in cart_items:
                    item_total = item.product.price * item.quantity
                    subtotal += item_total
                
                delivery_fee = Decimal(delivery_data.get('delivery_fee', '0.00'))
                total_amount = subtotal + delivery_fee
                
                # Créer la commande
                order = Order.objects.create(
                    customer=user,
                    payment_method=delivery_data.get('payment_method', 'cash_on_delivery'),
                    delivery_address=delivery_data.get('delivery_address', ''),
                    delivery_phone=delivery_data.get('delivery_phone', ''),
                    delivery_notes=delivery_data.get('delivery_notes', ''),
                    subtotal=subtotal,
                    delivery_fee=delivery_fee,
                    total_amount=total_amount
                )
                
                # Créer les articles de commande
                for cart_item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price_at_time=cart_item.product.price
                    )
                
                # Vider le panier
                cart.items.all().delete()
                
                logger.info(f"Order {order.uid} created for user {user.email}")
                return order
                
        except Exception as e:
            logger.error(f"Error creating order for user {user.email}: {e}")
            raise ValidationError(f"Erreur lors de la création de la commande: {e}")
    
    @classmethod
    def update_order_status(cls, order: Order, new_status: str, user: User) -> bool:
        """
        Met à jour le statut d'une commande
        
        Args:
            order: Commande à mettre à jour
            new_status: Nouveau statut
            user: Utilisateur effectuant la modification
            
        Returns:
            True si succès, False sinon
        """
        try:
            old_status = order.status
            order.status = new_status
            order.save()
            
            logger.info(f"Order {order.uid} status changed from {old_status} to {new_status} by {user.email}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating order {order.uid} status: {e}")
            return False
    
    @classmethod
    def cancel_order(cls, order: Order, user: User, reason: str = "") -> bool:
        """
        Annule une commande
        
        Args:
            order: Commande à annuler
            user: Utilisateur effectuant l'annulation
            reason: Raison de l'annulation
            
        Returns:
            True si succès, False sinon
        """
        if not order.can_be_cancelled:
            raise ValidationError("Cette commande ne peut pas être annulée")
        
        try:
            with transaction.atomic():
                order.status = 'cancelled'
                order.save()
                
                # Remettre les produits en stock
                for item in order.items.all():
                    item.product.quantity += item.quantity
                    item.product.save()
                
                logger.info(f"Order {order.uid} cancelled by {user.email}. Reason: {reason}")
                return True
                
        except Exception as e:
            logger.error(f"Error cancelling order {order.uid}: {e}")
            return False


class CartService:
    """Service de gestion du panier"""
    
    @classmethod
    def add_to_cart(cls, user: User, product: Product, quantity: int) -> Dict:
        """
        Ajoute un produit au panier
        
        Args:
            user: Utilisateur propriétaire du panier
            product: Produit à ajouter
            quantity: Quantité à ajouter
            
        Returns:
            Dictionnaire avec le résultat de l'opération
        """
        try:
            # Vérifier le stock
            available_qty = 0
            if hasattr(product, 'stock') and product.stock:
                available_qty = product.stock.available_quantity
            elif hasattr(product, 'quantity'):
                available_qty = product.quantity
            
            if available_qty < quantity:
                return {
                    'success': False,
                    'message': f'Stock insuffisant. Disponible: {available_qty}'
                }
            
            with transaction.atomic():
                # Récupérer ou créer le panier
                cart, created = Cart.objects.get_or_create(owner=user)
                
                # Vérifier si le produit est déjà dans le panier
                cart_item, created = CartItem.objects.get_or_create(
                    product=product,
                    cart=cart,
                    defaults={'quantity': quantity}
                )
                
                if not created:
                    # Mettre à jour la quantité
                    new_quantity = cart_item.quantity + quantity
                    if new_quantity > available_qty:
                        return {
                            'success': False,
                            'message': f'Quantité totale dépasserait le stock disponible ({available_qty})'
                        }
                    cart_item.quantity = new_quantity
                    cart_item.save()
                
                return {
                    'success': True,
                    'message': f'{product.name} ajouté au panier',
                    'cart_item_id': cart_item.id,
                    'quantity': cart_item.quantity
                }
                
        except Exception as e:
            logger.error(f"Error adding product {product.uid} to cart: {e}")
            return {
                'success': False,
                'message': 'Erreur lors de l\'ajout au panier'
            }
    
    @classmethod
    def update_cart_item_quantity(cls, user: User, product: Product, quantity: int) -> Dict:
        """
        Met à jour la quantité d'un article dans le panier
        
        Args:
            user: Utilisateur propriétaire du panier
            product: Produit à modifier
            quantity: Nouvelle quantité
            
        Returns:
            Dictionnaire avec le résultat de l'opération
        """
        try:
            cart = Cart.objects.get(owner=user)
            cart_item = CartItem.objects.get(cart=cart, product=product)
            
            if quantity <= 0:
                cart_item.delete()
                return {
                    'success': True,
                    'message': 'Article supprimé du panier'
                }
            
            if quantity > product.quantity:
                return {
                    'success': False,
                    'message': f'Stock insuffisant. Disponible: {product.quantity}'
                }
            
            cart_item.quantity = quantity
            cart_item.save()
            
            return {
                'success': True,
                'message': 'Quantité mise à jour',
                'cart_item': cart_item
            }
            
        except Cart.DoesNotExist:
            return {
                'success': False,
                'message': 'Panier non trouvé'
            }
        except CartItem.DoesNotExist:
            return {
                'success': False,
                'message': 'Article non trouvé dans le panier'
            }
        except Exception as e:
            logger.error(f"Error updating cart item quantity: {e}")
            return {
                'success': False,
                'message': 'Erreur lors de la mise à jour'
            }
    
    @classmethod
    def remove_from_cart(cls, user: User, product: Product) -> Dict:
        """
        Supprime un produit du panier
        
        Args:
            user: Utilisateur propriétaire du panier
            product: Produit à supprimer
            
        Returns:
            Dictionnaire avec le résultat de l'opération
        """
        try:
            cart = Cart.objects.get(owner=user)
            cart_item = CartItem.objects.get(cart=cart, product=product)
            cart_item.delete()
            
            return {
                'success': True,
                'message': f'{product.name} supprimé du panier'
            }
            
        except Cart.DoesNotExist:
            return {
                'success': False,
                'message': 'Panier non trouvé'
            }
        except CartItem.DoesNotExist:
            return {
                'success': False,
                'message': 'Article non trouvé dans le panier'
            }
        except Exception as e:
            logger.error(f"Error removing product from cart: {e}")
            return {
                'success': False,
                'message': 'Erreur lors de la suppression'
            }
    
    @classmethod
    def get_cart_count(cls, user: User) -> int:
        """
        Obtient le nombre total d'articles dans le panier
        
        Args:
            user: Utilisateur propriétaire du panier
            
        Returns:
            Nombre d'articles dans le panier
        """
        try:
            cart = Cart.objects.get(owner=user)
            return cart.items.aggregate(total=models.Sum('quantity'))['total'] or 0
        except Cart.DoesNotExist:
            return 0
        except Exception as e:
            logger.error(f"Error getting cart count for user {user.email}: {e}")
            return 0
    
    @classmethod
    def get_cart_summary(cls, user: User) -> Dict:
        """
        Récupère un résumé du panier
        
        Args:
            user: Utilisateur propriétaire du panier
            
        Returns:
            Dictionnaire avec le résumé du panier
        """
        try:
            cart = Cart.objects.get(owner=user)
            items = cart.items.select_related('product').all()
            
            total_items = sum(item.quantity for item in items)
            total_amount = sum(item.product.price * item.quantity for item in items)
            
            return {
                'success': True,
                'cart': cart,
                'items': items,
                'total_items': total_items,
                'total_amount': total_amount
            }
            
        except Cart.DoesNotExist:
            return {
                'success': True,
                'cart': None,
                'items': [],
                'total_items': 0,
                'total_amount': Decimal('0.00')
            }
        except Exception as e:
            logger.error(f"Error getting cart summary: {e}")
            return {
                'success': False,
                'message': 'Erreur lors de la récupération du panier'
            }


class PaymentService:
    """Service de gestion des paiements"""
    
    @classmethod
    def process_payment(cls, order: Order, payment_data: Dict) -> Dict:
        """
        Traite un paiement pour une commande
        
        Args:
            order: Commande à payer
            payment_data: Données de paiement
            
        Returns:
            Dictionnaire avec le résultat du paiement
        """
        try:
            with transaction.atomic():
                # Créer l'enregistrement de paiement
                payment = Payment.objects.create(
                    order=order,
                    amount=order.total_amount,
                    method=order.payment_method,
                    status='processing'
                )
                
                # Simuler le traitement du paiement
                # Dans un vrai système, on appellerait l'API de paiement ici
                payment.status = 'completed'
                payment.save()
                
                # Mettre à jour la commande
                order.payment_status = 'paid'
                order.paid_amount = order.total_amount
                order.save()
                
                logger.info(f"Payment {payment.uid} processed for order {order.uid}")
                
                return {
                    'success': True,
                    'payment': payment,
                    'message': 'Paiement traité avec succès'
                }
                
        except Exception as e:
            logger.error(f"Error processing payment for order {order.uid}: {e}")
            return {
                'success': False,
                'message': 'Erreur lors du traitement du paiement'
            }
