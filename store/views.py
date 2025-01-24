from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q
from .models import Product, Category, Profile
from .forms import SignUpForm, UpdateUserForm, ChangePasswordForm, UserInfoForm
from payment.forms import ShippingForm
from payment.models import ShippingAddress
from cart.cart import Cart
import json


# Signals para criar Profile automaticamente
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


# Views
def cart_add(request):
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        product_qty = request.POST.get('product_qty')

        if not product_id or not product_qty.isdigit():
            return JsonResponse({'error': 'Produto ou quantidade inválida!'}, status=400)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Produto não encontrado!'}, status=404)

        cart = request.session.get('cart', {})
        cart[product_id] = cart.get(product_id, 0) + int(product_qty)
        request.session['cart'] = cart
        request.session.modified = True

        return JsonResponse({'message': 'Produto adicionado ao carrinho!', 'qty': sum(cart.values())})

    return JsonResponse({'error': 'Método não permitido'}, status=405)


def _sync_saved_cart(request, user):
    """Sincroniza o carrinho salvo no banco com a sessão atual."""
    try:
        profile = Profile.objects.get(user=user)
        saved_cart = json.loads(profile.old_cart) if profile.old_cart else {}
    except Profile.DoesNotExist:
        saved_cart = {}

    session_cart = request.session.get('cart', {})
    for key, value in saved_cart.items():
        session_cart[key] = session_cart.get(key, 0) + value

    request.session['cart'] = session_cart
    request.session.modified = True


def search(request):
    if request.method == "POST":
        searched = request.POST['searched']
        searched = Product.objects.filter(Q(name__icontains=searched) | Q(description__icontains=searched))

        if not searched:
            messages.error(request, "O produto não foi encontrado. Por favor, tente novamente.")
            return render(request, "search.html", {})
        else:
            return render(request, "search.html", {'searched': searched})
    return render(request, "search.html", {})



def update_info(request):
    if request.user.is_authenticated:
        # Obtenha o usuário atual
        current_user = Profile.objects.get(user=request.user)

        # Tente recuperar ou criar o ShippingAddress
        shipping_user, created = ShippingAddress.objects.get_or_create(user=request.user)

        # Formulários com instâncias existentes
        form = UserInfoForm(request.POST or None, instance=current_user)
        shipping_form = ShippingForm(request.POST or None, instance=shipping_user)

        if request.method == "POST":
            if form.is_valid() and shipping_form.is_valid():
                form.save()
                shipping_form.save()
                messages.success(request, "Suas informações foram atualizadas com sucesso!")
                return redirect('home')

        return render(request, "update_info.html", {'form': form, 'shipping_form': shipping_form})
    else:
        messages.error(request, "Você precisa estar logado para acessar essa página.")
        return redirect('login')



def update_password(request):
    if request.user.is_authenticated:
        current_user = request.user
        if request.method == 'POST':
            form = ChangePasswordForm(current_user, request.POST)
            if form.is_valid():
                form.save()
                login(request, current_user)
                messages.success(request, "Sua senha foi atualizada com sucesso!")
                return redirect('update_user')
            else:
                for error in form.errors.values():
                    messages.error(request, error)
                return redirect('update_password')

        form = ChangePasswordForm(current_user)
        return render(request, "update_password.html", {'form': form})

    messages.error(request, "Você precisa estar logado para acessar esta página.")
    return redirect('home')


def update_user(request):
    if request.user.is_authenticated:
        current_user = User.objects.get(id=request.user.id)
        user_form = UpdateUserForm(request.POST or None, instance=current_user)

        if user_form.is_valid():
            user_form.save()
            login(request, current_user)
            messages.success(request, "Informações do usuário atualizadas com sucesso!")
            return redirect('home')

        return render(request, "update_user.html", {'user_form': user_form})

    messages.error(request, "Você precisa estar logado para acessar esta página.")
    return redirect('home')


def category_summary(request):
    categories = Category.objects.all()
    return render(request, 'category_summary.html', {"categories": categories})


def category(request, foo):
    foo = foo.replace('-', ' ')
    try:
        category = Category.objects.get(name__iexact=foo)
        products = Product.objects.filter(category=category)
        return render(request, 'category.html', {'products': products, 'category': category})
    except Category.DoesNotExist:
        messages.error(request, "Essa categoria não existe!")
        return redirect('category_summary')


def product(request, pk):
    product = Product.objects.get(id=pk)
    return render(request, 'product.html', {'product': product})


def home(request):
    products = Product.objects.all()
    return render(request, 'home.html', {'products': products})


def about(request):
    return render(request, 'about.html', {})


def login_user(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            _sync_saved_cart(request, user)
            messages.success(request, "Você foi logado com sucesso!")
            return redirect('home')

        messages.error(request, "Erro ao autenticar. Por favor, tente novamente.")
        return redirect('login')

    return render(request, 'login.html', {})


def logout_user(request):
    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.old_cart = json.dumps(request.session.get('cart', {}))
        profile.save()

    logout(request)
    messages.success(request, "Você foi deslogado com sucesso!")
    return redirect('home')


def register_user(request):
    form = SignUpForm()
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            password = form.cleaned_data['password1']
            user = authenticate(username=username, password=password)
            login(request, user)
            messages.success(request, "Usuário registrado com sucesso! Por favor, atualize suas informações.")
            return redirect('update_info')

        messages.error(request, "Erro ao registrar usuário. Por favor, tente novamente.")
        return redirect('register')

    return render(request, 'register.html', {'form': form})
