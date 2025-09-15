"""
Commande Django pour vérifier les niveaux de stock
Usage: python manage.py check_stock_levels
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from products.stock_services import StockAlertService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Vérifie les niveaux de stock et crée des alertes si nécessaire'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Affiche des informations détaillées',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simule la vérification sans créer d\'alertes',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        dry_run = options['dry_run']
        
        if verbose:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Début de la vérification des stocks - {timezone.now().strftime("%d/%m/%Y %H:%M:%S")}'
                )
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('Mode simulation activé - aucune alerte ne sera créée')
            )
        
        try:
            if dry_run:
                # En mode simulation, on compte juste les produits qui auraient des alertes
                from products.models import Product
                from django.db.models import F
                
                low_stock_count = Product.objects.filter(
                    is_active=True,
                    quantity__lte=F('min_stock_level')
                ).count()
                
                out_of_stock_count = Product.objects.filter(
                    is_active=True,
                    quantity=0
                ).count()
                
                overstock_count = Product.objects.filter(
                    is_active=True,
                    quantity__gt=F('max_stock_level')
                ).count()
                
                total_alerts = low_stock_count + out_of_stock_count + overstock_count
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Simulation terminée. {total_alerts} alertes seraient créées:'
                    )
                )
                self.stdout.write(f'  - Stock faible: {low_stock_count}')
                self.stdout.write(f'  - Rupture de stock: {out_of_stock_count}')
                self.stdout.write(f'  - Surstock: {overstock_count}')
                
            else:
                # Vérification réelle
                alerts_created = StockAlertService.check_stock_levels()
                
                if alerts_created > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Vérification terminée. {alerts_created} nouvelles alertes créées.'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS('Vérification terminée. Aucune nouvelle alerte nécessaire.')
                    )
                
                if verbose:
                    # Afficher les statistiques
                    from products.stock_services import StockMovementService
                    summary = StockMovementService.get_stock_summary()
                    
                    self.stdout.write('\nStatistiques des stocks:')
                    self.stdout.write(f'  - Produits actifs: {summary["total_products"]}')
                    self.stdout.write(f'  - Stock faible: {summary["low_stock_products"]}')
                    self.stdout.write(f'  - Rupture de stock: {summary["out_of_stock_products"]}')
                    self.stdout.write(f'  - Surstock: {summary["overstock_products"]}')
                    self.stdout.write(f'  - Alertes actives: {summary["active_alerts"]}')
                    self.stdout.write(f'  - Valeur totale du stock: {summary["total_stock_value"]:,.0f} GNF')
        
        except Exception as e:
            logger.error(f'Erreur lors de la vérification des stocks: {e}')
            self.stdout.write(
                self.style.ERROR(f'Erreur lors de la vérification: {str(e)}')
            )
            raise
