import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, jsonify
import requests
import time
import openai
import re
import sys
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
sys.path.append('..')
from product_catalog import create_product_catalog
from llm_product_selection import get_llm_product_selection
from conversation_manager import ConversationManager, ConversationContext
from intelligent_color_selection import IntelligentColorSelector
from intelligent_error_handler import IntelligentErrorHandler, ErrorContext, ErrorRecovery

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure logging (Vercel-compatible - no file logging in serverless)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Console logging only for Vercel
    ]
)
logger = logging.getLogger(__name__)

# In-memory log storage for Vercel (since we can't write files)
server_logs = []

def add_server_log(message):
    """Add a message to server logs (in-memory for Vercel)"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_message = f"{timestamp} - INFO - {message}"
    server_logs.append(formatted_message)
    # Keep only the last 100 log entries to prevent memory issues
    if len(server_logs) > 100:
        server_logs.pop(0)
    logger.info(message)  # Also log to console (visible in Vercel logs)

# Get API keys from environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
PRINTIFY_API_TOKEN = os.getenv('PRINTIFY_API_TOKEN')

if not OPENAI_API_KEY or not PRINTIFY_API_TOKEN:
    raise ValueError("Missing required environment variables: OPENAI_API_KEY and/or PRINTIFY_API_TOKEN")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Printify API headers
headers = {
    "Authorization": f"Bearer {PRINTIFY_API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "PythonScript"
}

# Chat history will be stored server-side
chat_history = []

# Default logo settings
default_logo_settings = {
    "scale": 1.0,
    "x": 0.5,
    "y": 0.5
}

# Store the current logo settings for the session
current_logo_settings = default_logo_settings.copy()

# Initialize product catalog, conversation manager, and color selector
product_catalog = None
conversation_manager = None
color_selector = None
error_handler = None

def init_product_catalog():
    """Initialize the product catalog on first use"""
    global product_catalog, conversation_manager, color_selector, error_handler
    if product_catalog is None:
        try:
            add_server_log("Starting product catalog initialization...")
            product_catalog = create_product_catalog()
            add_server_log("Product catalog created, loading catalog...")
            success = product_catalog.load_catalog()
            if success:
                add_server_log("Product catalog initialized successfully")
                # Initialize conversation manager with the catalog
                add_server_log("Initializing conversation manager...")
                conversation_manager = ConversationManager(product_catalog)
                add_server_log("Conversation manager initialized successfully")
                # Initialize intelligent color selector
                add_server_log("Initializing intelligent color selector...")
                color_selector = IntelligentColorSelector()
                add_server_log("Intelligent color selector initialized successfully")
                # Initialize intelligent error handler
                add_server_log("Initializing intelligent error handler...")
                error_handler = IntelligentErrorHandler(product_catalog, headers)
                add_server_log("Intelligent error handler initialized successfully")
            else:
                add_server_log("Failed to initialize product catalog")
        except Exception as e:
            add_server_log(f"Error initializing product catalog: {e}")
            import traceback
            add_server_log(f"Full traceback: {traceback.format_exc()}")
            product_catalog = None
            conversation_manager = None
            color_selector = None

# Store current product information for memory
current_product_memory = {
    "blueprint_id": None,
    "blueprint_title": None,
    "print_provider_id": None,
    "current_color": None,
    "available_colors": [],
    "last_mockup_url": None
}

# Debug logs for the webpage
debug_logs = []

def check_openai_client():
    """Check if OpenAI client is available and working"""
    if not openai.api_key:
        raise Exception("OpenAI API key not initialized - check API key and network connection")
    return True

def add_debug_log(message):
    """Add a debug message to the logs"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    debug_logs.append(formatted_message)
    # Keep only the last 20 log entries
    if len(debug_logs) > 20:
        debug_logs.pop(0)
    print(message)  # Also print to console
    add_server_log(f"DEBUG: {message}")  # Add to in-memory server logs

def extract_color_from_message(message):
    """Extract color from user message - simplified fallback implementation"""
    if not message:
        return None
    
    # Basic color extraction - this was replaced by intelligent color selection
    common_colors = ['red', 'blue', 'green', 'yellow', 'black', 'white', 'gray', 'grey', 
                    'pink', 'purple', 'orange', 'brown', 'navy', 'maroon', 'cyan']
    
    message_lower = message.lower()
    for color in common_colors:
        if color in message_lower:
            return color
    return None

def handle_compound_words(search_term):
    """Handle compound words - simplified fallback implementation"""
    if not search_term:
        return []
    
    # Basic compound word handling - this was replaced by AI understanding
    compound_map = {
        'lampshade': ['lamp', 'shade'],
        'mousepad': ['mouse', 'pad'],
        'keychain': ['key', 'chain'],
        'doormat': ['door', 'mat'],
        'pillowcase': ['pillow', 'case']
    }
    
    return compound_map.get(search_term.lower(), [])

def simplify_search_term(search_term):
    """Simplify search terms - simplified fallback implementation"""
    if not search_term:
        return search_term
    
    # Basic term simplification - this was replaced by AI understanding
    simplification_map = {
        'sweatshirt': 'hoodie',
        'sweater': 'hoodie',
        'jumper': 'hoodie',
        'pullover': 'hoodie',
        'tshirt': 't-shirt',
        'tee': 't-shirt',
        'cap': 'hat',
        'beanie': 'hat',
        'cup': 'mug',
        'tumbler': 'mug'
    }
    
    term_lower = search_term.lower().strip()
    return simplification_map.get(term_lower, search_term)

# =============================================================================
# PRODUCT CATALOG AND SELECTION SYSTEM
# =============================================================================
# This application now uses an AI-driven product selection system instead of 
# hardcoded string matching. The system consists of:
#
# 1. ProductCatalog (product_catalog.py) - Loads and caches all Printify products
# 2. LLMProductSelector (llm_product_selection.py) - Uses AI to select products  
# 3. Structured schemas (product_selection_schema.py) - Validates AI responses
#
# REMOVED: Legacy hardcoded color lists, product dictionaries, and string 
# matching functions have been eliminated in favor of intelligent AI selection.
# =============================================================================

def get_all_available_products():
    """Get a list of all available products from Printify API - DEPRECATED: Use product_catalog instead"""
    global product_catalog
    
    # Initialize catalog if needed
    if product_catalog is None:
        init_product_catalog()
    
    if product_catalog is None:
        # Fallback to old method if catalog initialization failed
        return get_all_available_products_old()
    
    try:
        # Get categories from the new catalog
        categories = product_catalog.get_categories()
        
        # Convert to old format for backward compatibility
        product_categories = {}
        for category_name, products in categories.items():
            product_categories[category_name] = []
            for product in products:
                product_categories[category_name].append({
                    'id': product.id,
                    'title': product.title,
                    'available': product.available
                })
        
        add_debug_log(f"Loaded {len(product_categories)} product categories from catalog")
        return product_categories
        
    except Exception as e:
        add_debug_log(f"Error getting products from catalog: {e}")
        # Fallback to old method
        return get_all_available_products_old()

def get_all_available_products_old():
    """Original method for getting products - kept as fallback"""
    try:
        url = "https://api.printify.com/v1/catalog/blueprints.json"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        blueprints = res.json()
        
        # Create a list of product categories and sample products
        product_categories = {}
        
        # Log all available products for debugging
        print("==== AVAILABLE PRODUCTS IN CATALOG ====")
        all_product_titles = [blueprint['title'] for blueprint in blueprints]
        for title in all_product_titles:
            print(f"- {title}")
        print("======================================")
        
        # Instead of checking all blueprints for availability (which is slow),
        # let's assume all are available initially and just categorize them
        for blueprint in blueprints:
            title = blueprint['title'].lower()
            # Extract main category (e.g., "T-Shirt" from "Premium T-Shirt")
            main_category = None
            for category in ['shirt', 'tee', 't-shirt', 'hat', 'cap', 'mug', 'cup', 'hoodie', 
                            'sweatshirt', 'bag', 'tote', 'poster', 'sticker', 'phone case',
                            'socks', 'pillow', 'blanket', 'lamp', 'apron', 'mask', 'beanie']:
                if category in title:
                    main_category = category
                    break
            
            # If no category match found, use the first word
            if not main_category and ' ' in title:
                main_category = title.split(' ')[0]
            elif not main_category:
                main_category = "other"
                
            # Add to category dict
            if main_category not in product_categories:
                product_categories[main_category] = []
            
            product_categories[main_category].append({
                'id': blueprint['id'],
                'title': blueprint['title'],
                'available': True  # Assume all products are available
            })
        
        return product_categories
    except Exception as e:
        print(f"Error getting available products: {e}")
        return {}

