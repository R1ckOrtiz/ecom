from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_summary, name="cart_summary"),  # Página de resumo do carrinho
    path('add/', views.cart_add, name="cart_add"),  # Rota para adicionar itens
    path('delete/', views.cart_delete, name="cart_delete"),  # Rota para deletar itens
    path('update/', views.cart_update, name="cart_update"),  # Rota para atualizar itens
]
