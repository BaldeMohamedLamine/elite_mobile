from django.http import HttpResponse
from django.template.loader import render_to_string
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io
from decimal import Decimal


def generate_invoice_pdf(order):
    """Génère un PDF de facture pour une commande"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#007bff')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#333333')
    )
    
    normal_style = styles['Normal']
    
    # Contenu du PDF
    story = []
    
    # En-tête
    story.append(Paragraph("Online Shop Guinée", title_style))
    story.append(Paragraph("Conakry, Guinée", normal_style))
    story.append(Paragraph("Tél: +224 XXX XX XX XX | Email: contact@onlineshopgn.com", normal_style))
    story.append(Spacer(1, 20))
    
    # Titre de la facture
    story.append(Paragraph("FACTURE", heading_style))
    story.append(Spacer(1, 20))
    
    # Informations de la facture
    invoice_data = [
        ['N° Facture:', f'FACT-{order.uid}'],
        ['Date:', order.created_at.strftime('%d/%m/%Y')],
        ['N° Commande:', str(order.uid)],
        ['Statut:', order.get_payment_status_display()],
        ['Méthode de paiement:', order.get_payment_method_display()],
    ]
    
    invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(invoice_table)
    story.append(Spacer(1, 20))
    
    # Informations client
    story.append(Paragraph("Facturé à:", heading_style))
    client_info = f"""
    <b>{order.customer.first_name} {order.customer.last_name}</b><br/>
    {order.customer.email}<br/>
    {order.delivery_address}<br/>
    Tél: {order.delivery_phone}
    """
    story.append(Paragraph(client_info, normal_style))
    story.append(Spacer(1, 20))
    
    # Articles
    story.append(Paragraph("Articles commandés:", heading_style))
    
    items_data = [['Description', 'Quantité', 'Prix unitaire', 'Total']]
    for item in order.items.all():
        items_data.append([
            f"{item.product.name}\n{item.product.category.name}",
            str(item.quantity),
            f"{item.price_at_time:.0f} GNF",
            f"{item.price_at_time * item.quantity:.0f} GNF"
        ])
    
    items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007bff')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Totaux
    totals_data = [
        ['Sous-total:', f"{order.subtotal:.0f} GNF"],
        ['Frais de livraison:', f"{order.delivery_fee:.0f} GNF"],
        ['TOTAL:', f"{order.total_amount:.0f} GNF"]
    ]
    
    totals_table = Table(totals_data, colWidths=[2*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTSIZE', (1, -1), (1, -1), 14),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#007bff')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(totals_table)
    story.append(Spacer(1, 30))
    
    # Pied de page
    footer_text = """
    Merci pour votre achat !<br/>
    Pour toute question, contactez-nous au +224 XXX XX XX XX ou par email à contact@onlineshopgn.com<br/>
    Document généré automatiquement le {date}
    """.format(date=order.created_at.strftime('%d/%m/%Y %H:%M'))
    
    story.append(Paragraph(footer_text, normal_style))
    
    # Génération du PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def generate_receipt_pdf(order):
    """Génère un PDF de reçu pour une commande"""
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#28a745')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor('#333333')
    )
    
    normal_style = styles['Normal']
    
    # Contenu du PDF
    story = []
    
    # En-tête
    story.append(Paragraph("Online Shop Guinée", title_style))
    story.append(Paragraph("Conakry, Guinée", normal_style))
    story.append(Paragraph("Tél: +224 XXX XX XX XX | Email: contact@onlineshopgn.com", normal_style))
    story.append(Spacer(1, 20))
    
    # Titre du reçu
    story.append(Paragraph("REÇU DE PAIEMENT", heading_style))
    story.append(Spacer(1, 20))
    
    # Informations du reçu
    receipt_date = order.paid_at.strftime('%d/%m/%Y') if order.paid_at else order.created_at.strftime('%d/%m/%Y')
    receipt_data = [
        ['N° Reçu:', f'RECU-{order.uid}'],
        ['Date de paiement:', receipt_date],
        ['N° Commande:', str(order.uid)],
        ['Statut:', 'Payé'],
    ]
    
    receipt_table = Table(receipt_data, colWidths=[2*inch, 3*inch])
    receipt_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(receipt_table)
    story.append(Spacer(1, 20))
    
    # Informations client
    story.append(Paragraph("Client:", heading_style))
    client_info = f"""
    <b>{order.customer.first_name} {order.customer.last_name}</b><br/>
    {order.customer.email}<br/>
    {order.delivery_address}<br/>
    Tél: {order.delivery_phone}
    """
    story.append(Paragraph(client_info, normal_style))
    story.append(Spacer(1, 20))
    
    # Articles
    story.append(Paragraph("Articles achetés:", heading_style))
    
    items_data = [['Description', 'Quantité', 'Prix unitaire', 'Total']]
    for item in order.items.all():
        items_data.append([
            f"{item.product.name}\n{item.product.category.name}",
            str(item.quantity),
            f"{item.price_at_time:.0f} GNF",
            f"{item.price_at_time * item.quantity:.0f} GNF"
        ])
    
    items_table = Table(items_data, colWidths=[3*inch, 1*inch, 1.5*inch, 1.5*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#28a745')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 20))
    
    # Totaux
    totals_data = [
        ['Sous-total:', f"{order.subtotal:.0f} GNF"],
        ['Frais de livraison:', f"{order.delivery_fee:.0f} GNF"],
        ['TOTAL PAYÉ:', f"{order.total_amount:.0f} GNF"]
    ]
    
    totals_table = Table(totals_data, colWidths=[2*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, -1), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTSIZE', (1, -1), (1, -1), 14),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#28a745')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(totals_table)
    story.append(Spacer(1, 20))
    
    # Informations de paiement
    if order.payments.exists():
        story.append(Paragraph("Détails du paiement:", heading_style))
        for payment in order.payments.all():
            payment_info = f"""
            <b>Méthode de paiement:</b> {payment.get_method_display()}<br/>
            <b>Montant payé:</b> {payment.amount:.0f} GNF<br/>
            <b>Date et heure:</b> {payment.created_at.strftime('%d/%m/%Y %H:%M')}<br/>
            """
            if payment.orange_money_phone:
                payment_info += f"<b>Téléphone Orange Money:</b> {payment.orange_money_phone}<br/>"
            if payment.card_last_four:
                payment_info += f"<b>Carte utilisée:</b> **** **** **** {payment.card_last_four}<br/>"
            if payment.cash_received:
                payment_info += f"<b>Montant reçu:</b> {payment.cash_received:.0f} GNF<br/>"
                if payment.cash_change:
                    payment_info += f"<b>Monnaie rendue:</b> {payment.cash_change:.0f} GNF<br/>"
            
            story.append(Paragraph(payment_info, normal_style))
            story.append(Spacer(1, 10))
    
    story.append(Spacer(1, 20))
    
    # Pied de page
    footer_text = """
    <b>Paiement confirmé et reçu !</b><br/>
    Merci pour votre achat. Votre commande sera traitée dans les plus brefs délais.<br/>
    Pour toute question, contactez-nous au +224 XXX XX XX XX ou par email à contact@onlineshopgn.com<br/>
    Reçu généré automatiquement le {date}
    """.format(date=order.created_at.strftime('%d/%m/%Y %H:%M'))
    
    story.append(Paragraph(footer_text, normal_style))
    
    # Génération du PDF
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes


def generate_pdf_response(pdf_bytes, filename):
    """Crée une réponse HTTP pour un PDF"""
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
