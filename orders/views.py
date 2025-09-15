import json
from decimal import Decimal
from django.views import View
from django.views.generic import DetailView, CreateView, ListView
from django.http import JsonResponse, HttpResponseRedirect
from django.db.utils import IntegrityError
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin

from products.models import Product
from orders.models import Cart, CartItem, Order, OrderItem, Payment, Refund, SupportTicket, SupportMessage
from orders.forms import CheckoutForm, OrangeMoneyPaymentForm, VisaPaymentForm, CashPaymentConfirmationForm, RefundRequestForm, RefundProcessForm, SupportTicketForm, SupportMessageForm
from orders.utils import generate_invoice_pdf, generate_receipt_pdf, generate_pdf_response
from orders.email_utils import (
    send_order_confirmation_email, send_payment_confirmation_email,
    send_order_shipped_email, send_order_delivered_email,
    send_refund_request_email, send_refund_processed_email
)
from orders.services import CartService, OrderService, PaymentService


class AddToCardView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': "Données JSON invalides."
            }, status=400)
        
        # Validation des données
        product_uid = data.get('product_uid')
        quantity = data.get('quantity', 1)
        
        if not product_uid:
            return JsonResponse({
                'success': False,
                'message': "ID du produit manquant."
            }, status=400)
        
        if not isinstance(quantity, int) or quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': "Quantité invalide."
            }, status=400)
        
        try:
            product = Product.objects.get(uid=product_uid)
            
            # Utiliser le service de panier
            result = CartService.add_to_cart(request.user, product, quantity)
            
            if result['success']:
                return JsonResponse(result)
            else:
                return JsonResponse(result, status=400)
            
        except Product.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': "Produit non trouvé."
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in AddToCardView: {e}")
            return JsonResponse({
                'success': False,
                'message': "Une erreur inattendue s'est produite."
            }, status=500)


class UpdateCartItemView(LoginRequiredMixin, View):
    """Vue pour mettre à jour la quantité d'un article du panier"""
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': "Données JSON invalides."
            }, status=400)
        
        # Validation des données
        item_id = data.get('item_id')
        quantity = data.get('quantity', 1)
        
        if not item_id:
            return JsonResponse({
                'success': False,
                'message': "ID de l'article manquant."
            }, status=400)
        
        if not isinstance(quantity, int) or quantity <= 0:
            return JsonResponse({
                'success': False,
                'message': "Quantité invalide."
            }, status=400)
        
        try:
            # Récupérer l'article du panier
            cart_item = CartItem.objects.get(id=item_id, cart__owner=request.user)
            
            # Mettre à jour la quantité
            cart_item.quantity = quantity
            cart_item.save()
            
            # Calculer le nouveau total du panier
            cart = cart_item.cart
            cart_total = sum(item.product.price * item.quantity for item in cart.items.all())
            
            return JsonResponse({
                'success': True,
                'message': "Quantité mise à jour avec succès.",
                'new_quantity': cart_item.quantity,
                'item_total': float(cart_item.product.price * cart_item.quantity),
                'cart_total': float(cart_total)
            })
            
        except CartItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': "Article du panier non trouvé."
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in UpdateCartItemView: {e}")
            return JsonResponse({
                'success': False,
                'message': "Une erreur inattendue s'est produite."
            }, status=500)


class RemoveFromCartView(LoginRequiredMixin, View):
    """Vue pour supprimer un article du panier"""
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': "Données JSON invalides."
            }, status=400)
        
        # Validation des données
        item_id = data.get('item_id')
        
        if not item_id:
            return JsonResponse({
                'success': False,
                'message': "ID de l'article manquant."
            }, status=400)
        
        try:
            # Récupérer l'article du panier
            cart_item = CartItem.objects.get(id=item_id, cart__owner=request.user)
            cart = cart_item.cart
            
            # Supprimer l'article
            cart_item.delete()
            
            # Calculer le nouveau total du panier
            cart_total = sum(item.product.price * item.quantity for item in cart.items.all())
            
            return JsonResponse({
                'success': True,
                'message': "Article supprimé du panier avec succès.",
                'cart_total': float(cart_total),
                'cart_count': cart.items.count()
            })
            
        except CartItem.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': "Article du panier non trouvé."
            }, status=404)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Unexpected error in RemoveFromCartView: {e}")
            return JsonResponse({
                'success': False,
                'message': "Une erreur inattendue s'est produite."
            }, status=500)


