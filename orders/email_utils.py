from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
from .models import Order, Refund


def send_order_confirmation_email(order):
    """Envoie un email de confirmation de commande"""
    subject = f"Confirmation de commande #{order.uid}"
    
    context = {
        'order': order,
        'company_name': 'Online Shop Guinée',
        'company_phone': '+224 XXX XX XX XX',
        'company_email': 'contact@onlineshopgn.com',
    }
    
    # Version HTML
    html_content = render_to_string('orders/emails/order_confirmation.html', context)
    
    # Version texte
    text_content = f"""
    Bonjour {order.customer.first_name} {order.customer.last_name},
    
    Nous avons bien reçu votre commande #{order.uid}.
    
    Détails de la commande :
    - Date : {order.created_at.strftime('%d/%m/%Y %H:%M')}
    - Montant total : {order.total_amount} GNF
    - Méthode de paiement : {order.get_payment_method_display()}
    - Statut : {order.get_status_display()}
    
    Adresse de livraison :
    {order.delivery_address}
    Tél : {order.delivery_phone}
    
    Articles commandés :
    """
    
    for item in order.items.all():
        text_content += f"- {item.product.name} x{item.quantity} = {item.price_at_time * item.quantity} GNF\n"
    
    text_content += f"""
    Sous-total : {order.subtotal} GNF
    Frais de livraison : {order.delivery_fee} GNF
    Total : {order.total_amount} GNF
    
    Merci pour votre achat !
    
    L'équipe Online Shop Guinée
    Tél : +224 XXX XX XX XX
    Email : contact@onlineshopgn.com
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print(f"Erreur envoi email confirmation commande: {e}")
        return False


def send_payment_confirmation_email(order):
    """Envoie un email de confirmation de paiement"""
    subject = f"Paiement confirmé - Commande #{order.uid}"
    
    context = {
        'order': order,
        'company_name': 'Online Shop Guinée',
        'company_phone': '+224 XXX XX XX XX',
        'company_email': 'contact@onlineshopgn.com',
    }
    
    # Version HTML
    html_content = render_to_string('orders/emails/payment_confirmation.html', context)
    
    # Version texte
    text_content = f"""
    Bonjour {order.customer.first_name} {order.customer.last_name},
    
    Votre paiement pour la commande #{order.uid} a été confirmé !
    
    Détails du paiement :
    - Montant payé : {order.total_amount} GNF
    - Méthode : {order.get_payment_method_display()}
    - Date : {order.paid_at.strftime('%d/%m/%Y %H:%M') if order.paid_at else 'N/A'}
    
    Votre commande est maintenant en cours de traitement.
    Vous recevrez un email dès qu'elle sera expédiée.
    
    Merci pour votre confiance !
    
    L'équipe Online Shop Guinée
    Tél : +224 XXX XX XX XX
    Email : contact@onlineshopgn.com
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print(f"Erreur envoi email confirmation paiement: {e}")
        return False


def send_order_shipped_email(order):
    """Envoie un email de notification d'expédition"""
    subject = f"Commande expédiée - #{order.uid}"
    
    context = {
        'order': order,
        'company_name': 'Online Shop Guinée',
        'company_phone': '+224 XXX XX XX XX',
        'company_email': 'contact@onlineshopgn.com',
    }
    
    # Version HTML
    html_content = render_to_string('orders/emails/order_shipped.html', context)
    
    # Version texte
    text_content = f"""
    Bonjour {order.customer.first_name} {order.customer.last_name},
    
    Excellente nouvelle ! Votre commande #{order.uid} a été expédiée.
    
    Détails de l'expédition :
    - Date d'expédition : {timezone.now().strftime('%d/%m/%Y %H:%M')}
    - Adresse de livraison : {order.delivery_address}
    - Téléphone : {order.delivery_phone}
    
    Votre commande devrait arriver dans les 2-3 jours ouvrés.
    
    Si vous avez des questions, n'hésitez pas à nous contacter.
    
    L'équipe Online Shop Guinée
    Tél : +224 XXX XX XX XX
    Email : contact@onlineshopgn.com
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print(f"Erreur envoi email expédition: {e}")
        return False


def send_order_delivered_email(order):
    """Envoie un email de confirmation de livraison"""
    subject = f"Commande livrée - #{order.uid}"
    
    context = {
        'order': order,
        'company_name': 'Online Shop Guinée',
        'company_phone': '+224 XXX XX XX XX',
        'company_email': 'contact@onlineshopgn.com',
    }
    
    # Version HTML
    html_content = render_to_string('orders/emails/order_delivered.html', context)
    
    # Version texte
    text_content = f"""
    Bonjour {order.customer.first_name} {order.customer.last_name},
    
    Votre commande #{order.uid} a été livrée avec succès !
    
    Détails de la livraison :
    - Date de livraison : {order.delivered_at.strftime('%d/%m/%Y %H:%M') if order.delivered_at else 'Aujourd\'hui'}
    - Adresse : {order.delivery_address}
    
    Nous espérons que vous êtes satisfait de votre achat.
    N'hésitez pas à nous laisser un avis ou à nous contacter si vous avez des questions.
    
    Merci d'avoir choisi Online Shop Guinée !
    
    L'équipe Online Shop Guinée
    Tél : +224 XXX XX XX XX
    Email : contact@onlineshopgn.com
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.customer.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print(f"Erreur envoi email livraison: {e}")
        return False