def find_blueprint_id(search_term):
    """
    Find a product blueprint ID using the intelligent catalog system.
    
    MODERN APPROACH: This function now uses the ProductCatalog system to search
    for products instead of hardcoded string matching. The catalog provides
    intelligent search capabilities with proper product categorization.
    
    Args:
        search_term (str): Product name to search for (usually from LLM selection)
        
    Returns:
        tuple: (blueprint_id, product_title) or (None, None) if not found
        
    Note: This function is still used for backward compatibility, but the main
    product selection is now handled by the LLM system in get_ai_suggestion().
    """
    add_debug_log(f"🔍 find_blueprint_id called with: '{search_term}'")
    
    # Initialize catalog if needed
    global product_catalog
    if product_catalog is None:
        init_product_catalog()
    
    # Use the intelligent catalog search if available
    if product_catalog is not None:
        try:
            # Search using the catalog's intelligent search
            search_results = product_catalog.search_products(search_term, limit=1)
            
            if search_results:
                product = search_results[0]
                add_debug_log(f"✅ Catalog search found: {product.title} (ID: {product.id})")
                return product.id, product.title
            else:
                add_debug_log(f"❌ No catalog results for '{search_term}'")
        except Exception as e:
            add_debug_log(f"⚠️ Catalog search failed: {e}")
    
    # Fallback: Direct API search (legacy compatibility)
    try:
        url = "https://api.printify.com/v1/catalog/blueprints.json"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        blueprints = res.json()
        
        search_term_lower = search_term.lower()
        
        # Try exact match first
        for blueprint in blueprints:
            if search_term_lower == blueprint['title'].lower():
                add_debug_log(f"✅ Exact match found: {blueprint['title']} (ID: {blueprint['id']})")
                return blueprint['id'], blueprint['title']
        
        # Try partial match
        for blueprint in blueprints:
            if search_term_lower in blueprint['title'].lower():
                add_debug_log(f"✅ Partial match found: {blueprint['title']} (ID: {blueprint['id']})")
                return blueprint['id'], blueprint['title']
                
    except Exception as e:
        add_debug_log(f"❌ Fallback API search failed: {e}")
    
    add_debug_log(f"❌ No blueprint found for '{search_term}'")
    return None, None

def get_print_providers(blueprint_id):
    url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers.json"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    providers = res.json()
    return providers

def get_shop_id():
    res = requests.get("https://api.printify.com/v1/shops.json", headers=headers)
    res.raise_for_status()
    return res.json()[0]["id"]