class CartOrderView(LoginRequiredMixin, DetailView):
    model = Cart
    template_name = 'orders/cart_orders.html'
    context_object_name = 'cart'

    def get_object(self):
        cart, created = Cart.objects.get_or_create(owner=self.request.user)
        return cart


class CheckoutView(LoginRequiredMixin, View):
    """Vue pour finaliser la commande"""
    
    def get(self, request):
        cart = Cart.objects.get(owner=request.user)
        if not cart.items.exists():
            messages.warning(request, "Votre panier est vide.")
            return redirect('orders:list_cart_orders')
        
        # Analyser les produits dropshipping
        dropship_items = []
        dropship_delivery_time = 0
        dropship_shipping_cost = 0
        
        form = CheckoutForm()
        context = {
            'cart': cart,
            'form': form,
            'delivery_fee': Decimal('5000') + dropship_shipping_cost,  # Frais de livraison + dropshipping
            'dropship_items': dropship_items,
            'dropship_delivery_time': dropship_delivery_time,
            'dropship_shipping_cost': dropship_shipping_cost,
        }
        return render(request, 'orders/checkout.html', context)
    
    def post(self, request):
        cart = Cart.objects.get(owner=request.user)
        form = CheckoutForm(request.POST)
        
        if form.is_valid():
            # Calculer les frais de livraison avec dropshipping
            dropship_shipping_cost = 0
            delivery_fee = Decimal('5000') + dropship_shipping_cost
            subtotal = cart.amount or Decimal('0')
            total_amount = subtotal + delivery_fee
            
            # Valider le stock dropshipping
            dropship_errors = []
            if dropship_errors:
                for error in dropship_errors:
                    messages.error(request, error)
                return redirect('checkout')
            
            # Créer la commande
            with transaction.atomic():
                order = Order.objects.create(
                    customer=request.user,
                    delivery_address=form.cleaned_data['delivery_address'],
                    delivery_phone=form.cleaned_data['delivery_phone'],
                    delivery_notes=form.cleaned_data['delivery_notes'],
                    payment_method=form.cleaned_data['payment_method'],
                    subtotal=subtotal,
                    delivery_fee=delivery_fee,
                    total_amount=total_amount
                )
                
                # Créer les articles de commande
                order_items = []
                for cart_item in cart.items.all():
                    order_item = OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        quantity=cart_item.quantity,
                        price_at_time=cart_item.product.price
                    )
                    order_items.append(order_item)
                
                # Traiter les produits dropshipping
                try:
                    dropship_sales = []
                    if dropship_sales:
                        messages.info(request, f"{len(dropship_sales)} produit(s) dropshipping traité(s) avec succès.")
                except Exception as e:
                    messages.error(request, f"Erreur lors du traitement dropshipping: {str(e)}")
                    raise
                
                # Vider le panier
                cart.items.all().delete()
                
                # Envoyer l'email de confirmation de commande
                send_order_confirmation_email(order)
            
            # Rediriger vers la page de paiement
            return redirect('orders:payment_process', order_uid=order.uid)
        
        # Analyser les produits dropshipping pour le contexte d'erreur
        dropship_items = []
        dropship_delivery_time = 0
        dropship_shipping_cost = 0
        
        context = {
            'cart': cart,
            'form': form,
            'delivery_fee': Decimal('5000') + dropship_shipping_cost,
            'dropship_items': dropship_items,
            'dropship_delivery_time': dropship_delivery_time,
            'dropship_shipping_cost': dropship_shipping_cost,
        }
        return render(request, 'orders/checkout.html', context)


