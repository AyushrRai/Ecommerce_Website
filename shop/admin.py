from django.contrib import admin
from .models import Product, Category, Cart, Order, OrderItem

class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'price', 'category')
    list_filter = ('category',)
    search_fields = ('title', 'description')

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'payment_status', 'created_at')
    list_filter = ('payment_status', 'created_at')
    inlines = [OrderItemInline]

admin.site.register(Product, ProductAdmin)
admin.site.register(Category)
admin.site.register(Cart)
admin.site.register(Order, OrderAdmin)