def send_refund_request_email(refund):
    """Envoie un email de confirmation de demande de remboursement"""
    subject = f"Demande de remboursement reçue - #{refund.uid}"
    
    context = {
        'refund': refund,
        'order': refund.order,
        'company_name': 'Online Shop Guinée',
        'company_phone': '+224 XXX XX XX XX',
        'company_email': 'contact@onlineshopgn.com',
    }
    
    # Version HTML
    html_content = render_to_string('orders/emails/refund_request.html', context)
    
    # Version texte
    text_content = f"""
    Bonjour {refund.requested_by.first_name} {refund.requested_by.last_name},
    
    Nous avons bien reçu votre demande de remboursement #{refund.uid}.
    
    Détails de la demande :
    - Commande concernée : #{refund.order.uid}
    - Montant : {refund.amount} GNF
    - Raison : {refund.get_reason_display()}
    - Date de demande : {refund.created_at.strftime('%d/%m/%Y %H:%M')}
    
    Votre demande sera traitée dans les 24-48 heures.
    Vous serez contacté par téléphone ou email pour confirmer les détails.
    
    Merci pour votre patience.
    
    L'équipe Online Shop Guinée
    Tél : +224 XXX XX XX XX
    Email : contact@onlineshopgn.com
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[refund.requested_by.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print(f"Erreur envoi email demande remboursement: {e}")
        return False


def send_refund_processed_email(refund):
    """Envoie un email de confirmation de traitement de remboursement"""
    subject = f"Remboursement traité - #{refund.uid}"
    
    context = {
        'refund': refund,
        'order': refund.order,
        'company_name': 'Online Shop Guinée',
        'company_phone': '+224 XXX XX XX XX',
        'company_email': 'contact@onlineshopgn.com',
    }
    
    # Version HTML
    html_content = render_to_string('orders/emails/refund_processed.html', context)
    
    # Version texte
    text_content = f"""
    Bonjour {refund.requested_by.first_name} {refund.requested_by.last_name},
    
    Votre remboursement #{refund.uid} a été traité.
    
    Détails du remboursement :
    - Commande concernée : #{refund.order.uid}
    - Montant remboursé : {refund.amount} GNF
    - Statut : {refund.get_status_display()}
    - Date de traitement : {refund.processed_at.strftime('%d/%m/%Y %H:%M') if refund.processed_at else 'Aujourd\'hui'}
    """
    
    if refund.status == 'completed':
        text_content += f"""
    
    Le remboursement a été effectué avec succès.
    Le montant devrait apparaître sur votre compte sous 2-5 jours ouvrés.
    """
    elif refund.status == 'failed':
        text_content += f"""
    
    Le remboursement a échoué. Veuillez nous contacter pour plus d'informations.
    """
    elif refund.status == 'cancelled':
        text_content += f"""
    
    Le remboursement a été annulé.
    """
    
    text_content += f"""
    
    Si vous avez des questions, n'hésitez pas à nous contacter.
    
    L'équipe Online Shop Guinée
    Tél : +224 XXX XX XX XX
    Email : contact@onlineshopgn.com
    """
    
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[refund.requested_by.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except Exception as e:
        print(f"Erreur envoi email remboursement traité: {e}")
        return False
