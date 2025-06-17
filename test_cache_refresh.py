#!/usr/bin/env python3
"""
Quick script to refresh the product cache with variants
"""

from product_catalog import create_product_catalog
import os

# Remove old cache to force refresh with variants
if os.path.exists('product_cache.json'):
    os.remove('product_cache.json')
    print('🗑️ Removed old cache file')

# Create catalog and force load with variants
catalog = create_product_catalog()
print('📦 Created product catalog instance')

print('⏳ Loading catalog with variants (this may take a few minutes)...')
success = catalog.load_catalog(force_refresh=True)
print(f'✅ Catalog load success: {success}')

if success:
    # Check if variants are now cached
    product = list(catalog._products_cache.values())[0]
    print(f'🎨 Sample product has {len(product.variants)} cached variants')
    if product.variants:
        print(f'🔍 First variant: {product.variants[0].color} - {product.variants[0].title}')
    
    # Test a specific product's colors
    if len(catalog._products_cache) > 10:
        test_product = list(catalog._products_cache.values())[10]  # Get a different product
        colors = catalog.get_available_colors(test_product.id)
        print(f'🌈 Product "{test_product.title}" has colors: {colors[:5]}{"..." if len(colors) > 5 else ""}')
        print(f'💾 Total cached variants across all products: {sum(len(p.variants) for p in catalog._products_cache.values())}')
else:
    print('❌ Failed to load catalog') 