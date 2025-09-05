from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .models import Product, Category, Cart, Order, OrderItem
from .forms import SignUpForm, LoginForm, CheckoutForm
import requests
import razorpay
from django.conf import settings
import json
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse

# Initialize Razorpay client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def home(request):
    # Get all products and categories
    products = Product.objects.all()
    categories = Category.objects.all()
    
    # Filter by category if specified
    category_id = request.GET.get('category')
    if category_id:
        products = products.filter(category_id=category_id)
    
    # Limit to 100 products
    products = products[:100]
    
    context = {
        'products': products,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None
    }
    return render(request, 'shop/home.html', context)

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    related_products = Product.objects.filter(category=product.category).exclude(id=product.id)[:4]
    context = {
        'product': product,
        'related_products': related_products,
    }
    return render(request, 'shop/product_detail.html', context)

@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item, created = Cart.objects.get_or_create(
        user=request.user,
        product=product,
        defaults={'quantity': 1}
    )
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect('cart')

@login_required
def remove_from_cart(request, cart_id):
    cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
    cart_item.delete()
    return redirect('cart')

@login_required
def update_cart(request, cart_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(Cart, id=cart_id, user=request.user)
        quantity = int(request.POST.get('quantity', 1))
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
    return redirect('cart')

@login_required
def cart(request):
    cart_items = Cart.objects.filter(user=request.user)
    total = sum(item.total_price() for item in cart_items)
    context = {
        'cart_items': cart_items,
        'total': total,
    }
    return render(request, 'shop/cart.html', context)

@login_required
def checkout(request):
    cart_items = Cart.objects.filter(user=request.user)
    if not cart_items.exists():
        return redirect('cart')
    
    total = sum(item.total_price() for item in cart_items)
    
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            # Create order
            order = Order.objects.create(
                user=request.user,
                total_amount=total,
                razorpay_order_id='temp_' + str(request.user.id) + '_' + str(cart_items.first().id)
            )
            
            # Create order items
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            
            # Create Razorpay order
            razorpay_order = client.order.create({
                'amount': int(total * 100),  # Razorpay expects amount in paise
                'currency': 'INR',
                'receipt': f'order_{order.id}',
                'payment_capture': '1'
            })
            
            order.razorpay_order_id = razorpay_order['id']
            order.save()
            
            context = {
                'order': order,
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount': int(total * 100),
                'currency': 'INR',
                'name': request.user.username,
                'email': request.user.email,
            }
            return render(request, 'shop/payment.html', context)
    else:
        form = CheckoutForm()
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'total': total,
    }
    return render(request, 'shop/checkout.html', context)

@csrf_exempt
def payment_success(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        order_id = data.get('razorpay_order_id')
        payment_id = data.get('razorpay_payment_id')
        signature = data.get('razorpay_signature')
        
        try:
            order = Order.objects.get(razorpay_order_id=order_id)
            
            # Verify payment signature
            params_dict = {
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': signature
            }
            
            try:
                client.utility.verify_payment_signature(params_dict)
                order.payment_status = 'completed'
                order.save()
                
                # Clear the cart
                Cart.objects.filter(user=request.user).delete()
                
                return JsonResponse({'status': 'success'})
            except:
                order.payment_status = 'failed'
                order.save()
                return JsonResponse({'status': 'signature_verification_failed'}, status=400)
        except Order.DoesNotExist:
            return JsonResponse({'status': 'order_not_found'}, status=404)
    
    return JsonResponse({'status': 'invalid_request'}, status=400)

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'shop/signup.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('home')
    else:
        form = LoginForm()
    return render(request, 'shop/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def process_order(request):
    if request.method == 'POST':
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            return redirect('cart')
        
        total = sum(item.total_price() for item in cart_items)
        payment_method = request.POST.get('payment_method', 'COD')

        if payment_method == 'COD':
            # Create order for COD
            order = Order.objects.create(
                user=request.user,
                total_amount=total,
                payment_method=payment_method,
                payment_status='confirmed'
            )
            
            # Create order items
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price=item.product.price
                )
            
            # Clear the cart
            cart_items.delete()
            return render(request, 'shop/order_confirmation.html', {
                'order': order,
                'order_detail_url': reverse('order_detail', args=[order.id])
            })
        
        # Create order for Razorpay
        order = Order.objects.create(
            user=request.user,
            total_amount=total,
            payment_method=payment_method,
            payment_status='pending'
        )
        
        # Create order items
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
        
        # Create Razorpay order
        razorpay_order = client.order.create({
            'amount': int(total * 100),
            'currency': 'INR',
            'receipt': f'order_{order.id}',
            'payment_capture': '1'
        })
        
        order.razorpay_order_id = razorpay_order['id']
        order.save()
        
        context = {
            'order': order,
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'amount': int(total * 100),
            'currency': 'INR',
            'name': request.user.username,
            'email': request.user.email,
        }
        return render(request, 'shop/payment.html', context)
    
    return redirect('checkout')

@login_required
def order_history(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'shop/order_history.html', {'orders': orders})

@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'shop/order_detail.html', {'order': order})