"""
Vues pour le système de reviews et avis
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from .models import Product, ProductReview, ReviewImage, ReviewHelpfulness, ReviewReport, ReviewAnalytics
from .review_forms import (
    ProductReviewForm, ReviewImageForm, ReviewReportForm, 
    ReviewHelpfulnessForm, ReviewModerationForm, ReviewFilterForm, ReviewSearchForm
)


class ReviewListView(ListView):
    """Vue pour lister les avis d'un produit"""
    model = ProductReview
    template_name = 'products/review_list.html'
    context_object_name = 'reviews'
    paginate_by = 10
    
    def get_queryset(self):
        """Filtrer les avis selon les critères"""
        self.product = get_object_or_404(Product, uid=self.kwargs['product_uid'])
        queryset = self.product.reviews.filter(status='approved')
        
        # Appliquer les filtres
        filter_form = ReviewFilterForm(self.request.GET)
        if filter_form.is_valid():
            rating = filter_form.cleaned_data.get('rating')
            sort_by = filter_form.cleaned_data.get('sort_by', 'newest')
            verified_only = filter_form.cleaned_data.get('verified_only')
            with_images = filter_form.cleaned_data.get('with_images')
            
            if rating:
                queryset = queryset.filter(rating=rating)
            
            if verified_only:
                queryset = queryset.filter(is_verified_purchase=True)
            
            if with_images:
                queryset = queryset.filter(images__isnull=False).distinct()
            
            # Tri
            if sort_by == 'newest':
                queryset = queryset.order_by('-created_at')
            elif sort_by == 'oldest':
                queryset = queryset.order_by('created_at')
            elif sort_by == 'highest_rating':
                queryset = queryset.order_by('-rating', '-created_at')
            elif sort_by == 'lowest_rating':
                queryset = queryset.order_by('rating', '-created_at')
            elif sort_by == 'most_helpful':
                queryset = queryset.order_by('-is_helpful', '-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.product
        context['filter_form'] = ReviewFilterForm(self.request.GET)
        
        # Statistiques des avis
        analytics, created = ReviewAnalytics.objects.get_or_create(product=self.product)
        if created:
            analytics.calculate_stats()
        
        context['analytics'] = analytics
        context['total_reviews'] = self.get_queryset().count()
        
        return context


class ReviewDetailView(DetailView):
    """Vue pour afficher un avis en détail"""
    model = ProductReview
    template_name = 'products/review_detail.html'
    context_object_name = 'review'
    
    def get_object(self):
        """Récupérer l'avis avec ses relations"""
        return get_object_or_404(
            ProductReview.objects.select_related('user', 'product').prefetch_related('images'),
            uid=self.kwargs['review_uid']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        review = self.get_object()
        
        # Vérifier si l'utilisateur a déjà voté
        if self.request.user.is_authenticated:
            try:
                user_vote = ReviewHelpfulness.objects.get(
                    review=review, 
                    user=self.request.user
                )
                context['user_vote'] = user_vote.is_helpful
            except ReviewHelpfulness.DoesNotExist:
                context['user_vote'] = None
        
        # Statistiques de l'avis
        context['helpful_score'] = review.helpful_score
        context['total_votes'] = review.is_helpful + review.is_not_helpful
        
        return context


class ReviewCreateView(LoginRequiredMixin, CreateView):
    """Vue pour créer un nouvel avis"""
    model = ProductReview
    form_class = ProductReviewForm
    template_name = 'products/review_create.html'
    
    def dispatch(self, request, *args, **kwargs):
        """Vérifier que l'utilisateur peut créer un avis"""
        self.product = get_object_or_404(Product, uid=kwargs['product_uid'])
        
        # Vérifier si l'utilisateur a déjà un avis pour ce produit
        if ProductReview.objects.filter(product=self.product, user=request.user).exists():
            messages.warning(request, 'Vous avez déjà laissé un avis pour ce produit.')
            return redirect('products:review_list', product_uid=self.product.uid)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        """Passer l'utilisateur et le produit au formulaire"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['product'] = self.product
        return kwargs
    
    def form_valid(self, form):
        """Sauvegarder l'avis et rediriger"""
        response = super().form_valid(form)
        messages.success(self.request, 'Votre avis a été soumis et sera examiné avant publication.')
        
        # Mettre à jour les analytics
        analytics, created = ReviewAnalytics.objects.get_or_create(product=self.product)
        analytics.calculate_stats()
        
        return response
    
    def get_success_url(self):
        return reverse('products:review_list', kwargs={'product_uid': self.product.uid})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['product'] = self.product
        return context


class ReviewUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Vue pour modifier un avis"""
    model = ProductReview
    form_class = ProductReviewForm
    template_name = 'products/review_update.html'
    
    def test_func(self):
        """Vérifier que l'utilisateur peut modifier cet avis"""
        review = self.get_object()
        return review.user == self.request.user and review.status != 'approved'
    
    def get_form_kwargs(self):
        """Passer l'utilisateur et le produit au formulaire"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['product'] = self.object.product
        return kwargs
    
    def form_valid(self, form):
        """Sauvegarder les modifications"""
        response = super().form_valid(form)
        messages.success(self.request, 'Votre avis a été mis à jour.')
        return response
    
    def get_success_url(self):
        return reverse('products:review_detail', kwargs={'review_uid': self.object.uid})


class ReviewDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Vue pour supprimer un avis"""
    model = ProductReview
    template_name = 'products/review_confirm_delete.html'
    
    def test_func(self):
        """Vérifier que l'utilisateur peut supprimer cet avis"""
        review = self.get_object()
        return review.user == self.request.user
    
    def delete(self, request, *args, **kwargs):
        """Supprimer l'avis et mettre à jour les analytics"""
        review = self.get_object()
        product = review.product
        
        response = super().delete(request, *args, **kwargs)
        
        # Mettre à jour les analytics
        analytics, created = ReviewAnalytics.objects.get_or_create(product=product)
        analytics.calculate_stats()
        
        messages.success(request, 'Votre avis a été supprimé.')
        return response
    
    def get_success_url(self):
        return reverse('products:review_list', kwargs={'product_uid': self.object.product.uid})


@login_required
def review_helpfulness_vote(request, review_uid):
    """Vue AJAX pour voter sur l'utilité d'un avis"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
    
    review = get_object_or_404(ProductReview, uid=review_uid)
    is_helpful = request.POST.get('is_helpful') == 'true'
    
    # Vérifier si l'utilisateur a déjà voté
    vote, created = ReviewHelpfulness.objects.get_or_create(
        review=review,
        user=request.user,
        defaults={'is_helpful': is_helpful}
    )
    
    if not created:
        # L'utilisateur a déjà voté, mettre à jour le vote
        if vote.is_helpful != is_helpful:
            vote.is_helpful = is_helpful
            vote.save()
        else:
            # L'utilisateur annule son vote
            vote.delete()
            return JsonResponse({
                'success': True,
                'action': 'removed',
                'helpful_count': review.is_helpful,
                'not_helpful_count': review.is_not_helpful
            })
    
    # Mettre à jour les compteurs
    review.is_helpful = review.helpfulness_votes.filter(is_helpful=True).count()
    review.is_not_helpful = review.helpfulness_votes.filter(is_helpful=False).count()
    review.save()
    
    return JsonResponse({
        'success': True,
        'action': 'voted',
        'helpful_count': review.is_helpful,
        'not_helpful_count': review.is_not_helpful,
        'user_vote': is_helpful
    })


@login_required
def review_report(request, review_uid):
    """Vue pour signaler un avis"""
    if request.method == 'POST':
        review = get_object_or_404(ProductReview, uid=review_uid)
        form = ReviewReportForm(request.POST)
        
        if form.is_valid():
            # Vérifier si l'utilisateur a déjà signalé cet avis
            if ReviewReport.objects.filter(review=review, reporter=request.user).exists():
                messages.warning(request, 'Vous avez déjà signalé cet avis.')
            else:
                report = form.save(commit=False)
                report.review = review
                report.reporter = request.user
                report.save()
                messages.success(request, 'Votre signalement a été envoyé. Nous l\'examinerons rapidement.')
            
            return redirect('products:review_detail', review_uid=review.uid)
    else:
        form = ReviewReportForm()
    
    review = get_object_or_404(ProductReview, uid=review_uid)
    return render(request, 'products/review_report.html', {
        'form': form,
        'review': review
    })


class ReviewModerationListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Vue pour lister les avis en attente de modération (admin)"""
    model = ProductReview
    template_name = 'products/review_moderation_list.html'
    context_object_name = 'reviews'
    paginate_by = 20
    
    def test_func(self):
        """Vérifier que l'utilisateur est un modérateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_queryset(self):
        """Filtrer les avis selon le statut"""
        status = self.request.GET.get('status', 'pending')
        queryset = ProductReview.objects.select_related('user', 'product')
        
        if status == 'pending':
            queryset = queryset.filter(status='pending')
        elif status == 'approved':
            queryset = queryset.filter(status='approved')
        elif status == 'rejected':
            queryset = queryset.filter(status='rejected')
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_status'] = self.request.GET.get('status', 'pending')
        context['status_choices'] = ProductReview.STATUS_CHOICES
        return context


class ReviewModerationDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Vue pour modérer un avis (admin)"""
    model = ProductReview
    template_name = 'products/review_moderation_detail.html'
    context_object_name = 'review'
    
    def test_func(self):
        """Vérifier que l'utilisateur est un modérateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['moderation_form'] = ReviewModerationForm(instance=self.object)
        context['reports'] = self.object.reports.all()
        return context


@login_required
def review_moderate(request, review_uid):
    """Vue pour approuver/rejeter un avis (admin)"""
    if not (request.user.is_staff or request.user.is_superuser):
        raise PermissionDenied
    
    review = get_object_or_404(ProductReview, uid=review_uid)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            review.approve(moderator=request.user)
            messages.success(request, 'L\'avis a été approuvé.')
        elif action == 'reject':
            notes = request.POST.get('moderation_notes', '')
            review.reject(moderator=request.user, notes=notes)
            messages.success(request, 'L\'avis a été rejeté.')
        
        # Mettre à jour les analytics
        analytics, created = ReviewAnalytics.objects.get_or_create(product=review.product)
        analytics.calculate_stats()
        
        return redirect('products:review_moderation_list')
    
    return redirect('products:review_moderation_detail', review_uid=review.uid)


class ReviewAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Vue pour afficher les analytics des avis (admin)"""
    model = Product
    template_name = 'products/review_analytics.html'
    context_object_name = 'product'
    
    def test_func(self):
        """Vérifier que l'utilisateur est un modérateur"""
        return self.request.user.is_staff or self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        product = self.get_object()
        
        # Récupérer ou créer les analytics
        analytics, created = ReviewAnalytics.objects.get_or_create(product=product)
        if created:
            analytics.calculate_stats()
        
        context['analytics'] = analytics
        context['recent_reviews'] = product.reviews.filter(status='approved').order_by('-created_at')[:10]
        context['reports'] = ReviewReport.objects.filter(review__product=product).order_by('-created_at')[:10]
        
        return context


def review_search(request):
    """Vue pour rechercher dans les avis"""
    form = ReviewSearchForm(request.GET)
    reviews = []
    
    if form.is_valid():
        query = form.cleaned_data.get('query')
        if query:
            reviews = ProductReview.objects.filter(
                Q(title__icontains=query) | Q(content__icontains=query),
                status='approved'
            ).select_related('user', 'product').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(reviews, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'products/review_search.html', {
        'form': form,
        'page_obj': page_obj,
        'query': request.GET.get('query', '')
    })