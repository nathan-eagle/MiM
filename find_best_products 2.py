import requests
import os
from dotenv import load_dotenv
import json
from collections import defaultdict

# Load environment variables
load_dotenv()

# Get API token
PRINTIFY_API_TOKEN = os.getenv('PRINTIFY_API_TOKEN')

if not PRINTIFY_API_TOKEN:
    print("Error: PRINTIFY_API_TOKEN not found in environment variables")
    print("Please set your PRINTIFY_API_TOKEN in the .env file")
    exit(1)

headers = {
    "Authorization": f"Bearer {PRINTIFY_API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "PythonScript"
}

# Categories to search for
CATEGORIES = [
    "Hoodies and Warm Ups",
    "Water Bottles", 
    "Blankets",
    "Drawstring Bags",
    "Rally Towels",
    "Bucket Hats",
    "Stadium Chairs & Cushions",
    "Cooler Bags",
    "Car Magnets and Fridge Magnets",
    "Headbands and Wrist Bands",
    "Performance T-Shirts",
    "Foam Fingers",
    "Door Flags",
    "Hand Warmers",
    "Tailgate Flags",
    "Team Scarves",
    "Face Stickers",
    "Waterproof Bags",
    "Flip Flops",
    "Car Mats",
    "Bag Tags",
    "Tape Bags",
    "Umbrellas"
]

# Search terms for each category
SEARCH_TERMS = {
    "Hoodies and Warm Ups": ["hoodie", "sweatshirt", "pullover", "zip", "warm up"],
    "Water Bottles": ["water bottle", "bottle", "tumbler", "flask"],
    "Blankets": ["blanket", "throw", "fleece"],
    "Drawstring Bags": ["drawstring", "gym bag", "cinch", "sack"],
    "Rally Towels": ["towel", "rally"],
    "Bucket Hats": ["bucket hat", "bucket", "fishing hat"],
    "Stadium Chairs & Cushions": ["chair", "cushion", "seat", "stadium"],
    "Cooler Bags": ["cooler", "insulated bag", "lunch bag"],
    "Car Magnets and Fridge Magnets": ["magnet", "car magnet", "fridge magnet"],
    "Headbands and Wrist Bands": ["headband", "wristband", "sweatband"],
    "Performance T-Shirts": ["performance", "athletic", "sport", "moisture", "dry fit"],
    "Foam Fingers": ["foam finger", "foam"],
    "Door Flags": ["door flag", "flag", "banner"],
    "Hand Warmers": ["hand warmer", "warmer"],
    "Tailgate Flags": ["tailgate", "flag", "banner"],
    "Team Scarves": ["scarf", "scarves"],
    "Face Stickers": ["face sticker", "sticker", "decal"],
    "Waterproof Bags": ["waterproof", "water resistant", "dry bag"],
    "Flip Flops": ["flip flop", "sandal", "slipper"],
    "Car Mats": ["car mat", "floor mat", "mat"],
    "Bag Tags": ["bag tag", "luggage tag", "tag"],
    "Tape Bags": ["tape bag", "bag"],
    "Umbrellas": ["umbrella"]
}

def get_all_blueprints():
    """Get all available blueprints from Printify"""
    try:
        url = "https://api.printify.com/v1/catalog/blueprints.json"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        print(f"Error fetching blueprints: {e}")
        return []

def search_category_products(category, search_terms, blueprints):
    """Search for products matching a category"""
    matches = []
    
    for blueprint in blueprints:
        title_lower = blueprint['title'].lower()
        
        # Check if any search term matches
        for term in search_terms:
            if term.lower() in title_lower:
                matches.append({
                    'id': blueprint['id'],
                    'title': blueprint['title'],
                    'matched_term': term
                })
                break  # Only count each blueprint once
    
    return matches

def get_print_providers(blueprint_id):
    """Get print providers for a blueprint"""
    try:
        url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers.json"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        providers = res.json()
        return len(providers) > 0, providers
    except Exception as e:
        print(f"Error getting providers for blueprint {blueprint_id}: {e}")
        return False, []

def analyze_products():
    """Analyze all products and find the best for each category"""
    print("Fetching all Printify blueprints...")
    blueprints = get_all_blueprints()
    
    if not blueprints:
        print("Failed to fetch blueprints")
        return
    
    print(f"Found {len(blueprints)} total blueprints")
    print("=" * 80)
    
    results = {}
    
    for category in CATEGORIES:
        print(f"\n🔍 Searching for: {category}")
        print("-" * 50)
        
        search_terms = SEARCH_TERMS.get(category, [category.lower()])
        matches = search_category_products(category, search_terms, blueprints)
        
        if not matches:
            print(f"❌ No products found for {category}")
            results[category] = []
            continue
        
        print(f"✅ Found {len(matches)} potential products:")
        
        # Check which ones have print providers (are actually available)
        available_products = []
        
        for match in matches[:10]:  # Check top 10 matches
            has_providers, providers = get_print_providers(match['id'])
            if has_providers:
                available_products.append({
                    **match,
                    'provider_count': len(providers),
                    'providers': [p.get('title', 'Unknown') for p in providers[:3]]  # Top 3 providers
                })
                print(f"  ✓ {match['title']} (ID: {match['id']}) - {len(providers)} providers")
            else:
                print(f"  ✗ {match['title']} (ID: {match['id']}) - No providers")
        
        # Sort by provider count (more providers = better availability)
        available_products.sort(key=lambda x: x['provider_count'], reverse=True)
        results[category] = available_products
        
        if available_products:
            best = available_products[0]
            print(f"🏆 BEST: {best['title']} (ID: {best['id']}) - {best['provider_count']} providers")
        else:
            print(f"❌ No available products found for {category}")
    
    return results

def save_whitelist(results):
    """Save the whitelist to a JSON file"""
    whitelist = {}
    
    for category, products in results.items():
        if products:
            best_product = products[0]  # Top product
            whitelist[category] = {
                'blueprint_id': best_product['id'],
                'title': best_product['title'],
                'provider_count': best_product['provider_count'],
                'top_providers': best_product['providers'],
                'matched_term': best_product['matched_term']
            }
        else:
            whitelist[category] = None
    
    # Save to JSON file
    with open('printify_whitelist.json', 'w') as f:
        json.dump(whitelist, f, indent=2)
    
    print(f"\n💾 Whitelist saved to 'printify_whitelist.json'")
    
    # Print summary
    print("\n" + "=" * 80)
    print("📋 WHITELIST SUMMARY")
    print("=" * 80)
    
    found_count = 0
    for category, product in whitelist.items():
        if product:
            found_count += 1
            print(f"✅ {category}: {product['title']} (ID: {product['blueprint_id']})")
        else:
            print(f"❌ {category}: No suitable product found")
    
    print(f"\n📊 Found products for {found_count}/{len(CATEGORIES)} categories")
    
    return whitelist

if __name__ == "__main__":
    print("🔍 Printify Product Whitelist Generator")
    print("=" * 80)
    
    results = analyze_products()
    if results:
        whitelist = save_whitelist(results)
        
        print(f"\n✨ Analysis complete! Check 'printify_whitelist.json' for the full results.")
    else:
        print("❌ Analysis failed") 