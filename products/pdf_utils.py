"""
Utilitaires pour la génération de PDFs pour les rapports fournisseurs
"""
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.conf import settings
import os
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from PIL import Image as PILImage
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


def generate_supplier_report_pdf(supplier, product_data, report_type, report_title):
    """
    Génère un PDF pour les rapports fournisseurs
    
    Args:
        supplier: Instance du modèle Supplier
        product_data: Liste des données des produits
        report_type: 'sold' ou 'unsold'
        report_title: Titre du rapport
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Style personnalisé pour le titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=TA_CENTER,
        textColor=colors.darkblue
    )
    
    # Style pour les sous-titres
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        textColor=colors.darkblue
    )
    
    # Style pour le texte normal
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=6
    )
    
    # Contenu du document
    story = []
    
    # En-tête
    story.append(Paragraph(report_title, title_style))
    story.append(Spacer(1, 12))
    
    # Informations du fournisseur
    story.append(Paragraph(f"<b>Fournisseur:</b> {supplier.name}", subtitle_style))
    story.append(Paragraph(f"<b>Entreprise:</b> {supplier.company_name}", normal_style))
    story.append(Paragraph(f"<b>Email:</b> {supplier.email}", normal_style))
    story.append(Paragraph(f"<b>Téléphone:</b> {supplier.phone}", normal_style))
    story.append(Spacer(1, 20))
    
    # Statistiques générales
    if report_type == 'sold':
        total_products = len(product_data)
        total_quantity = sum(ps['total_quantity'] for ps in product_data)
        total_amount = sum(ps['total_amount'] for ps in product_data)
        
        stats_data = [
            ['Statistiques', 'Valeur'],
            ['Nombre de produits vendus', str(total_products)],
            ['Quantité totale vendue', str(total_quantity)],
            ['Montant total des ventes', f"{total_amount:,.2f} FCFA"]
        ]
    else:  # unsold
        total_products = len(product_data)
        total_quantity = sum(p['available_quantity'] for p in product_data)
        total_value = sum(p['total_value'] for p in product_data)
        
        stats_data = [
            ['Statistiques', 'Valeur'],
            ['Nombre de produits non vendus', str(total_products)],
            ['Quantité disponible', str(total_quantity)],
            ['Valeur totale du stock', f"{total_value:,.2f} FCFA"]
        ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Tableau des produits
    if report_type == 'sold':
        # En-têtes pour les produits vendus
        table_data = [['Produit', 'Description', 'Quantité', 'Prix Unitaire', 'Total']]
        
        for product_info in product_data:
            product = product_info['product']
            quantity = product_info['total_quantity']
            unit_price = product_info['unit_price']
            total = product_info['total_amount']
            
            # Description tronquée pour le PDF
            description = product.description[:50] + "..." if len(product.description) > 50 else product.description
            
            table_data.append([
                product.name,
                description,
                str(quantity),
                f"{unit_price:,.2f} FCFA",
                f"{total:,.2f} FCFA"
            ])
    else:  # unsold
        # En-têtes pour les produits non vendus
        table_data = [['Produit', 'Description', 'Stock Disponible', 'Prix Unitaire', 'Valeur Totale']]
        
        for product_info in product_data:
            product = product_info['product']
            available_quantity = product_info['available_quantity']
            unit_price = product_info['unit_price']
            total_value = product_info['total_value']
            
            # Description tronquée pour le PDF
            description = product.description[:50] + "..." if len(product.description) > 50 else product.description
            
            table_data.append([
                product.name,
                description,
                str(available_quantity),
                f"{unit_price:,.2f} FCFA",
                f"{total_value:,.2f} FCFA"
            ])
    
    # Créer le tableau
    product_table = Table(table_data, colWidths=[2*inch, 2.5*inch, 1*inch, 1.5*inch, 1.5*inch])
    product_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Description alignée à gauche
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    story.append(Paragraph("Détail des Produits", subtitle_style))
    story.append(product_table)
    
    # Pied de page
    story.append(Spacer(1, 30))
    story.append(Paragraph(f"Rapport généré le {timezone.now().strftime('%d/%m/%Y à %H:%M')}", 
                          ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER)))
    
    # Construire le PDF
    doc.build(story)
    
    # Récupérer le contenu du buffer
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content


def generate_pdf_response(pdf_bytes, filename):
    """
    Génère une réponse HTTP pour un PDF
    """
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
