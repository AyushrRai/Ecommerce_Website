from django.core.management.base import BaseCommand
from shop.models import Product, Category
import requests


class Command(BaseCommand):
    help = 'Seed products from DummyJSON API'

    def handle(self, *args, **options):
        # Create categories if they don't exist
        categories = ["mens-shoes", "womens-dresses", "smartphones", "laptops", "fragrances", "groceries", "home-decoration"]
        category_mapping = {}

        for cat_name in categories:
            category_obj, created = Category.objects.get_or_create(name=cat_name)
            category_mapping[cat_name] = category_obj
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Created category: {cat_name}'))

        # Fetch products from DummyJSON
        try:
            response = requests.get('https://dummyjson.com/products?limit=100', timeout=30)
            response.raise_for_status()
            data = response.json()
            products = data.get('products', [])

            if not products:
                self.stdout.write(self.style.ERROR('❌ No products found in API response'))
                return

            imported_count = 0
            updated_count = 0
            skipped_count = 0

            for product in products:
                # Category check
                category_name = product.get('category', '').lower()
                category_obj = category_mapping.get(category_name)

                if not category_obj:
                    self.stdout.write(self.style.WARNING(
                        f"⚠️ Skipping product '{product.get('title')}' - unknown category: {category_name}"
                    ))
                    skipped_count += 1
                    continue

                # Pick best image
                image_url = (
                    product.get('thumbnail')
                    or (product.get('images', [None])[0])
                    or "https://via.placeholder.com/400x400?text=No+Image"
                )

                # Ensure HTTPS (avoid mixed content issues)
                if image_url.startswith("http://"):
                    image_url = image_url.replace("http://", "https://")

                # Create or update product
                product_obj, created = Product.objects.get_or_create(
                    api_id=product.get('id'),
                    defaults={
                        'title': product.get('title', 'No Title'),
                        'price': product.get('price', 0),
                        'description': product.get('description', ''),
                        'category': category_obj,
                        'image_url': image_url,
                    }
                )

                if created:
                    imported_count += 1
                else:
                    # Update old record
                    product_obj.title = product.get('title', product_obj.title)
                    product_obj.price = product.get('price', product_obj.price)
                    product_obj.description = product.get('description', product_obj.description)
                    product_obj.category = category_obj
                    product_obj.image_url = image_url
                    product_obj.save()
                    updated_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f'🎉 Successfully imported {imported_count} products, updated {updated_count}, skipped {skipped_count}'
                )
            )

        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'❌ Failed to fetch products from API: {e}'))
        except KeyError as e:
            self.stdout.write(self.style.ERROR(f'❌ Unexpected API response format: {e}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ An unexpected error occurred: {e}'))
