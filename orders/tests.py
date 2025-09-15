"""
Tests pour l'application orders
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from decimal import Decimal
import json

from .models import Cart, CartItem, Order, OrderItem, Payment
from products.models import Product, Category
from .validators import validate_phone_number, validate_card_number, validate_positive_decimal

User = get_user_model()


class OrderModelTests(TestCase):
    """Tests pour les modèles de commandes"""
    
    def setUp(self):
        """Configuration des tests"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product',
            price=Decimal('100.00'),
            category=self.category,
            quantity=10
        )
    
    def test_cart_creation(self):
        """Test de création d'un panier"""
        cart = Cart.objects.create(owner=self.user)
        self.assertEqual(cart.owner, self.user)
        self.assertIsNotNone(cart.uid)
    
    def test_cart_item_creation(self):
        """Test de création d'un article de panier"""
        cart = Cart.objects.create(owner=self.user)
        cart_item = CartItem.objects.create(
            product=self.product,
            cart=cart,
            quantity=2
        )
        self.assertEqual(cart_item.product, self.product)
        self.assertEqual(cart_item.quantity, 2)
    
    def test_order_creation(self):
        """Test de création d'une commande"""
        order = Order.objects.create(
            customer=self.user,
            payment_method='cash_on_delivery',
            delivery_address='Test Address',
            delivery_phone='+224612345678',
            subtotal=Decimal('100.00'),
            total_amount=Decimal('100.00')
        )
        self.assertEqual(order.customer, self.user)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.payment_status, 'pending')
    
    def test_order_item_creation(self):
        """Test de création d'un article de commande"""
        order = Order.objects.create(
            customer=self.user,
            payment_method='cash_on_delivery',
            delivery_address='Test Address',
            delivery_phone='+224612345678',
            subtotal=Decimal('100.00'),
            total_amount=Decimal('100.00')
        )
        order_item = OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=1,
            price_at_time=Decimal('100.00')
        )
        self.assertEqual(order_item.order, order)
        self.assertEqual(order_item.product, self.product)
        self.assertEqual(order_item.quantity, 1)


class ValidatorTests(TestCase):
    """Tests pour les validateurs"""
    
    def test_validate_phone_number_valid(self):
        """Test de validation de numéros de téléphone valides"""
        valid_phones = ['+224612345678', '612345678']
        for phone in valid_phones:
            try:
                validate_phone_number(phone)
            except ValidationError:
                self.fail(f"validate_phone_number raised ValidationError for {phone}")
    
    def test_validate_phone_number_invalid(self):
        """Test de validation de numéros de téléphone invalides"""
        invalid_phones = ['123456789', '+224123', '61234567', 'invalid']
        for phone in invalid_phones:
            with self.assertRaises(ValidationError):
                validate_phone_number(phone)
    
    def test_validate_card_number_valid(self):
        """Test de validation de numéros de carte valides"""
        # Numéro de carte de test valide (algorithme de Luhn)
        valid_card = '4111111111111111'
        try:
            validate_card_number(valid_card)
        except ValidationError:
            self.fail("validate_card_number raised ValidationError for valid card")
    
    def test_validate_card_number_invalid(self):
        """Test de validation de numéros de carte invalides"""
        invalid_cards = ['1234567890123456', '123', 'invalid']
        for card in invalid_cards:
            with self.assertRaises(ValidationError):
                validate_card_number(card)
    
    def test_validate_positive_decimal_valid(self):
        """Test de validation de décimaux positifs valides"""
        valid_values = [Decimal('100.00'), Decimal('0.01'), 100, 0.5]
        for value in valid_values:
            try:
                validate_positive_decimal(value)
            except ValidationError:
                self.fail(f"validate_positive_decimal raised ValidationError for {value}")
    
    def test_validate_positive_decimal_invalid(self):
        """Test de validation de décimaux positifs invalides"""
        invalid_values = [Decimal('-100.00'), Decimal('0.00'), -100, 0]
        for value in invalid_values:
            with self.assertRaises(ValidationError):
                validate_positive_decimal(value)


