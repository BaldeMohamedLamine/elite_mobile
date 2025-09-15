"""
Services de monitoring et d'alertes
"""
import logging
import time
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Q
from django.contrib.auth import get_user_model

from .models import Product, StockAlert, ProductReview
from .cache_services import CacheService

logger = logging.getLogger(__name__)
User = get_user_model()


class MonitoringService:
    """Service de monitoring de l'application"""
    
    @staticmethod
    def check_system_health():
        """Vérifie la santé générale du système"""
        health_status = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'checks': {}
        }
        
        # Vérification de la base de données
        try:
            Product.objects.count()
            health_status['checks']['database'] = {
                'status': 'healthy',
                'message': 'Database connection successful'
            }
        except Exception as e:
            health_status['checks']['database'] = {
                'status': 'unhealthy',
                'message': f'Database error: {str(e)}'
            }
            health_status['status'] = 'unhealthy'
        
        # Vérification du cache Redis
        try:
            cache.set('health_check', 'ok', 10)
            cache_result = cache.get('health_check')
            if cache_result == 'ok':
                health_status['checks']['cache'] = {
                    'status': 'healthy',
                    'message': 'Cache system working'
                }
            else:
                health_status['checks']['cache'] = {
                    'status': 'unhealthy',
                    'message': 'Cache system not responding'
                }
                health_status['status'] = 'unhealthy'
        except Exception as e:
            health_status['checks']['cache'] = {
                'status': 'unhealthy',
                'message': f'Cache error: {str(e)}'
            }
            health_status['status'] = 'unhealthy'
        
        # Vérification des stocks
        try:
            low_stock_count = Product.objects.filter(
                is_active=True,
                quantity__lte=models.F('min_stock_level')
            ).count()
            
            out_of_stock_count = Product.objects.filter(
                is_active=True,
                quantity=0
            ).count()
            
            health_status['checks']['inventory'] = {
                'status': 'healthy' if low_stock_count < 10 and out_of_stock_count < 5 else 'warning',
                'message': f'Low stock: {low_stock_count}, Out of stock: {out_of_stock_count}',
                'low_stock_count': low_stock_count,
                'out_of_stock_count': out_of_stock_count
            }
            
            if low_stock_count > 20 or out_of_stock_count > 10:
                health_status['status'] = 'unhealthy'
        except Exception as e:
            health_status['checks']['inventory'] = {
                'status': 'unhealthy',
                'message': f'Inventory check error: {str(e)}'
            }
            health_status['status'] = 'unhealthy'
        
        # Vérification des avis en attente
        try:
            pending_reviews = ProductReview.objects.filter(status='pending').count()
            health_status['checks']['reviews'] = {
                'status': 'healthy' if pending_reviews < 50 else 'warning',
                'message': f'Pending reviews: {pending_reviews}',
                'pending_reviews': pending_reviews
            }
            
            if pending_reviews > 100:
                health_status['status'] = 'unhealthy'
        except Exception as e:
            health_status['checks']['reviews'] = {
                'status': 'unhealthy',
                'message': f'Reviews check error: {str(e)}'
            }
            health_status['status'] = 'unhealthy'
        
        return health_status
    
    @staticmethod
    def get_performance_metrics():
        """Récupère les métriques de performance"""
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'database': {},
            'cache': {},
            'application': {}
        }
        
        # Métriques de base de données
        try:
            start_time = time.time()
            Product.objects.count()
            db_time = time.time() - start_time
            
            metrics['database'] = {
                'query_time': round(db_time * 1000, 2),  # en millisecondes
                'total_products': Product.objects.count(),
                'active_products': Product.objects.filter(is_active=True).count(),
                'total_orders': 0,  # TODO: Implémenter quand le modèle Order sera disponible
                'total_reviews': ProductReview.objects.count()
            }
        except Exception as e:
            metrics['database'] = {'error': str(e)}
        
        # Métriques de cache
        try:
            cache_hits = cache.get('cache_hits', 0)
            cache_misses = cache.get('cache_misses', 0)
            total_requests = cache_hits + cache_misses
            hit_rate = (cache_hits / total_requests * 100) if total_requests > 0 else 0
            
            metrics['cache'] = {
                'hit_rate': round(hit_rate, 2),
                'total_requests': total_requests,
                'cache_hits': cache_hits,
                'cache_misses': cache_misses
            }
        except Exception as e:
            metrics['cache'] = {'error': str(e)}
        
        # Métriques d'application
        try:
            metrics['application'] = {
                'active_users': User.objects.filter(is_active=True).count(),
                'total_users': User.objects.count(),
                'recent_orders': 0,  # TODO: Implémenter quand le modèle Order sera disponible
                'recent_reviews': ProductReview.objects.filter(
                    created_at__gte=timezone.now() - timedelta(days=1)
                ).count()
            }
        except Exception as e:
            metrics['application'] = {'error': str(e)}
        
        return metrics
    
    @staticmethod
    def check_security_alerts():
        """Vérifie les alertes de sécurité"""
        alerts = []
        
        # Vérifier les tentatives de connexion échouées
        try:
            failed_logins = cache.get('failed_logins', 0)
            if failed_logins > 10:
                alerts.append({
                    'type': 'security',
                    'severity': 'high',
                    'message': f'High number of failed login attempts: {failed_logins}',
                    'timestamp': timezone.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Error checking failed logins: {e}")
        
        # Vérifier les requêtes suspectes
        try:
            suspicious_requests = cache.get('suspicious_requests', 0)
            if suspicious_requests > 5:
                alerts.append({
                    'type': 'security',
                    'severity': 'medium',
                    'message': f'Suspicious requests detected: {suspicious_requests}',
                    'timestamp': timezone.now().isoformat()
                })
        except Exception as e:
            logger.error(f"Error checking suspicious requests: {e}")
        
        return alerts


class AlertService:
    """Service d'alertes et notifications"""
    
    @staticmethod
    def send_system_alert(alert_type, message, severity='medium'):
        """Envoie une alerte système"""
        try:
            # Enregistrer l'alerte dans le cache
            alert_key = f"system_alert:{timezone.now().timestamp()}"
            alert_data = {
                'type': alert_type,
                'message': message,
                'severity': severity,
                'timestamp': timezone.now().isoformat()
            }
            cache.set(alert_key, alert_data, 86400)  # 24 heures
            
            # Envoyer un email si la sévérité est élevée
            if severity in ['high', 'critical']:
                AlertService._send_email_alert(alert_data)
            
            logger.warning(f"System alert: {alert_type} - {message}")
            
        except Exception as e:
            logger.error(f"Error sending system alert: {e}")
    
    @staticmethod
    def _send_email_alert(alert_data):
        """Envoie une alerte par email"""
        try:
            subject = f"[ALERTE] {alert_data['type'].upper()} - {alert_data['severity'].upper()}"
            message = f"""
            Type: {alert_data['type']}
            Sévérité: {alert_data['severity']}
            Message: {alert_data['message']}
            Timestamp: {alert_data['timestamp']}
            
            Veuillez vérifier le système immédiatement.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [settings.ADMIN_EMAIL] if hasattr(settings, 'ADMIN_EMAIL') else [],
                fail_silently=False,
            )
        except Exception as e:
            logger.error(f"Error sending email alert: {e}")
    
    @staticmethod
    def get_recent_alerts(limit=10):
        """Récupère les alertes récentes"""
        try:
            # Récupérer les clés d'alertes du cache
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            alert_keys = redis_conn.keys("system_alert:*")
            
            alerts = []
            for key in alert_keys[-limit:]:  # Dernières alertes
                alert_data = cache.get(key)
                if alert_data:
                    alerts.append(alert_data)
            
            return sorted(alerts, key=lambda x: x['timestamp'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []


class PerformanceMonitoringService:
    """Service de monitoring des performances"""
    
    @staticmethod
    def track_request_performance(request, response):
        """Enregistre les performances d'une requête"""
        try:
            if hasattr(request, '_start_time'):
                duration = time.time() - request._start_time
                
                # Enregistrer les requêtes lentes
                if duration > 2.0:  # Plus de 2 secondes
                    PerformanceMonitoringService._log_slow_request(request, duration)
                
                # Mettre à jour les métriques de cache
                if hasattr(response, '_cache_hit'):
                    if response._cache_hit:
                        cache.incr('cache_hits', 1)
                    else:
                        cache.incr('cache_misses', 1)
                
        except Exception as e:
            logger.error(f"Error tracking request performance: {e}")
    
    @staticmethod
    def _log_slow_request(request, duration):
        """Enregistre une requête lente"""
        try:
            slow_request_data = {
                'path': request.path,
                'method': request.method,
                'duration': duration,
                'timestamp': timezone.now().isoformat(),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'ip_address': request.META.get('REMOTE_ADDR', '')
            }
            
            # Enregistrer dans le cache
            slow_request_key = f"slow_request:{timezone.now().timestamp()}"
            cache.set(slow_request_key, slow_request_data, 86400)
            
            logger.warning(f"Slow request: {request.path} took {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Error logging slow request: {e}")
    
    @staticmethod
    def get_slow_requests(limit=10):
        """Récupère les requêtes lentes récentes"""
        try:
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            slow_request_keys = redis_conn.keys("slow_request:*")
            
            slow_requests = []
            for key in slow_request_keys[-limit:]:
                request_data = cache.get(key)
                if request_data:
                    slow_requests.append(request_data)
            
            return sorted(slow_requests, key=lambda x: x['timestamp'], reverse=True)
        except Exception as e:
            logger.error(f"Error getting slow requests: {e}")
            return []


class SecurityMonitoringService:
    """Service de monitoring de sécurité"""
    
    @staticmethod
    def track_failed_login(ip_address, username=None):
        """Enregistre une tentative de connexion échouée"""
        try:
            # Incrémenter le compteur de connexions échouées
            cache.incr('failed_logins', 1)
            
            # Enregistrer les détails
            failed_login_key = f"failed_login:{ip_address}:{timezone.now().timestamp()}"
            failed_login_data = {
                'ip_address': ip_address,
                'username': username,
                'timestamp': timezone.now().isoformat()
            }
            cache.set(failed_login_key, failed_login_data, 3600)  # 1 heure
            
            # Vérifier si le seuil est dépassé
            failed_logins = cache.get('failed_logins', 0)
            if failed_logins > 10:
                AlertService.send_system_alert(
                    'security',
                    f'High number of failed login attempts from {ip_address}',
                    'high'
                )
            
        except Exception as e:
            logger.error(f"Error tracking failed login: {e}")
    
    @staticmethod
    def track_suspicious_request(request):
        """Enregistre une requête suspecte"""
        try:
            # Incrémenter le compteur de requêtes suspectes
            cache.incr('suspicious_requests', 1)
            
            # Enregistrer les détails
            suspicious_request_key = f"suspicious_request:{timezone.now().timestamp()}"
            suspicious_request_data = {
                'path': request.path,
                'method': request.method,
                'ip_address': request.META.get('REMOTE_ADDR', ''),
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'timestamp': timezone.now().isoformat()
            }
            cache.set(suspicious_request_key, suspicious_request_data, 3600)
            
            # Vérifier si le seuil est dépassé
            suspicious_requests = cache.get('suspicious_requests', 0)
            if suspicious_requests > 5:
                AlertService.send_system_alert(
                    'security',
                    f'Suspicious requests detected from {request.META.get("REMOTE_ADDR", "")}',
                    'medium'
                )
            
        except Exception as e:
            logger.error(f"Error tracking suspicious request: {e}")
    
    @staticmethod
    def reset_security_counters():
        """Remet à zéro les compteurs de sécurité"""
        try:
            cache.delete('failed_logins')
            cache.delete('suspicious_requests')
            logger.info("Security counters reset")
        except Exception as e:
            logger.error(f"Error resetting security counters: {e}")
