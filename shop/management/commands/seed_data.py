from django.core.management.base import BaseCommand
from shop.models import Product, Category
import requests

class Command(BaseCommand):
    help = 'Seed products from DummyJSON API'

    def handle(self, *args, **options):
        # Create categories if they don't exist
        categories = ["men's clothing", "women's clothing", "electronics", "jewelery"]
        category_mapping = {}
        
        for cat_name in categories:
            category_obj, created = Category.objects.get_or_create(name=cat_name)
            category_mapping[cat_name] = category_obj
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created category: {cat_name}'))
        
        # Fetch products from API
        try:
            response = requests.get('https://dummyjson.com/products?limit=100', timeout=30)
            response.raise_for_status()  # Raise exception for bad status codes
            
            data = response.json()
            products = data.get('products', [])
            
            if not products:
                self.stdout.write(self.style.ERROR('No products found in API response'))
                return
            
            imported_count = 0
            skipped_count = 0
            
            for product in products:
                # Safely get category with fallback
                category_name = product.get('category', '').lower()
                category_obj = category_mapping.get(category_name)
                
                if not category_obj:
                    self.stdout.write(self.style.WARNING(f"Skipping product '{product.get('title')}' - unknown category: {category_name}"))
                    skipped_count += 1
                    continue
                
                # Create or update product
                product_obj, created = Product.objects.get_or_create(
                    title=product['title'],
                    defaults={
                        'price': product.get('price', 0),
                        'description': product.get('description', ''),
                        'category': category_obj,
                        'image_url': product.get('thumbnail', '') or product.get('image', '')
                    }
                )
                
                if created:
                    imported_count += 1
                else:
                    # Update existing product if needed
                    product_obj.price = product.get('price', 0)
                    product_obj.description = product.get('description', '')
                    product_obj.category = category_obj
                    product_obj.image_url = product.get('thumbnail', '') or product.get('image', '')
                    product_obj.save()
                    skipped_count += 1
            
            self.stdout.write(self.style.SUCCESS(f'Successfully imported {imported_count} products, skipped {skipped_count} existing products'))
            
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch products from API: {e}'))
        except KeyError as e:
            self.stdout.write(self.style.ERROR(f'Unexpected API response format: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An unexpected error occurred: {e}'))