@override_settings(
    TESTING=True,  # Désactiver les middlewares de sécurité pendant les tests
    RATE_LIMIT_MAX_REQUESTS=1000,
    RATE_LIMIT_TIME_WINDOW=60
)
class OrderViewTests(TestCase):
    """Tests pour les vues de commandes"""
    
    def setUp(self):
        """Configuration des tests"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            is_active=True  # Activer l'utilisateur
        )
        self.category = Category.objects.create(name='Test Category')
        self.product = Product.objects.create(
            name='Test Product',
            price=Decimal('100.00'),
            category=self.category,
            quantity=10
        )
    
    def test_add_to_cart_authenticated(self):
        """Test d'ajout au panier pour un utilisateur authentifié"""
        self.client.login(email='test@example.com', password='testpass123')
        
        data = {
            'product_uid': str(self.product.uid),
            'quantity': 2
        }
        
        response = self.client.post(
            reverse('orders:add_to_cart'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
    
    def test_add_to_cart_unauthenticated(self):
        """Test d'ajout au panier pour un utilisateur non authentifié"""
        data = {
            'product_uid': str(self.product.uid),
            'quantity': 2
        }
        
        response = self.client.post(
            reverse('orders:add_to_cart'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        # L'utilisateur non authentifié devrait recevoir une erreur 400
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
    
    def test_add_to_cart_invalid_data(self):
        """Test d'ajout au panier avec des données invalides"""
        self.client.login(email='test@example.com', password='testpass123')
        
        # Test avec quantité négative
        data = {
            'product_uid': str(self.product.uid),
            'quantity': -1
        }
        
        response = self.client.post(
            reverse('orders:add_to_cart'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
    
    def test_add_to_cart_insufficient_stock(self):
        """Test d'ajout au panier avec stock insuffisant"""
        self.client.login(email='test@example.com', password='testpass123')
        
        data = {
            'product_uid': str(self.product.uid),
            'quantity': 15  # Plus que le stock disponible (10)
        }
        
        response = self.client.post(
            reverse('orders:add_to_cart'),
            data=json.dumps(data),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.content)
        self.assertFalse(response_data['success'])
        self.assertIn('Stock insuffisant', response_data['message'])


@override_settings(
    TESTING=False,  # Activer les middlewares de sécurité pour les tests de sécurité
    RATE_LIMIT_MAX_REQUESTS=2,  # Limite très basse pour tester le rate limiting
    RATE_LIMIT_TIME_WINDOW=60
)
class SecurityTests(TestCase):
    """Tests de sécurité"""
    
    def setUp(self):
        """Configuration des tests"""
        self.client = Client()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_rate_limiting(self):
        """Test du rate limiting"""
        # Faire plusieurs requêtes rapides
        for i in range(3):  # Plus que la limite de 2
            response = self.client.get('/')
            if response.status_code == 403:
                # Vérifier que c'est bien le rate limiting qui bloque
                content = response.content.decode()
                if 'Trop de requêtes' in content or 'Access denied' in content:
                    break
        else:
            self.fail("Rate limiting not working")
    
    def test_sql_injection_protection(self):
        """Test de protection contre l'injection SQL"""
        malicious_payload = "'; DROP TABLE orders_order; --"
        
        response = self.client.get(f'/?search={malicious_payload}')
        # La requête ne devrait pas causer d'erreur 500
        self.assertNotEqual(response.status_code, 500)
    
    def test_xss_protection(self):
        """Test de protection contre XSS"""
        xss_payload = "<script>alert('XSS')</script>"
        
        response = self.client.get(f'/?search={xss_payload}')
        # Le contenu ne devrait pas contenir le script
        self.assertNotIn('<script>', response.content.decode())