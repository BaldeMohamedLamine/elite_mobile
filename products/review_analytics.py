"""
Services d'analytics pour les avis et évaluations
"""
from django.db.models import Avg, Count, Q, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

from .models import Product, ProductReview, ReviewAnalytics, Category

logger = logging.getLogger(__name__)


class ReviewAnalyticsService:
    """Service d'analytics pour les avis"""
    
    @staticmethod
    def get_review_overview():
        """Retourne un aperçu général des avis"""
        total_reviews = ProductReview.objects.filter(status='approved').count()
        total_products = Product.objects.filter(is_active=True).count()
        
        # Note moyenne globale
        avg_rating = ProductReview.objects.filter(status='approved').aggregate(
            avg=Avg('rating')
        )['avg'] or 0
        
        # Répartition par note
        rating_distribution = {}
        for rating in range(1, 6):
            count = ProductReview.objects.filter(
                status='approved',
                rating=rating
            ).count()
            rating_distribution[rating] = count
        
        # Avis récents (7 derniers jours)
        recent_reviews = ProductReview.objects.filter(
            status='approved',
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Avis avec images
        reviews_with_images = ProductReview.objects.filter(
            status='approved',
            images__isnull=False
        ).distinct().count()
        
        # Avis vérifiés
        verified_reviews = ProductReview.objects.filter(
            status='approved',
            is_verified_purchase=True
        ).count()
        
        return {
            'total_reviews': total_reviews,
            'total_products': total_products,
            'average_rating': round(avg_rating, 2),
            'rating_distribution': rating_distribution,
            'recent_reviews': recent_reviews,
            'reviews_with_images': reviews_with_images,
            'verified_reviews': verified_reviews,
            'verification_rate': round(
                (verified_reviews / total_reviews * 100) if total_reviews > 0 else 0, 2
            )
        }
    
    @staticmethod
    def get_product_review_analytics(product_id):
        """Analytics détaillées pour un produit"""
        product = Product.objects.get(id=product_id)
        reviews = product.reviews.filter(status='approved')
        
        # Statistiques de base
        total_reviews = reviews.count()
        avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Répartition par note
        rating_distribution = {}
        for rating in range(1, 6):
            count = reviews.filter(rating=rating).count()
            percentage = (count / total_reviews * 100) if total_reviews > 0 else 0
            rating_distribution[rating] = {
                'count': count,
                'percentage': round(percentage, 2)
            }
        
        # Avis récents
        recent_reviews = reviews.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Avis avec images
        reviews_with_images = reviews.filter(images__isnull=False).distinct().count()
        
        # Avis vérifiés
        verified_reviews = reviews.filter(is_verified_purchase=True).count()
        
        # Mots-clés les plus fréquents
        keywords = ReviewAnalyticsService._extract_keywords(reviews)
        
        return {
            'product': product,
            'total_reviews': total_reviews,
            'average_rating': round(avg_rating, 2),
            'rating_distribution': rating_distribution,
            'recent_reviews': recent_reviews,
            'reviews_with_images': reviews_with_images,
            'verified_reviews': verified_reviews,
            'keywords': keywords[:10],  # Top 10 mots-clés
            'verification_rate': round(
                (verified_reviews / total_reviews * 100) if total_reviews > 0 else 0, 2
            )
        }
    
    @staticmethod
    def _extract_keywords(reviews):
        """Extrait les mots-clés les plus fréquents des avis"""
        # TODO: Implémenter l'extraction de mots-clés
        # Pour l'instant, retourner des mots-clés factices
        return [
            {'word': 'qualité', 'count': 15},
            {'word': 'prix', 'count': 12},
            {'word': 'livraison', 'count': 10},
            {'word': 'emballage', 'count': 8},
            {'word': 'recommandé', 'count': 7},
        ]
    
    @staticmethod
    def get_category_review_analytics():
        """Analytics des avis par catégorie"""
        categories = Category.objects.annotate(
            product_count=Count('products', filter=Q(products__is_active=True)),
            review_count=Count('products__reviews', filter=Q(products__reviews__status='approved')),
            avg_rating=Avg('products__reviews__rating', filter=Q(products__reviews__status='approved')),
            verified_reviews=Count(
                'products__reviews',
                filter=Q(
                    products__reviews__status='approved',
                    products__reviews__is_verified_purchase=True
                )
            )
        ).filter(review_count__gt=0).order_by('-review_count')
        
        return list(categories)
    
    @staticmethod
    def get_review_trends(days=30):
        """Analyse les tendances des avis"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Avis par jour
        daily_reviews = ProductReview.objects.filter(
            status='approved',
            created_at__range=[start_date, end_date]
        ).extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            count=Count('id'),
            avg_rating=Avg('rating')
        ).order_by('day')
        
        # Avis par note
        rating_trends = {}
        for rating in range(1, 6):
            count = ProductReview.objects.filter(
                status='approved',
                rating=rating,
                created_at__range=[start_date, end_date]
            ).count()
            rating_trends[rating] = count
        
        return {
            'daily_reviews': list(daily_reviews),
            'rating_trends': rating_trends,
            'period_days': days
        }
    
    @staticmethod
    def get_top_reviewed_products(limit=10):
        """Retourne les produits les mieux notés"""
        products = Product.objects.filter(
            is_active=True,
            reviews__status='approved'
        ).annotate(
            review_count=Count('reviews', filter=Q(reviews__status='approved')),
            avg_rating=Avg('reviews__rating', filter=Q(reviews__status='approved')),
            verified_reviews=Count(
                'reviews',
                filter=Q(
                    reviews__status='approved',
                    reviews__is_verified_purchase=True
                )
            )
        ).filter(review_count__gte=5).order_by('-avg_rating', '-review_count')[:limit]
        
        return list(products)
    
    @staticmethod
    def get_review_quality_metrics():
        """Métriques de qualité des avis"""
        total_reviews = ProductReview.objects.filter(status='approved').count()
        
        # Avis avec texte (plus de 10 caractères)
        detailed_reviews = ProductReview.objects.filter(
            status='approved',
            content__length__gt=10
        ).count()
        
        # Avis avec images
        reviews_with_images = ProductReview.objects.filter(
            status='approved',
            images__isnull=False
        ).distinct().count()
        
        # Avis vérifiés
        verified_reviews = ProductReview.objects.filter(
            status='approved',
            is_verified_purchase=True
        ).count()
        
        # Avis récents (30 derniers jours)
        recent_reviews = ProductReview.objects.filter(
            status='approved',
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        return {
            'total_reviews': total_reviews,
            'detailed_reviews': detailed_reviews,
            'reviews_with_images': reviews_with_images,
            'verified_reviews': verified_reviews,
            'recent_reviews': recent_reviews,
            'detail_rate': round(
                (detailed_reviews / total_reviews * 100) if total_reviews > 0 else 0, 2
            ),
            'image_rate': round(
                (reviews_with_images / total_reviews * 100) if total_reviews > 0 else 0, 2
            ),
            'verification_rate': round(
                (verified_reviews / total_reviews * 100) if total_reviews > 0 else 0, 2
            )
        }
    
    @staticmethod
    def get_review_insights():
        """Insights et recommandations basés sur les avis"""
        insights = []
        
        # Produits sans avis
        products_without_reviews = Product.objects.filter(
            is_active=True,
            reviews__isnull=True
        ).count()
        
        if products_without_reviews > 0:
            insights.append({
                'type': 'warning',
                'title': 'Produits sans avis',
                'description': f'{products_without_reviews} produits n\'ont aucun avis',
                'action': 'Encourager les clients à laisser des avis'
            })
        
        # Produits avec note faible
        low_rated_products = Product.objects.filter(
            is_active=True,
            reviews__status='approved'
        ).annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__status='approved')),
            review_count=Count('reviews', filter=Q(reviews__status='approved'))
        ).filter(
            avg_rating__lt=3,
            review_count__gte=5
        ).count()
        
        if low_rated_products > 0:
            insights.append({
                'type': 'error',
                'title': 'Produits mal notés',
                'description': f'{low_rated_products} produits ont une note moyenne inférieure à 3/5',
                'action': 'Analyser les avis et améliorer la qualité'
            })
        
        # Avis en attente de modération
        pending_reviews = ProductReview.objects.filter(status='pending').count()
        
        if pending_reviews > 0:
            insights.append({
                'type': 'info',
                'title': 'Avis en attente',
                'description': f'{pending_reviews} avis sont en attente de modération',
                'action': 'Modérer les avis en attente'
            })
        
        return insights


class ReviewModerationService:
    """Service de modération des avis"""
    
    @staticmethod
    def get_moderation_queue():
        """Retourne la file de modération"""
        pending_reviews = ProductReview.objects.filter(
            status='pending'
        ).order_by('created_at')
        
        return list(pending_reviews)
    
    @staticmethod
    def moderate_review(review_id, action, moderator_notes=None):
        """Modère un avis"""
        review = ProductReview.objects.get(id=review_id)
        
        if action == 'approve':
            review.status = 'approved'
        elif action == 'reject':
            review.status = 'rejected'
        
        if moderator_notes:
            review.moderator_notes = moderator_notes
        
        review.moderated_at = timezone.now()
        review.save()
        
        return review
    
    @staticmethod
    def get_moderation_stats():
        """Statistiques de modération"""
        total_pending = ProductReview.objects.filter(status='pending').count()
        total_approved = ProductReview.objects.filter(status='approved').count()
        total_rejected = ProductReview.objects.filter(status='rejected').count()
        
        return {
            'pending': total_pending,
            'approved': total_approved,
            'rejected': total_rejected,
            'total': total_pending + total_approved + total_rejected
        }