class PaymentProcessView(LoginRequiredMixin, View):
    """Vue pour traiter le paiement"""
    
    def get(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid, customer=request.user)
        
        if order.payment_status == 'paid':
            messages.success(request, "Cette commande est déjà payée.")
            return redirect('orders:order_detail', order_uid=order.uid)
        
        context = {
            'order': order,
        }
        
        # Afficher le formulaire approprié selon la méthode de paiement
        if order.payment_method == 'orange_money':
            context['payment_form'] = OrangeMoneyPaymentForm()
            return render(request, 'orders/payment_orange_money.html', context)
        elif order.payment_method == 'visa':
            context['payment_form'] = VisaPaymentForm()
            return render(request, 'orders/payment_visa.html', context)
        elif order.payment_method == 'cash_on_delivery':
            return render(request, 'orders/payment_cash_delivery.html', context)
    
    def post(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid, customer=request.user)
        
        if order.payment_method == 'orange_money':
            form = OrangeMoneyPaymentForm(request.POST)
            if form.is_valid():
                # Simuler le paiement Orange Money
                payment = Payment.objects.create(
                    order=order,
                    amount=order.total_amount,
                    method='orange_money',
                    orange_money_phone=form.cleaned_data['phone_number'],
                    status='completed'
                )
                
                # Mettre à jour la commande
                order.payment_status = 'paid'
                order.paid_at = timezone.now()
                order.status = 'paid'
                order.save()
                
                # Mettre à jour les quantités en stock
                order.update_stock_quantities()
                
                # Envoyer l'email de confirmation de paiement
                send_payment_confirmation_email(order)
                
                messages.success(request, "Paiement Orange Money effectué avec succès! Les quantités en stock ont été mises à jour.")
                return redirect('orders:order_detail', order_uid=order.uid)
        
        elif order.payment_method == 'visa':
            form = VisaPaymentForm(request.POST)
            if form.is_valid():
                # Simuler le paiement par carte
                payment = Payment.objects.create(
                    order=order,
                    amount=order.total_amount,
                    method='visa',
                    card_last_four=form.cleaned_data['card_number'][-4:],
                    card_brand='Visa',
                    status='completed'
                )
                
                # Mettre à jour la commande
                order.payment_status = 'paid'
                order.paid_at = timezone.now()
                order.status = 'paid'
                order.save()
                
                # Mettre à jour les quantités en stock
                order.update_stock_quantities()
                
                # Envoyer l'email de confirmation de paiement
                send_payment_confirmation_email(order)
                
                messages.success(request, "Paiement par carte effectué avec succès! Les quantités en stock ont été mises à jour.")
                return redirect('orders:order_detail', order_uid=order.uid)
        
        # Pour paiement à la livraison, pas de traitement POST nécessaire
        return redirect('orders:order_detail', order_uid=order.uid)


class OrderDetailView(LoginRequiredMixin, DetailView):
    """Vue pour afficher les détails d'une commande"""
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'
    pk_url_kwarg = 'order_uid'
    
    def get_object(self):
        return get_object_or_404(Order, uid=self.kwargs['order_uid'], customer=self.request.user)


class OrderListView(LoginRequiredMixin, ListView):
    """Vue pour lister les commandes de l'utilisateur"""
    model = Order
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 10
    
    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user).order_by('-created_at')


