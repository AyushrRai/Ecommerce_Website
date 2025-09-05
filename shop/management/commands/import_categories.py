
from django.core.management.base import BaseCommand
from shop.models import Category

class Command(BaseCommand):
    help = 'Import standard product categories'
    
    def handle(self, *args, **options):
        categories = [
            "men's clothing",
            "women's clothing",
            "electronics",
            "jewelery"
        ]
        
        for cat in categories:
            Category.objects.get_or_create(
                name=cat,
                defaults={'slug': cat.replace(" ", "-").replace("'", "")}
            )
        
        self.stdout.write(self.style.SUCCESS('Successfully imported categories'))