def upload_image(image_url):
    # Default image URL if none provided or it fails
    default_logo_url = "https://cdn-icons-png.flaticon.com/512/25/25231.png"  # GitHub logo as a fallback
    
    # If no image_url or it's invalid, use the default
    if not image_url or not image_url.strip() or not (image_url.startswith('http://') or image_url.startswith('https://')):
        print(f"Using default image instead of invalid URL: {image_url}")
        image_url = default_logo_url
    
    try:
        upload_url = "https://api.printify.com/v1/uploads/images.json"
        payload = {"url": image_url, "file_name": "logo.svg"}
        res = requests.post(upload_url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["id"]
    except requests.exceptions.HTTPError as e:
        print(f"Error uploading image ({image_url}): {e}")
        print(f"Trying with default image instead")
        # Fall back to default logo if the provided URL fails
        payload = {"url": default_logo_url, "file_name": "logo.svg"}
        res = requests.post(upload_url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["id"]

def create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids):
    global current_logo_settings
    
    # Use only the first variant to ensure we get the desired color in the mockup
    primary_variant_id = variant_ids[0] if variant_ids else None
    if not primary_variant_id:
        raise Exception("No variants available for product creation")
    
    print(f"Creating product with primary variant ID: {primary_variant_id}")
    
    product_payload = {
        "title": "Custom Product",
        "description": "A custom product with a logo.",
        "blueprint_id": blueprint_id,
        "print_provider_id": print_provider_id,
        "variants": [{"id": primary_variant_id, "price": 1999, "is_enabled": True}],
        "print_areas": [
            {
                "variant_ids": [primary_variant_id],
                "placeholders": [
                    {
                        "position": "front",
                        "images": [
                            {
                                "id": image_id,
                                "angle": 0,
                                "x": current_logo_settings["x"],
                                "y": current_logo_settings["y"],
                                "scale": current_logo_settings["scale"]
                            }
                        ]
                    }
                ]
            }
        ]
    }
    try:
        res = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products.json", headers=headers, json=product_payload)
        res.raise_for_status()
        product_id = res.json()["id"]
        print(f"Successfully created product with ID: {product_id}")
        return product_id
    except requests.exceptions.HTTPError as e:
        print(f"Error creating product: {e}")
        print(f"Response content: {e.response.content}")
        raise e

def get_mockup_image(shop_id, product_id):
    for _ in range(10):  # wait for mockup generation
        res = requests.get(f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}.json", headers=headers)
        res.raise_for_status()
        product = res.json()
        images = product.get("images", [])
        if images:
            return images[0]["src"]
        time.sleep(3)
    raise Exception("Mockup not generated in time.")

def get_ai_suggestion_old(user_message):
    """Original AI suggestion function - kept as backup"""
    global chat_history, current_logo_settings
    
    # Check if this is a conversational message without product request
    conversational_input = any(term in user_message.lower() 
                            for term in ['thanks', 'thank you', 'great', 'awesome', 'perfect', 
                                        'looks good', 'nice', 'cool', 'love it', 'amazing'])
    
    # Check if this is a logo adjustment request
    logo_adjustment_request = any(term in user_message.lower() 
                               for term in ['smaller', 'bigger', 'larger', 'resize', 'left', 'right',
                                           'up', 'down', 'move', 'position', 'scale', 'size'])
    
    # Check if this is a query about available products of a specific type
    product_availability_query = any([
        'what types' in user_message.lower(),
        'what kind' in user_message.lower(),
        'what options' in user_message.lower(),
        'available types' in user_message.lower(),
        'available options' in user_message.lower(),
        'other types' in user_message.lower(),
        'other options' in user_message.lower(),
        'other variations' in user_message.lower(),
        'different styles' in user_message.lower(),
        'different types' in user_message.lower(),
        'what styles' in user_message.lower(),
        'which styles' in user_message.lower(),
        'do you have' in user_message.lower() and any(word in user_message.lower() for word in ['sweatshirt', 'shirt', 'hat', 'mug']),
        'can i get' in user_message.lower() and any(word in user_message.lower() for word in ['sweatshirt', 'shirt', 'hat', 'mug']),
        'are there' in user_message.lower() and any(word in user_message.lower() for word in ['sweatshirt', 'shirt', 'hat', 'mug'])
    ])
    
    # Check if this is a product recommendations request
    recommendation_request = any(term in user_message.lower() 
                              for term in ['recommend', 'suggestion', 'ideas', 'what about', 
                                         'what else', 'other products', 'other options', 
                                         'what would be good', 'cool gift', 'team gift',
                                         'what should i', 'what can i', 'can you suggest',
                                         'swag', 'merchandise', 'merch'])
    
    try:
        # Handle conversational responses first
        if conversational_input and not any(term in user_message.lower() for term in ['hat', 'shirt', 'mug', 'cup', 'hoodie', 'product']):
            # Generate a conversational response
            ai_message = "You're welcome! Is there anything else you'd like to customize or try?"
            add_message_to_chat("assistant", ai_message)
            
            # Return the current product type (or t-shirt as fallback) to maintain context
            current_product = extract_current_product_type(chat_history)
            return {"search_term": current_product, "conversational": True}, ai_message
            
        # For logo adjustment requests, update the logo settings
        elif logo_adjustment_request:
            # Parse the user message for logo adjustments
            adjust_logo_settings(user_message)
            
            # Get the current product type to reuse
            search_term = extract_current_product_type(chat_history)
            
            # Return response with updated settings
            ai_message = generate_logo_adjustment_response(user_message)
            add_message_to_chat("assistant", ai_message)
            
            return {"search_term": search_term, "adjust_logo": True}, ai_message
            
        # For queries about available specific product types, fetch actual available products
        elif product_availability_query:
            # Add a timeout to prevent hanging
            timeout_seconds = 5
            start_time = time.time()
            
            try:
                # Get all products from the API
                product_categories = get_all_available_products()
                
                # Extract the product type the user is asking about
                product_type_keywords = ['shirt', 'sweatshirt', 'hoodie', 'hat', 'cap', 'mug', 'tote', 'bag']
                target_product_type = None
                
                # Find which product type the user is asking about
                search_lower = user_message.lower()
                for keyword in product_type_keywords:
                    if keyword in search_lower:
                        target_product_type = keyword
                        break
                
                if target_product_type:
                    # Find all matching products in the catalog
                    matching_products = []
                    for category, products in product_categories.items():
                        # Check if we've exceeded the timeout
                        if time.time() - start_time > timeout_seconds:
                            print(f"Timeout reached when searching for {target_product_type} products")
                            break
                            
                        # Match either the exact category or products that contain the target type
                        if target_product_type in category or category in target_product_type:
                            matching_products.extend(products)
                        else:
                            # Also check individual product titles
                            for product in products:
                                if target_product_type in product['title'].lower():
                                    matching_products.append(product)
                                    
                                # Check if we've exceeded the timeout
                                if time.time() - start_time > timeout_seconds:
                                    print(f"Timeout reached during product title check")
                                    break
                    
                    if matching_products:
                        # Create a response listing the available products
                        # Limit to first 10 products to ensure we don't overwhelm the user
                        # Skip availability check to improve performance
                        product_list = "\n".join([f"- {product['title']}" for product in matching_products[:10]])
                        
                        if len(matching_products) > 10:
                            product_list += f"\n...and {len(matching_products) - 10} more options."
                        
                        response_message = f"Here are some {target_product_type} products available on Printify:\n\n{product_list}\n\nWhich one would you like to try?"
                        add_message_to_chat("assistant", response_message)
                        
                        # Choose the first product as a search term
                        if matching_products:
                            return {"search_term": matching_products[0]['title']}, response_message
                        else:
                            # Fallback if there are no matches
                            return {"search_term": target_product_type}, response_message
                    else:
                        response_message = f"I couldn't find any specific {target_product_type} products in the catalog. Would you like to try a different product type?"
                        add_message_to_chat("assistant", response_message)
                        return {"search_term": target_product_type}, response_message
                else:
                    # If no specific product type found, proceed to general recommendations
                    # Return a fallback so we don't return None
                    current_product = extract_current_product_type(chat_history) 
                    return {"search_term": current_product}, "I'll help you find products"
            except Exception as e:
                print(f"Error handling product availability query: {e}")
                error_message = f"Sorry, I had trouble finding information about available products. Let's try something else."
                add_message_to_chat("assistant", error_message)
                current_product = extract_current_product_type(chat_history)
                return {"search_term": current_product}, error_message
                
        # For recommendation requests, use a different system prompt
        elif recommendation_request:
            # Get available products to include in the system prompt
            product_categories = get_all_available_products()
            available_products_str = ""
            for category, products in product_categories.items():
                sample_products = [p['title'] for p in products[:3]]  # Take first 3 examples
                available_products_str += f"- {category}: {', '.join(sample_products)}\n"
            
            # Create a more conversational, recommendation-focused prompt
            system_content = f"""You are a helpful merchandise assistant that recommends products available on Printify.
Available product categories include:
{available_products_str}

When the user asks for suggestions, recommend 2-3 specific products from the available categories that would work well for their use case.
IMPORTANT: ONLY recommend products that are specifically listed in the available categories above. DO NOT make up or hallucinate product names.
Be conversational and focus on understanding what they want to use the product for.
Provide a brief explanation for why each recommendation would be good for their needs.
Format your response in natural language, not as JSON."""
            
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_content},
                    *chat_history
                ]
            )
            
            ai_message = response.choices[0].message.content
            # Add this conversational response to chat history
            add_message_to_chat("assistant", ai_message)
            
            # Try to extract a primary recommendation from the text to use as search term
            follow_up = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract the main product type being recommended in this message. Return a simple JSON with just one key 'search_term' containing the product type."},
                    {"role": "user", "content": ai_message}
                ]
            )
            
            json_str = follow_up.choices[0].message.content
            try:
                # Try to extract the JSON
                json_match = re.search(r'```json\n(.*?)\n```', json_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = re.search(r'{.*}', json_str, re.DOTALL).group(0)
                    
                suggestion = json.loads(json_str)
                return suggestion, ai_message
            except:
                # If parsing fails, extract a keyword from the conversational response
                for category in product_categories.keys():
                    if category in ai_message.lower():
                        return {"search_term": category}, ai_message
                
                # Default fallback if no category found
                current_product = extract_current_product_type(chat_history)
                return {"search_term": current_product}, ai_message
        else:
            # Use the original product extraction approach for non-recommendation requests
            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that helps users find products on Printify. Your task is to extract the product type and relevant details from the user's message. Return a JSON with 'search_term' and optionally 'image_url' if mentioned. Focus on the main product type (hat, shirt, mug, etc.) and key attributes. If the user mentions a compound word (like 'lampshade'), consider breaking it into parts (lamp, shade) or look for synonyms or related terms that might be more common on an e-commerce platform."},
                    *chat_history
                ]
            )
            
            ai_message = response.choices[0].message.content
            # Don't add the raw JSON response to chat history
            
            # Try to extract JSON data from AI response
            try:
                import json
                import re
                
                # Look for JSON pattern in the response
                json_match = re.search(r'```json\n(.*?)\n```', ai_message, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = re.search(r'{.*}', ai_message, re.DOTALL).group(0)
                    
                suggestion = json.loads(json_str)
                return suggestion, ai_message
            except Exception as e:
                # If JSON parsing fails, have the AI try again with a more structured format
                follow_up = openai.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "Extract the product information from the conversation and return ONLY a JSON object with keys 'search_term' and optionally 'image_url'."},
                        *chat_history,
                        {"role": "user", "content": "Please format your response as a simple JSON with 'search_term' and optionally 'image_url' keys only."}
                    ]
                )
                
                json_str = follow_up.choices[0].message.content
                # Don't add this follow-up to chat history either
                
                # Try to extract the JSON
                json_match = re.search(r'```json\n(.*?)\n```', json_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = re.search(r'{.*}', json_str, re.DOTALL).group(0)
                    
                suggestion = json.loads(json_str)
                return suggestion, ai_message
            
    except Exception as e:
        print(f"Error communicating with OpenAI: {e}")
        # Return a fallback to prevent NoneType errors
        current_product = extract_current_product_type(chat_history)
        return {"search_term": current_product}, f"Error: {str(e)}"

def handle_product_not_found(user_message, original_request=""):
    """
    Handle product not found scenarios with intelligent alternatives.
    
    Uses the IntelligentErrorHandler to suggest alternatives when products
    can't be found, replacing generic error messages with helpful suggestions.
    """
    global error_handler, chat_history
    
    # Initialize error handler if needed
    if error_handler is None:
        init_product_catalog()
    
    if error_handler is None:
        return "I couldn't find that product. Please try a different search term."
    
    try:
        # Create error context
        context = ErrorContext(
            error_type="PRODUCT_NOT_FOUND",
            original_request=original_request or user_message,
            user_message=user_message,
            conversation_history=chat_history[-5:] if chat_history else []
        )
        
        # Get intelligent recovery suggestions
        recovery = error_handler.handle_product_not_found(context)
        
        # Generate user-friendly message
        return error_handler.get_recovery_message(recovery)
        
    except Exception as e:
        add_debug_log(f"❌ Error in intelligent error handling: {e}")
        return "I couldn't find that product, but let me suggest some popular alternatives like t-shirts, mugs, or hats."

def get_ai_suggestion(user_message):
    """
    NEW LLM-Driven Product Selection System
    
    This replaces the old string matching heuristics with intelligent 
    LLM-based product selection using the complete Printify catalog.
    """
    global chat_history, current_logo_settings
    
    # Handle conversational input without product requests
    conversational_input = any(term in user_message.lower() 
                            for term in ['thanks', 'thank you', 'great', 'awesome', 'perfect', 
                                        'looks good', 'nice', 'cool', 'love it', 'amazing'])
    
    # Handle logo adjustment requests
    logo_adjustment_request = any(term in user_message.lower() 
                               for term in ['smaller', 'bigger', 'larger', 'resize', 'left', 'right',
                                           'up', 'down', 'move', 'position', 'scale', 'size'])
    
    try:
        # Handle conversational responses
        if conversational_input and not any(term in user_message.lower() for term in ['hat', 'shirt', 'mug', 'cup', 'hoodie', 'product']):
            ai_message = "You're welcome! Is there anything else you'd like to customize or try?"
            add_message_to_chat("assistant", ai_message)
            current_product = extract_current_product_type(chat_history)
            return {"search_term": current_product, "conversational": True}, ai_message
            
        # Handle logo adjustments
        elif logo_adjustment_request:
            adjust_logo_settings(user_message)
            search_term = extract_current_product_type(chat_history)
            ai_message = generate_logo_adjustment_response(user_message)
            add_message_to_chat("assistant", ai_message)
            return {"search_term": search_term, "adjust_logo": True}, ai_message
        
        # Use LLM for intelligent product selection
        else:
            # Format conversation history for LLM
            formatted_history = []
            for msg in chat_history[-5:]:  # Last 5 messages for context
                formatted_history.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Get LLM product selection
            success, llm_response, error = get_llm_product_selection(user_message, formatted_history)
            
            if success and llm_response:
                # Add the LLM's response to chat history
                add_message_to_chat("assistant", llm_response.response_message)
                
                # Return the search term and message
                return {
                    "search_term": llm_response.primary_product.product_title,
                    "product_id": llm_response.primary_product.product_id,
                    "category": llm_response.primary_product.category,
                    "confidence": llm_response.primary_product.confidence,
                    "llm_driven": True
                }, llm_response.response_message
            else:
                # Fallback to old system if LLM fails
                add_debug_log(f"LLM selection failed, falling back to old system: {error}")
                return get_ai_suggestion_old(user_message)
                
    except Exception as e:
        add_debug_log(f"Error in new AI suggestion system: {e}")
        # Fallback to old system
        return get_ai_suggestion_old(user_message)

# =============================================================================
# MODERN APPROACH: Intelligent Logo Adjustment
# =============================================================================
# REMOVED: adjust_logo_settings() function
# 
# This hardcoded function has been replaced by the ConversationManager's
# handle_logo_adjustment() method, which uses LLM natural language understanding
# to interpret logo positioning requests and provide intelligent responses.
#
# The new system:
# • Understands complex positioning requests ("top right corner")
# • Provides natural language explanations of adjustments
# • Handles edge cases and invalid requests gracefully
# • Uses AI to interpret user intent instead of keyword matching
#
# Integration: Logo adjustments are now handled through the conversation
# management system in the main Flask route.
# =============================================================================

def extract_current_product_type(chat_history):
    """Extract the most recent product type from chat history or product memory"""
    global current_product_memory
    
    # First, check if we have a current product in memory (most reliable)
    if current_product_memory.get("blueprint_title"):
        product_title = current_product_memory["blueprint_title"]
        add_debug_log(f"📋 Using product from memory: {product_title}")
        return product_title.lower()
    
    # Look through recent messages to find a product mention
    product_types = ['t-shirt', 'shirt', 'hat', 'cap', 'baseball cap', 'mug', 'tote', 'bag', 'sticker', 'poster', 'sweatshirt', 'hoodie']
    
    # Look for success messages with product names, but be more careful about extraction
    for msg in reversed(chat_history):
        if msg["role"] == "assistant" and "found a" in msg["content"].lower():
            content = msg["content"].lower()
            # More specific pattern to avoid catching colors as products
            product_match = re.search(r"found a ([^!]+?) product for you", content)
            if product_match:
                found_product = product_match.group(1).strip()
                # Skip if it's just a color word or contains color words at the beginning
                color_words = ['red', 'blue', 'green', 'black', 'white', 'yellow', 'pink', 'purple', 'orange', 'brown', 'gray', 'grey', 'navy', 'dark', 'light', 'bright']
                
                # Split the found product and check if it starts with a color
                words = found_product.split()
                if words and words[0] in color_words:
                    # Skip this match - it's likely "red hat" instead of just "hat"
                    continue
                elif found_product not in color_words:
                    add_debug_log(f"📋 Found product from success message: {found_product}")
                    return found_product
    
    # Look for initial user product requests (like "hat", "mug", etc.)
    for msg in reversed(chat_history):
        if msg["role"] == "user":
            user_content = msg["content"].lower().strip()
            # Check if it's a simple product request (single word or simple phrase)
            if user_content in product_types:
                add_debug_log(f"📋 Found product from user request: {user_content}")
                return user_content
            # Check for compound product names
            for product_type in product_types:
                if product_type in user_content and len(user_content.split()) <= 3:
                    # Only consider it if the message is short (likely a product request, not a color change)
                    add_debug_log(f"📋 Found product type from user request: {product_type}")
                    return product_type
    
    # Default fallback 
    add_debug_log("📋 Using default fallback: t-shirt")
    return "t-shirt"

# =============================================================================
# MODERN APPROACH: Intelligent Response Generation
# =============================================================================
# REMOVED: generate_logo_adjustment_response() function
#
# This hardcoded response generation function has been replaced by the
# ConversationManager's intelligent response system. The new system:
#
# • Uses LLM to generate natural, contextual responses
# • Explains adjustments in clear, user-friendly language
# • Adapts responses based on conversation history and context
# • Handles complex multi-part adjustments intelligently
# • Provides helpful feedback and next-step suggestions
#
# The LLM now generates responses that are:
# - Contextually appropriate to the specific adjustment made
# - Natural and conversational in tone
# - Informative about what changed and why
# - Encouraging and helpful for continued interaction
#
# Integration: Response generation is now handled by ConversationManager
# within the main conversation flow.
# =============================================================================

def add_message_to_chat(role, content):
    """Add a message to chat history, avoiding duplicates"""
    global chat_history
    
    # Skip empty messages
    if not content.strip():
        return
        
    # Skip if the last message with the same role had identical content
    if chat_history and chat_history[-1]["role"] == role and chat_history[-1]["content"] == content:
        return
        
    # Skip any JSON-formatted messages (they contain user data but shouldn't be shown)
    if re.search(r'^\s*{.*}\s*$', content):
        return
        
    # Add the message
    chat_history.append({"role": role, "content": content})
    
    # Log chat messages to server logs
    add_server_log(f"CHAT - {role.upper()}: {content}")

# =============================================================================
# REMOVED: Legacy String Matching Functions
# =============================================================================
# The following functions have been REMOVED in favor of LLM-driven selection:
#
# - handle_compound_words() - AI now handles word variations intelligently
# - simplify_search_term() - LLM understands complex product descriptions  
# - extract_color_from_message() - LLM handles color requests contextually
# - detect_simple_product_request() - LLM processes all product requests
# - detect_color_availability_question() - LLM handles color questions
#
# WHY REMOVED: These functions relied on hardcoded dictionaries and regex
# patterns that were brittle and hard to maintain. The new LLM system in
# get_ai_suggestion() handles all these cases intelligently using the
# complete Printify catalog and natural language understanding.
#
# REPLACEMENT: All product selection is now handled by:
# 1. get_ai_suggestion() - Main LLM-driven function
# 2. LLMProductSelector - Intelligent product selection with catalog context
# 3. ProductCatalog - Smart search across all available products
# =============================================================================

def get_variants_for_product(blueprint_id, print_provider_id, requested_color=None):
    """
    Get variants for a product using intelligent color selection.
    
    MODERN APPROACH: This function now uses the IntelligentColorSelector
    to provide AI-driven color matching instead of hardcoded heuristics.
    
    The new system:
    • Uses LLM to understand color requests in natural language
    • Provides intelligent color matching with confidence scoring  
    • Handles color synonyms, relationships, and variations
    • Offers smart alternatives when exact matches aren't available
    • Eliminates all hardcoded color matching patterns
    
    Args:
        blueprint_id: Product blueprint ID
        print_provider_id: Print provider ID
        requested_color: User's color request (optional)
        
    Returns:
        List of variant IDs or error dict with alternatives
    """
    global current_product_memory, color_selector
    
    # Initialize color selector if needed
    if color_selector is None:
        init_product_catalog()
    
    try:
        # Fetch variants from Printify API
        res = requests.get(
            f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json", 
            headers=headers
        )
        res.raise_for_status()
        all_variants = res.json()["variants"]
        
        add_debug_log(f"🎨 Fetched {len(all_variants)} variants for blueprint {blueprint_id}")
        
        # Get product context for intelligent color selection
        product_context = {
            "id": blueprint_id,
            "title": current_product_memory.get("blueprint_title", "Unknown Product")
        }
        
        # Use intelligent color selection system
        if color_selector is not None:
            try:
                selection_result = color_selector.select_color_variants(
                    all_variants=all_variants,
                    requested_color=requested_color,
                    product_context=product_context
                )
                
                # Update product memory with results
                current_product_memory["available_colors"] = selection_result.available_colors
                if selection_result.selected_color:
                    current_product_memory["current_color"] = selection_result.selected_color
                
                # Log results
                if selection_result.selected_color:
                    add_debug_log(f"🤖 AI selected color: '{selection_result.selected_color}' (confidence: {selection_result.color_match.confidence:.2f})")
                    add_debug_log(f"✅ Found {len(selection_result.variant_ids)} matching variants")
                    return selection_result.variant_ids
                elif selection_result.error_message:
                    add_debug_log(f"❌ {selection_result.error_message}")
                    # Return error in legacy format for compatibility
                    return {
                        "error": "color_not_found", 
                        "available_colors": selection_result.available_colors,
                        "requested_color": requested_color,
                        "alternatives": selection_result.color_match.alternatives if selection_result.color_match else []
                    }
                else:
                    # No specific color requested - return all variants
                    add_debug_log("No color requested, returning all variants")
                    return selection_result.variant_ids
                    
            except Exception as e:
                add_debug_log(f"⚠️ AI color selection failed: {e}")
                # Fall through to fallback method
        
        # Fallback: Basic color extraction and matching
        add_debug_log("Using fallback color selection")
        available_colors = []
        colors_set = set()
        
        for variant in all_variants:
            color = variant.get("options", {}).get("color", "")
            if color:
                primary_color = color.split('/')[0].strip()
                primary_color = primary_color.split(' patch')[0].strip()
                if primary_color:
                    colors_set.add(primary_color.title())
        
        available_colors = sorted(list(colors_set))
        current_product_memory["available_colors"] = available_colors
        
        if not requested_color:
            return [v["id"] for v in all_variants]
        
        # Basic color matching as fallback
        for variant in all_variants:
            color = variant.get("options", {}).get("color", "").lower()
            if requested_color.lower() in color or color in requested_color.lower():
                current_product_memory["current_color"] = requested_color
                return [v["id"] for v in all_variants if requested_color.lower() in v.get("options", {}).get("color", "").lower()]
        
        # No match found
        return {
            "error": "color_not_found", 
            "available_colors": available_colors,
            "requested_color": requested_color
        }
        
    except Exception as e:
        add_debug_log(f"❌ Error in get_variants_for_product: {e}")
        return []

@app.route('/', methods=['GET', 'POST'])
def index():
    global chat_history, current_logo_settings
    
    mockup_url = None
    attempted_searches = []
    image_url = None
    search_term = None
    error_message = None
    success = False
    user_message = ""
    
    if request.method == 'POST':
        # Check if logo positioning controls were included in the form submission
        if 'logo_scale' in request.form:
            try:
                current_logo_settings["scale"] = float(request.form.get('logo_scale', 1.0))
                current_logo_settings["x"] = float(request.form.get('logo_x', 0.5))
                current_logo_settings["y"] = float(request.form.get('logo_y', 0.5))
                
                # Ensure values are within valid ranges
                current_logo_settings["scale"] = max(0.1, min(2.0, current_logo_settings["scale"]))
                current_logo_settings["x"] = max(0.0, min(1.0, current_logo_settings["x"]))
                current_logo_settings["y"] = max(0.0, min(1.0, current_logo_settings["y"]))
                
                print(f"Updated logo settings from form: {current_logo_settings}")
            except (ValueError, TypeError) as e:
                print(f"Error updating logo settings: {e}")
        
        if 'reset' in request.form:
            # Reset chat history and logo settings
            chat_history = []
            current_logo_settings = default_logo_settings.copy()
            # Reset product memory
            current_product_memory.update({
                "blueprint_id": None,
                "blueprint_title": None,
                "print_provider_id": None,
                "current_color": None,
                "available_colors": [],
                "last_mockup_url": None
            })
            # Clear debug logs
            debug_logs.clear()
            add_debug_log("🔄 Conversation reset - all memory cleared")
            add_debug_log(f"📋 Product memory after reset: {current_product_memory}")
        elif 'message' in request.form and request.form['message'].strip():
            # Reset previous product display when starting a new search
            mockup_url = None
            attempted_searches = []
            success = False
            error_message = None
            
            user_message = request.form['message'].strip()
            if 'image_url' in request.form:
                image_url = request.form['image_url']
            
            # Add user message to chat history first
            add_message_to_chat("user", user_message)
            add_debug_log(f"💬 User message: {user_message}")
            
            # =================================================================
            # MODERN APPROACH: All user requests are now handled by the LLM
            # =================================================================
            # REMOVED: Legacy color availability detection - the LLM now handles
            # all types of questions including color availability inquiries
            # intelligently within the main conversation flow.
            
            # Check if this is a color change request
            color_change_request = any(phrase in user_message.lower() for phrase in 
                                     ["make it", "change", "color", "blue", "red", "green", "black", "white"])
            
            # Check if this is a product type change request (like "make it a shirt")
            product_type_change_request = any(phrase in user_message.lower() for phrase in 
                                          ["make it a", "change to", "switch to", "i want a", 
                                           "show me a", "get me a", "now make it a", "can i see a"])
            
            add_debug_log(f"🔍 Request analysis - Color change: {color_change_request}, Product change: {product_type_change_request}")
            
            # Check if this is a recommendation request
            recommendation_request = any(term in user_message.lower() 
                               for term in ['recommend', 'suggestion', 'ideas', 'what about', 
                                          'what else', 'other products', 'other options', 
                                          'what would be good', 'cool gift', 'team gift',
                                          'what should i', 'what can i', 'can you suggest',
                                          'swag', 'merchandise', 'merch'])
            
            # Initialize processing flags
            color_change_handled = False
            should_create_product = False
            
            # If this is a color change request, keep the same product but change color
            if color_change_request and not product_type_change_request:
                # Extract the current product type from chat history or memory
                current_product = extract_current_product_type(chat_history)
                search_term = current_product
                add_debug_log(f"🎨 Color change requested for: {search_term}")
                should_create_product = True
                
                # Extract the requested color
                requested_color = extract_color_from_message(user_message)
                if requested_color:
                    add_message_to_chat("assistant", f"Let me show you a {requested_color} {search_term}!")
                else:
                    add_message_to_chat("assistant", f"Let me update the {search_term} for you!")
                
                # Create a simple suggestion object for consistency  
                suggestion = {"search_term": search_term, "conversational": False, "adjust_logo": False}
                
                # Skip LLM processing for color changes - we already have what we need
                add_debug_log(f"🎨 Color change complete, proceeding with search_term: {search_term}")
                
                # Set a flag to prevent re-processing
                color_change_handled = True
            # If this is a product type change, extract the new product type directly
            elif product_type_change_request:
                # Get what product they want to change to
                search_term = None
                
                # Common product types to look for
                product_types = ['t-shirt', 'tee', 'shirt', 'hoodie', 'sweatshirt', 
                                'hat', 'cap', 'mug', 'cup', 'bag', 'tote']
                
                for product_type in product_types:
                    if product_type in user_message.lower():
                        search_term = product_type
                        # For "shirt" we want to be more specific - prioritize t-shirt unless sweatshirt is specified
                        if product_type == "shirt":
                            if "sweat" in user_message.lower() or "hoodie" in user_message.lower():
                                search_term = "sweatshirt" 
                            elif "t-" in user_message.lower() or "tee" in user_message.lower():
                                search_term = "t-shirt"
                            else:
                                search_term = "t-shirt"  # Default to t-shirt when just "shirt" is specified
                        break
                
                if search_term:
                    print(f"Product type change requested: {search_term}")
                    should_create_product = True
                    add_message_to_chat("assistant", f"Let me show you a {search_term} instead.")
                else:
                    # If no specific product type found in the request, use AI suggestion
                    suggestion, ai_response = get_ai_suggestion(user_message)
                    search_term = suggestion.get('search_term')
                    print(f"Original search term from AI: {search_term}")  # Debug
                    
                    if not image_url and 'image_url' in suggestion:
                        image_url = suggestion.get('image_url')
                        
                    # Check if this is a logo adjustment request
                    adjust_logo = suggestion.get('adjust_logo', False)
                    should_create_product = not adjust_logo
            else:
                # ================================================================
                # MODERN APPROACH: All requests handled by intelligent LLM system
                # ================================================================
                # REMOVED: Legacy detect_simple_product_request() function
                # The LLM now handles ALL product requests intelligently, including
                # simple ones like "hat" or "mug" as well as complex descriptions.
                
                add_debug_log(f"🤖 Calling LLM system for: '{user_message}'")
                # Get AI suggestion for all types of requests
                suggestion, ai_response = get_ai_suggestion(user_message)
                search_term = suggestion.get('search_term')
                add_debug_log(f"🤖 LLM selected product: {search_term}")
                
                # If this is a purely conversational message, just show the conversation without creating a product
                if suggestion.get('conversational', False):
                    should_create_product = False
                    # Keep the current mockup if there is one
                    if 'mockup_url' in request.form and request.form['mockup_url']:
                        mockup_url = request.form['mockup_url']
                    return render_template('index.html', mockup_url=mockup_url, attempted_searches=attempted_searches, 
                                          search_term=search_term, image_url=image_url, chat_history=chat_history,
                                          error_message=error_message, success=success, user_message="",
                                          current_logo_settings=current_logo_settings, debug_logs=debug_logs)
                
                if not image_url and 'image_url' in suggestion:
                    image_url = suggestion.get('image_url')
                
                # Handle potential hallucinated products
                if any(term.lower() in user_message.lower() for term in ["how about", "what about", "try the", "can i get the"]):
                    # Get the actual product catalog to verify if the requested product exists
                    product_categories = get_all_available_products()
                    all_products = []
                    for products in product_categories.values():
                        all_products.extend(products)
                    
                    # Extract a potential product name from the user's message
                    # Remove common phrases to isolate the product name
                    cleaned_message = user_message.lower()
                    for phrase in ["how about", "what about", "try the", "can i get", "the", "a", "that"]:
                        cleaned_message = cleaned_message.replace(phrase, "").strip()
                    
                    potential_product_name = cleaned_message.strip()
                    print(f"User is asking for specific product: '{potential_product_name}'")
                    
                    # Check if the requested product exists in our catalog
                    product_exists = False
                    best_match = None
                    for product in all_products:
                        # Exact match
                        if potential_product_name.lower() == product['title'].lower():
                            product_exists = True
                            best_match = product['title']
                            break
                        # Partial match (product title contains the search term)
                        elif potential_product_name.lower() in product['title'].lower():
                            product_exists = True
                            best_match = product['title']
                            # Don't break - keep looking for exact matches
                    
                    if product_exists:
                        print(f"Found requested product in catalog: {best_match}")
                        search_term = best_match
                    else:
                        print(f"WARNING: Requested product '{potential_product_name}' does not exist in the catalog! This may be a hallucinated recommendation.")
                        
                        # Use intelligent error handling for product not found
                        recovery_message = handle_product_not_found(user_message, potential_product_name)
                        add_message_to_chat("assistant", recovery_message)
                        
                        # Fallback to basic product suggestion if error handler fails
                        search_term = "t-shirt"
                
                # If the request was for logo adjustment, use the same product type with new settings
                adjust_logo = suggestion.get('adjust_logo', False)
                should_create_product = True
                
                if adjust_logo:
                    # We'll try to create a product with the same terms but adjusted logo
                    attempted_terms = []
                    
                    # Use the suggested search term from the adjustment function
                    # This should be the exact product name from the previous success
                    attempted_terms.append(search_term)
                    attempted_searches.append(search_term)
                    
                    try:
                        # First try to find the exact product by its full name
                        blueprint_id, blueprint_title = find_blueprint_id(search_term)
                        
                        # If that fails, try to find a product of the same general type
                        if not blueprint_id:
                            # Extract a more generic product type from the search term
                            generic_types = ['sweatshirt', 'hoodie', 'shirt', 't-shirt', 'hat', 'mug']
                            for generic_type in generic_types:
                                if generic_type in search_term.lower():
                                    print(f"Trying generic type: {generic_type} instead of {search_term}")
                                    blueprint_id, blueprint_title = find_blueprint_id(generic_type)
                                    if blueprint_id:
                                        break
                        
                        if blueprint_id:
                            providers = get_print_providers(blueprint_id)
                            if providers:
                                print_provider_id = providers[0]['id']
                                
                                shop_id = get_shop_id()
                                image_id = upload_image(image_url)
                                
                                # Extract color from user message
                                requested_color = extract_color_from_message(user_message)
                                
                                # If a color was requested, filter variants for that color
                                variant_ids = get_variants_for_product(blueprint_id, print_provider_id, requested_color)
                                
                                # Check if color was not found
                                if isinstance(variant_ids, dict) and variant_ids.get("error") == "color_not_found":
                                    available_colors = variant_ids["available_colors"]
                                    requested_color_name = variant_ids["requested_color"]
                                    
                                    # Format the available colors nicely
                                    if len(available_colors) <= 3:
                                        colors_text = ", ".join(available_colors)
                                    else:
                                        colors_text = ", ".join(available_colors[:3]) + f", and {len(available_colors)-3} more"
                                    
                                    error_message = f"Sorry, '{requested_color_name}' is not available for this {blueprint_title}. Available colors are: {colors_text}. Please try one of these colors instead!"
                                    add_message_to_chat("assistant", error_message)
                                    # Don't try to create the product, just return with error
                                    return render_template('index.html', mockup_url=mockup_url, attempted_searches=attempted_searches, 
                                                          search_term=search_term, image_url=image_url, chat_history=chat_history,
                                                          error_message=error_message, success=False, user_message="",
                                                          current_logo_settings=current_logo_settings, debug_logs=debug_logs)
                                
                                product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                mockup_url = get_mockup_image(shop_id, product_id)
                                
                                success = True
                                
                                # Update product memory for logo adjustments too
                                current_product_memory.update({
                                    "blueprint_id": blueprint_id,
                                    "blueprint_title": blueprint_title,
                                    "print_provider_id": print_provider_id,
                                    "last_mockup_url": mockup_url
                                })
                                
                                # Don't add a second confirmation message here since we already added the logo adjustment one
                                # in the get_ai_suggestion function
                                
                            else:
                                error_message = f"Sorry, I couldn't adjust the logo on that product. The product may no longer be available."
                                add_message_to_chat("assistant", error_message)
                        else:
                            error_message = f"Sorry, I couldn't find that product type anymore. Would you like to try a different product?"
                            add_message_to_chat("assistant", error_message)
                    except Exception as e:
                        error_message = f"Error adjusting the logo: {str(e)}"
                        add_message_to_chat("assistant", error_message)
                        
                # If this was a recommendation request, we already added the conversation response to chat history,
                # and we'll only try to create a product if the user specifically asked for it
                elif recommendation_request and "show me" not in user_message.lower() and "create" not in user_message.lower():
                    # The conversational response has already been added to chat history in get_ai_suggestion
                    should_create_product = False
                    # Preserve the current mockup if there is one
                    if 'mockup_url' in request.form and request.form['mockup_url']:
                        mockup_url = request.form['mockup_url']
                        success = True
            
            # Try up to 3 search terms if we should create a product
            if should_create_product:
                original_search_term = search_term
                attempted_terms = []  # Track all terms we've tried to avoid duplicates
                
                # First try the original term
                for attempt in range(3):
                    # Skip this term if we've already tried it
                    if search_term in attempted_terms:
                        continue
                        
                    attempted_terms.append(search_term)
                    attempted_searches.append(search_term)
                    print(f"Attempt {attempt+1}, using search term: {search_term}")
                    
                    try:
                        add_debug_log(f"🔍 Searching for blueprint with term: '{search_term}'")
                        blueprint_id, blueprint_title = find_blueprint_id(search_term)
                        add_debug_log(f"📦 Found blueprint: ID={blueprint_id}, Title='{blueprint_title}'")
                        if blueprint_id:
                            providers = get_print_providers(blueprint_id)
                            if providers:
                                print_provider_id = providers[0]['id']
                                
                                shop_id = get_shop_id()
                                image_id = upload_image(image_url)
                                
                                # Extract color from user message
                                requested_color = extract_color_from_message(user_message)
                                
                                # If a color was requested, filter variants for that color
                                variant_ids = get_variants_for_product(blueprint_id, print_provider_id, requested_color)
                                
                                # Check if color was not found
                                if isinstance(variant_ids, dict) and variant_ids.get("error") == "color_not_found":
                                    available_colors = variant_ids["available_colors"]
                                    requested_color_name = variant_ids["requested_color"]
                                    
                                    add_debug_log(f"🎨 Color '{requested_color_name}' not available for {blueprint_title}")
                                    add_debug_log(f"📋 Available colors: {available_colors}")
                                    
                                    # Format the available colors nicely
                                    if len(available_colors) <= 3:
                                        colors_text = ", ".join(available_colors)
                                    else:
                                        colors_text = ", ".join(available_colors[:3]) + f", and {len(available_colors)-3} more"
                                    
                                    error_message = f"Sorry, '{requested_color_name}' is not available for this {blueprint_title}. Available colors are: {colors_text}. Please try one of these colors instead!"
                                    add_message_to_chat("assistant", error_message)
                                    break  # Exit the attempt loop and show error
                                
                                product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                mockup_url = get_mockup_image(shop_id, product_id)
                                
                                success = True
                                
                                # Update product memory
                                current_product_memory.update({
                                    "blueprint_id": blueprint_id,
                                    "blueprint_title": blueprint_title,
                                    "print_provider_id": print_provider_id,
                                    "last_mockup_url": mockup_url
                                })
                                
                                # Only add this success message if we're not handling a logo adjustment
                                # (which would have its own message already)
                                if not suggestion.get('adjust_logo', False) and "logo" not in user_message.lower():
                                    add_message_to_chat("assistant", f"I found a {blueprint_title} product for you! Here's what it looks like with your image.")
                                    
                                    # Show available colors after successful product creation (if no specific color was requested)
                                    if not extract_color_from_message(user_message) and current_product_memory["available_colors"]:
                                        colors_text = ", ".join(current_product_memory["available_colors"])
                                        color_message = f"Available colors: {colors_text}. Just say 'make it [color]' to change the color!"
                                        add_message_to_chat("assistant", color_message)
                                
                                break
                    except Exception as e:
                        print(f"Error processing product: {e}")
                        if attempt == 2:  # On the last attempt, propagate the error to the user
                            error_message = f"Error creating product: {str(e)}"
                    
                    if not success and attempt < 2:  # Try another search term if this isn't the last attempt
                        if attempt == 0:
                            # First fallback: Try splitting compound words
                            add_message_to_chat("assistant", f"I couldn't find a product for '{search_term}'. Let me suggest some alternatives.")
                                
                            # Instead of just trying alternatives automatically, let's have the AI suggest options
                            product_categories = get_all_available_products()
                            # Find categories similar to the search term
                            similar_categories = []
                            for category in product_categories.keys():
                                # Use fuzzy matching or keyword matching to find related categories
                                if (category in search_term.lower() or search_term.lower() in category or
                                    any(word in category for word in search_term.lower().split())):
                                    similar_categories.append(category)
                            
                            # If we found similar categories, use them for suggestions
                            if similar_categories:
                                suggestions_prompt = f"""The user was looking for '{search_term}' but it's not available. 
Based on their request, suggest 2-3 specific alternatives from these available categories: {', '.join(similar_categories)}.
Explain briefly why each alternative might work for their needs. Be conversational and helpful."""
                            else:
                                # If no similar categories, suggest popular products
                                popular_categories = ['t-shirt', 'hat', 'mug', 'tote', 'sticker']
                                suggestions_prompt = f"""The user was looking for '{search_term}' but it's not available.
Suggest 2-3 alternatives from these popular products: {', '.join(popular_categories)}.
Explain briefly why each alternative might work for their needs. Be conversational and helpful."""
                            
                            try:
                                # Ask the AI for suggestions
                                suggestions_response = openai.chat.completions.create(
                                    model="gpt-3.5-turbo",
                                    messages=[
                                        {"role": "system", "content": "You are a helpful merchandise assistant suggesting alternative products."},
                                        *chat_history,
                                        {"role": "user", "content": suggestions_prompt}
                                    ]
                                )
                                
                                suggestions_message = suggestions_response.choices[0].message.content
                                # Add the suggestions to chat history
                                add_message_to_chat("assistant", suggestions_message)
                                
                                # Extract a product from the suggestions to try
                                # Check for compound words first
                                compound_alternatives = handle_compound_words(search_term)
                                if compound_alternatives:
                                    # Try each alternative until one works
                                    for alt_term in compound_alternatives:
                                        if alt_term not in attempted_terms:
                                            search_term = alt_term
                                            break
                                else:
                                    # If not a compound word, try our standard simplification
                                    simplified_term = simplify_search_term(original_search_term)
                                    if simplified_term and simplified_term != original_search_term and simplified_term not in attempted_terms:
                                        search_term = simplified_term
                                    else:
                                        # Use sweatshirt as first fallback for sweat-related terms
                                        if "sweat" in original_search_term.lower() or "hoodie" in original_search_term.lower():
                                            search_term = "sweatshirt"
                                        elif "hat" in original_search_term.lower():
                                            search_term = "hat" 
                                        else:
                                            search_term = "t-shirt"
                            except Exception as e:
                                print(f"Error getting suggestions: {e}")
                                # Fall back to our original logic
                                compound_alternatives = handle_compound_words(search_term)
                                if compound_alternatives:
                                    for alt_term in compound_alternatives:
                                        if alt_term not in attempted_terms:
                                            search_term = alt_term
                                            break
                                else:
                                    simplified_term = simplify_search_term(original_search_term)
                                    if simplified_term and simplified_term != original_search_term and simplified_term not in attempted_terms:
                                        search_term = simplified_term
                                    else:
                                        # Use sweatshirt as first fallback for sweat-related terms
                                        if "sweat" in original_search_term.lower() or "hoodie" in original_search_term.lower():
                                            search_term = "sweatshirt"
                                        elif "hat" in original_search_term.lower():
                                            search_term = "hat" 
                                        else:
                                            search_term = "t-shirt"
                        else:
                            # Second fallback: Use a generic product type but be more conversational
                            add_message_to_chat("assistant", f"I'm still looking for the perfect item for you. Let me try a different product type that might work for your needs.")
                            
                            # Check what basic types we haven't tried yet
                            if "sweat" in original_search_term.lower() and "sweatshirt" not in attempted_terms:
                                search_term = "sweatshirt" 
                            elif "hoodie" in original_search_term.lower() and "sweatshirt" not in attempted_terms:
                                search_term = "sweatshirt"
                            elif "hat" in original_search_term.lower() and "hat" not in attempted_terms:
                                search_term = "hat" 
                            elif "shirt" in original_search_term.lower() and "t-shirt" not in attempted_terms:
                                search_term = "t-shirt"
                            elif "mug" in original_search_term.lower() and "mug" not in attempted_terms:
                                search_term = "mug"
                            elif "lamp" in original_search_term.lower() and "lamp" not in attempted_terms:
                                search_term = "lamp"
                            elif "light" in original_search_term.lower() and "lamp" not in attempted_terms:
                                search_term = "lamp"
                            elif "sweatshirt" not in attempted_terms:
                                search_term = "sweatshirt"  # Try sweatshirt as an early fallback
                            elif "t-shirt" not in attempted_terms:
                                search_term = "t-shirt"  # Common item as default
                            elif "hat" not in attempted_terms:
                                search_term = "hat"
                            elif "mug" not in attempted_terms:
                                search_term = "mug"
                            else:
                                search_term = "tote"  # Try something completely different
                
                if not success:
                    error_message = error_message or "I've tried several options but couldn't find exactly what you're looking for. Let me know if you'd like me to suggest some other products that might work for you."
                    add_message_to_chat("assistant", error_message)
        else:
            # Manual form submission
            search_term = request.form.get('search_term', '').strip()
            if search_term:
                image_url = request.form.get('image_url', '').strip()
                
                attempted_searches.append(search_term)
                
                try:
                    blueprint_id, blueprint_title = find_blueprint_id(search_term)
                    if blueprint_id:
                        providers = get_print_providers(blueprint_id)
                        if providers:
                            print_provider_id = providers[0]['id']
                            
                            shop_id = get_shop_id()
                            image_id = upload_image(image_url)
                            
                            # Extract color from user message
                            requested_color = extract_color_from_message(search_term)
                            
                            # If a color was requested, filter variants for that color
                            variant_ids = get_variants_for_product(blueprint_id, print_provider_id, requested_color)
                            
                            # Check if color was not found
                            if isinstance(variant_ids, dict) and variant_ids.get("error") == "color_not_found":
                                available_colors = variant_ids["available_colors"]
                                requested_color_name = variant_ids["requested_color"]
                                
                                # Format the available colors nicely
                                if len(available_colors) <= 3:
                                    colors_text = ", ".join(available_colors)
                                else:
                                    colors_text = ", ".join(available_colors[:3]) + f", and {len(available_colors)-3} more"
                                
                                error_message = f"Sorry, '{requested_color_name}' is not available for this {blueprint_title}. Available colors are: {colors_text}. Please try one of these colors instead!"
                            else:
                                product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                mockup_url = get_mockup_image(shop_id, product_id)
                                success = True
                                
                                # Update product memory
                                current_product_memory.update({
                                    "blueprint_id": blueprint_id,
                                    "blueprint_title": blueprint_title,
                                    "print_provider_id": print_provider_id,
                                    "last_mockup_url": mockup_url
                                })
                        else:
                            error_message = f"No print providers found for '{search_term}'."
                    else:
                        error_message = f"No product found for '{search_term}'. Try a different search term."
                        # Try with a simpler term
                        simplified = simplify_search_term(search_term)
                        if simplified != search_term:
                            attempted_searches.append(simplified)
                            blueprint_id, blueprint_title = find_blueprint_id(simplified)
                            if blueprint_id:
                                providers = get_print_providers(blueprint_id)
                                if providers:
                                    print_provider_id = providers[0]['id']
                                    
                                    shop_id = get_shop_id()
                                    image_id = upload_image(image_url)
                                    
                                    # Extract color from user message
                                    requested_color = extract_color_from_message(search_term)
                                    
                                    # If a color was requested, filter variants for that color
                                    variant_ids = get_variants_for_product(blueprint_id, print_provider_id, requested_color)
                                    
                                    # Check if color was not found
                                    if isinstance(variant_ids, dict) and variant_ids.get("error") == "color_not_found":
                                        available_colors = variant_ids["available_colors"]
                                        requested_color_name = variant_ids["requested_color"]
                                        
                                        # Format the available colors nicely
                                        if len(available_colors) <= 3:
                                            colors_text = ", ".join(available_colors)
                                        else:
                                            colors_text = ", ".join(available_colors[:3]) + f", and {len(available_colors)-3} more"
                                        
                                        error_message = f"Sorry, '{requested_color_name}' is not available for this {blueprint_title}. Available colors are: {colors_text}. Please try one of these colors instead!"
                                    else:
                                        product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                        mockup_url = get_mockup_image(shop_id, product_id)
                                        success = True
                                        error_message = None
                                        
                                        # Update product memory
                                        current_product_memory.update({
                                            "blueprint_id": blueprint_id,
                                            "blueprint_title": blueprint_title,
                                            "print_provider_id": print_provider_id,
                                            "last_mockup_url": mockup_url
                                        })
                except Exception as e:
                    error_message = f"Error: {str(e)}"
    
    # Clear user message after processing and include current logo settings in the template context
    return render_template('index.html', mockup_url=mockup_url, attempted_searches=attempted_searches, 
                          search_term=search_term, image_url=image_url, chat_history=chat_history,
                          error_message=error_message, success=success, user_message="",
                          current_logo_settings=current_logo_settings, debug_logs=debug_logs)

@app.route('/logs')
def view_logs():
    """View the server logs (in-memory for Vercel)"""
    if not server_logs:
        return "<p>No logs yet. Try using the app first to generate some logs.</p>"
    
    logs_text = "\n".join(server_logs)
    return f"""
    <html>
    <head><title>MiM Server Logs</title></head>
    <body>
        <h2>MiM Server Logs (Last {len(server_logs)} entries)</h2>
        <p><a href="/logs/download">Download as text file</a></p>
        <pre style='font-family: monospace; font-size: 12px; white-space: pre-wrap; background: #f5f5f5; padding: 10px; border: 1px solid #ddd;'>{logs_text}</pre>
    </body>
    </html>
    """

@app.route('/logs/download')
def download_logs():
    """Download the log file (in-memory for Vercel)"""
    if not server_logs:
        return "No logs available yet."
    
    logs_text = "\n".join(server_logs)
    from flask import Response
    return Response(
        logs_text,
        mimetype="text/plain",
        headers={"Content-disposition": "attachment; filename=mim_server_logs.txt"}
    )

# For Vercel deployment
app = app

# Your approved whitelist
APPROVED_PRODUCTS = {
    "hoodie": 49,  # Unisex Heavy Blend™ Crewneck Sweatshirt
    "blanket": 439,  # Three-Panel Fleece Hoodie  
    "stickers": 400,  # Kiss-Cut Stickers
    "bucket_hat": 1910,  # Bucket Hat (Embroidery)
    "towel": 352,  # Beach Towel
    # ... add more as needed
}

if __name__ == '__main__':
    # For local development
    app.run(debug=True, port=5000)