class CashPaymentConfirmationView(LoginRequiredMixin, View):
    """Vue pour confirmer le paiement à la livraison (admin uniquement)"""
    
    def get(self, request, order_uid):
        if not request.user.is_staff:
            messages.error(request, "Accès non autorisé.")
            return redirect('home')
        
        order = get_object_or_404(Order, uid=order_uid)
        form = CashPaymentConfirmationForm(order=order)
        
        context = {
            'order': order,
            'form': form,
        }
        return render(request, 'orders/cash_payment_confirmation.html', context)
    
    def post(self, request, order_uid):
        if not request.user.is_staff:
            messages.error(request, "Accès non autorisé.")
            return redirect('home')
        
        order = get_object_or_404(Order, uid=order_uid)
        form = CashPaymentConfirmationForm(request.POST, order=order)
        
        if form.is_valid():
            cash_received = form.cleaned_data['cash_received']
            cash_change = cash_received - order.total_amount
            
            # Créer le paiement
            payment = Payment.objects.create(
                order=order,
                amount=order.total_amount,
                method='cash_on_delivery',
                status='completed',
                cash_received=cash_received,
                cash_change=cash_change
            )
            
            # Mettre à jour la commande
            order.payment_status = 'paid'
            order.paid_amount = order.total_amount
            order.cash_payment_confirmed = True
            order.cash_payment_confirmed_by = request.user
            order.cash_payment_confirmed_at = timezone.now()
            order.paid_at = timezone.now()
            order.status = 'paid'
            order.save()
            
            # Mettre à jour les quantités en stock
            order.update_stock_quantities()
            
            # Envoyer l'email de confirmation de paiement
            send_payment_confirmation_email(order)
            
            messages.success(
                request, 
                f"Paiement confirmé! Montant reçu: {cash_received} GNF, "
                f"Monnaie rendue: {cash_change} GNF. "
                f"Les quantités en stock ont été mises à jour."
            )
            return redirect('admin_order_detail', order_uid=order.uid)
        
        context = {
            'order': order,
            'form': form,
        }
        return render(request, 'orders/cash_payment_confirmation.html', context)


class InvoicePDFView(LoginRequiredMixin, View):
    """Vue pour générer et télécharger la facture PDF (accessible à tous les utilisateurs connectés)"""
    
    def get(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid)
        
        try:
            pdf_bytes = generate_invoice_pdf(order)
            order_ref = order.order_number or str(order.uid)[:8]
            filename = f'facture_{order_ref}.pdf'
            return generate_pdf_response(pdf_bytes, filename)
        except Exception as e:
            messages.error(request, f"Erreur lors de la génération de la facture: {str(e)}")
            return redirect('orders:order_detail', order_uid=order.uid)


class ReceiptPDFView(LoginRequiredMixin, View):
    """Vue pour générer et télécharger le reçu PDF (accessible à tous les utilisateurs connectés)"""
    
    def get(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid)
        
        if not order.is_paid:
            messages.warning(request, "Le reçu n'est disponible que pour les commandes payées.")
            return redirect('orders:order_detail', order_uid=order.uid)
        
        try:
            pdf_bytes = generate_receipt_pdf(order)
            order_ref = order.order_number or str(order.uid)[:8]
            filename = f'recu_{order_ref}.pdf'
            return generate_pdf_response(pdf_bytes, filename)
        except Exception as e:
            messages.error(request, f"Erreur lors de la génération du reçu: {str(e)}")
            return redirect('orders:order_detail', order_uid=order.uid)


