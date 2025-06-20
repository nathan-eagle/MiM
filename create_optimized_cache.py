#!/usr/bin/env python3
"""
Script to create an optimized product cache for faster serverless loading.

This removes unnecessary data like detailed variants, sizes, and descriptions
while keeping essential product information for LLM selection.
"""

import json
from collections import defaultdict

def create_optimized_cache():
    """Create optimized cache from complete cache file"""
    
    # Load complete cache
    print("Loading complete product cache...")
    with open('product_cache_complete.json', 'r') as f:
        complete_cache = json.load(f)
    
    print(f"Found {len(complete_cache['products'])} products in complete cache")
    
    # Create optimized structure
    optimized_cache = {
        "last_update": complete_cache["last_update"],
        "products": {},
        "categories": defaultdict(list),
        "total_products": 0
    }
    
    # Process each product
    for product_id, product_data in complete_cache["products"].items():
        
        # Extract unique colors from variants (without sizes)
        available_colors = set()
        for variant in product_data.get("variants", []):
            if variant.get("color"):
                color = variant["color"].strip()
                # Clean up color names
                color = color.split('/')[0].strip()  # Remove "color/heather" parts
                color = color.split(' patch')[0].strip()  # Remove "color patch" parts
                if color and color not in ['', 'None']:
                    available_colors.add(color)
        
        # Create optimized product entry
        optimized_product = {
            "id": product_data["id"],
            "title": product_data["title"],
            "category": product_data["category"],
            "available_colors": sorted(list(available_colors)),
            "tags": product_data.get("tags", [])[:5],  # Keep only first 5 tags
            "available": product_data.get("available", True)
        }
        
        # Store in optimized cache
        optimized_cache["products"][product_id] = optimized_product
        
        # Add to category index
        category = product_data["category"]
        optimized_cache["categories"][category].append(int(product_id))
    
    # Convert defaultdict to regular dict and sort category lists
    optimized_cache["categories"] = {
        category: sorted(product_ids) 
        for category, product_ids in optimized_cache["categories"].items()
    }
    
    optimized_cache["total_products"] = len(optimized_cache["products"])
    
    # Save optimized cache
    print("Saving optimized cache...")
    with open('product_cache.json', 'w') as f:
        json.dump(optimized_cache, f, indent=2)
    
    # Calculate size reduction
    import os
    original_size = os.path.getsize('product_cache_complete.json')
    optimized_size = os.path.getsize('product_cache.json')
    reduction_percent = ((original_size - optimized_size) / original_size) * 100
    
    print(f"✅ Optimization complete!")
    print(f"   Original size: {original_size / 1024 / 1024:.1f}MB")
    print(f"   Optimized size: {optimized_size / 1024 / 1024:.1f}MB")
    print(f"   Size reduction: {reduction_percent:.1f}%")
    print(f"   Products: {optimized_cache['total_products']}")
    print(f"   Categories: {len(optimized_cache['categories'])}")
    
    # Show sample categories
    print(f"\nCategories:")
    for category, product_ids in sorted(optimized_cache["categories"].items()):
        print(f"   {category}: {len(product_ids)} products")

if __name__ == "__main__":
    create_optimized_cache() 