class RefundRequestView(LoginRequiredMixin, View):
    """Vue pour demander un remboursement"""
    
    def get(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid, customer=request.user)
        
        # Vérifier si la commande peut être remboursée
        if not order.is_paid:
            messages.error(request, "Seules les commandes payées peuvent être remboursées.")
            return redirect('orders:order_detail', order_uid=order.uid)
        
        if order.status == 'cancelled':
            messages.error(request, "Cette commande est déjà annulée.")
            return redirect('orders:order_detail', order_uid=order.uid)
        
        # Vérifier s'il n'y a pas déjà un remboursement en cours
        existing_refund = Refund.objects.filter(
            order=order, 
            status__in=['pending', 'processing']
        ).first()
        
        if existing_refund:
            messages.warning(request, "Un remboursement est déjà en cours pour cette commande.")
            return redirect('orders:order_detail', order_uid=order.uid)
        
        form = RefundRequestForm(order=order)
        context = {
            'order': order,
            'form': form,
        }
        return render(request, 'orders/refund_request.html', context)
    
    def post(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid, customer=request.user)
        form = RefundRequestForm(request.POST, order=order)
        
        if form.is_valid():
            refund = form.save(commit=False)
            refund.order = order
            refund.requested_by = request.user
            refund.refund_method = order.payment_method  # Même méthode que le paiement
            refund.save()
            
            # Mettre à jour le statut de la commande
            order.status = 'cancelled'
            order.save()
            
            # Envoyer l'email de confirmation de demande de remboursement
            send_refund_request_email(refund)
            
            messages.success(
                request, 
                f"Demande de remboursement créée avec succès. "
                f"Montant: {refund.amount} GNF. "
                f"Vous serez contacté sous 24-48h. "
                f"Un email de confirmation vous a été envoyé."
            )
            return redirect('orders:order_detail', order_uid=order.uid)
        
        context = {
            'order': order,
            'form': form,
        }
        return render(request, 'orders/refund_request.html', context)


class RefundListView(LoginRequiredMixin, ListView):
    """Vue pour lister les remboursements de l'utilisateur"""
    model = Refund
    template_name = 'orders/refund_list.html'
    context_object_name = 'refunds'
    paginate_by = 10
    
    def get_queryset(self):
        return Refund.objects.filter(requested_by=self.request.user).order_by('-created_at')


class RefundDetailView(LoginRequiredMixin, DetailView):
    """Vue pour afficher les détails d'un remboursement"""
    model = Refund
    template_name = 'orders/refund_detail.html'
    context_object_name = 'refund'
    pk_url_kwarg = 'refund_uid'
    
    def get_object(self):
        return get_object_or_404(Refund, uid=self.kwargs['refund_uid'], requested_by=self.request.user)


class OrderStatusUpdateView(LoginRequiredMixin, View):
    """Vue pour mettre à jour le statut d'une commande (admin)"""
    
    def post(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid)
        new_status = request.POST.get('status')
        
        if new_status in [choice[0] for choice in Order.STATUS_CHOICES]:
            old_status = order.status
            order.status = new_status
            
            # Envoyer les emails selon le nouveau statut
            if new_status == 'shipped' and old_status != 'shipped':
                send_order_shipped_email(order)
            elif new_status == 'delivered' and old_status != 'delivered':
                order.delivered_at = timezone.now()
                send_order_delivered_email(order)
            
            order.save()
            messages.success(request, f"Statut de la commande mis à jour à {order.get_status_display()}")
        else:
            messages.error(request, "Statut invalide")
        
        return redirect('orders:order_detail', order_uid=order.uid)


class SupportTicketListView(LoginRequiredMixin, ListView):
    """Vue pour lister les tickets de support de l'utilisateur"""
    model = SupportTicket
    template_name = 'orders/support_ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 10
    
    def get_queryset(self):
        return SupportTicket.objects.filter(customer=self.request.user).order_by('-created_at')


class SupportTicketCreateView(LoginRequiredMixin, View):
    """Vue pour créer un nouveau ticket de support"""
    
    def get(self, request):
        form = SupportTicketForm(user=request.user)
        context = {
            'form': form,
        }
        return render(request, 'orders/support_ticket_create.html', context)
    
    def post(self, request):
        form = SupportTicketForm(request.POST, user=request.user)
        
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.customer = request.user
            ticket.save()
            
            messages.success(
                request, 
                f"Ticket de support créé avec succès ! N° {ticket.uid}. "
                f"Vous serez contacté sous 24-48h."
            )
            return redirect('support_ticket_detail', ticket_uid=ticket.uid)
        
        context = {
            'form': form,
        }
        return render(request, 'orders/support_ticket_create.html', context)


class SupportTicketDetailView(LoginRequiredMixin, DetailView):
    """Vue pour afficher les détails d'un ticket de support"""
    model = SupportTicket
    template_name = 'orders/support_ticket_detail.html'
    context_object_name = 'ticket'
    pk_url_kwarg = 'ticket_uid'
    
    def get_object(self):
        return get_object_or_404(SupportTicket, uid=self.kwargs['ticket_uid'], customer=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['message_form'] = SupportMessageForm(user=self.request.user)
        return context
    
    def post(self, request, ticket_uid):
        ticket = get_object_or_404(SupportTicket, uid=ticket_uid, customer=request.user)
        form = SupportMessageForm(request.POST, user=request.user)
        
        if form.is_valid():
            message = form.save(commit=False)
            message.ticket = ticket
            message.author = request.user
            message.save()
            
            # Mettre à jour le statut du ticket
            if ticket.status == 'resolved':
                ticket.status = 'open'
                ticket.save()
            
            messages.success(request, "Message ajouté avec succès.")
            return redirect('support_ticket_detail', ticket_uid=ticket.uid)
        
        context = {
            'ticket': ticket,
            'message_form': form,
        }
        return render(request, 'orders/support_ticket_detail.html', context)


class CartCountView(View):
    """Vue pour obtenir le nombre d'articles dans le panier"""
    
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            try:
                cart = Cart.objects.get(user=request.user)
                count = cart.items.count()
            except Cart.DoesNotExist:
                count = 0
        else:
            # Pour les utilisateurs non connectés, on peut utiliser la session
            cart_items = request.session.get('cart_items', [])
            count = len(cart_items)
        
        return JsonResponse({
            'count': count,
            'status': 'success'
        })


class ManagerInvoicePDFView(LoginRequiredMixin, View):
    """Vue pour générer et télécharger la facture PDF (accessible à tous les utilisateurs connectés)"""
    
    def get(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid)
        
        try:
            pdf_bytes = generate_invoice_pdf(order)
            order_ref = order.order_number or str(order.uid)[:8]
            filename = f'facture_{order_ref}.pdf'
            return generate_pdf_response(pdf_bytes, filename)
        except Exception as e:
            messages.error(request, f"Erreur lors de la génération de la facture: {str(e)}")
            # Rediriger vers la page appropriée selon le type d'utilisateur
            if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'manager':
                return redirect('manager:order_detail', order_uid=order.uid)
            else:
                return redirect('orders:order_detail', order_uid=order.uid)


class ManagerReceiptPDFView(LoginRequiredMixin, View):
    """Vue pour générer et télécharger le reçu PDF (accessible à tous les utilisateurs connectés)"""
    
    def get(self, request, order_uid):
        order = get_object_or_404(Order, uid=order_uid)
        
        if not order.is_paid:
            messages.warning(request, "Le reçu n'est disponible que pour les commandes payées.")
            # Rediriger vers la page appropriée selon le type d'utilisateur
            if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'manager':
                return redirect('manager:order_detail', order_uid=order.uid)
            else:
                return redirect('orders:order_detail', order_uid=order.uid)
        
        try:
            pdf_bytes = generate_receipt_pdf(order)
            order_ref = order.order_number or str(order.uid)[:8]
            filename = f'recu_{order_ref}.pdf'
            return generate_pdf_response(pdf_bytes, filename)
        except Exception as e:
            messages.error(request, f"Erreur lors de la génération du reçu: {str(e)}")
            # Rediriger vers la page appropriée selon le type d'utilisateur
            if hasattr(request.user, 'userprofile') and request.user.userprofile.user_type == 'manager':
                return redirect('manager:order_detail', order_uid=order.uid)
            else:
                return redirect('orders:order_detail', order_uid=order.uid)
