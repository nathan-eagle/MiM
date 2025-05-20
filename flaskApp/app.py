from flask import Flask, request, render_template, redirect, url_for, jsonify
import requests
import time
import openai
import re
import os

app = Flask(__name__)

# Configure OpenAI API
# Use environment variable for API key or set a placeholder
openai.api_key = os.environ.get("OPENAI_API_KEY", "your-api-key")

# Use environment variable for API token or set a placeholder
API_TOKEN = os.environ.get("PRINTIFY_API_TOKEN", "your-printify-token")
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
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

def get_all_available_products():
    """Get a list of all available products from Printify API"""
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
    url = "https://api.printify.com/v1/catalog/blueprints.json"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    blueprints = res.json()
    
    # First, try to find an exact match (case insensitive)
    search_term_lower = search_term.lower()
    for blueprint in blueprints:
        if search_term_lower == blueprint['title'].lower():
            print(f"Found exact match: {blueprint['title']}")
            return blueprint['id'], blueprint['title']
    
    # Next, try to find a blueprint that contains the search term as a substring
    for blueprint in blueprints:
        if search_term_lower in blueprint['title'].lower():
            print(f"Found partial match: {blueprint['title']}")
            return blueprint['id'], blueprint['title']
            
    # If no match found, try a more flexible approach by checking if all words in search_term
    # appear in the blueprint title (in any order)
    search_words = set(search_term_lower.split())
    for blueprint in blueprints:
        title_words = set(blueprint['title'].lower().split())
        # Check if all words in search_term are in title
        if search_words.issubset(title_words):
            print(f"Found word match: {blueprint['title']}")
            return blueprint['id'], blueprint['title']
    
    # For longer search terms, try matching with the most significant words
    if len(search_words) > 2:
        # Remove common words that might cause issues
        stop_words = {'a', 'an', 'the', 'and', 'or', 'but', 'of', 'for', 'with'}
        filtered_search_words = search_words - stop_words
        
        best_match = None
        best_match_score = 0
        
        for blueprint in blueprints:
            title_words = set(blueprint['title'].lower().split())
            # Count how many significant words match
            match_count = len(filtered_search_words.intersection(title_words))
            
            # Check if this is the best match so far
            if match_count > best_match_score:
                best_match_score = match_count
                best_match = blueprint
        
        # If we found a decent match (at least 50% of significant words match)
        if best_match and best_match_score >= len(filtered_search_words) / 2:
            print(f"Found word similarity match: {best_match['title']}")
            return best_match['id'], best_match['title']
    
    # If all attempts fail, return None
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
    
    product_payload = {
        "title": "Custom Product",
        "description": "A custom product with a logo.",
        "blueprint_id": blueprint_id,
        "print_provider_id": print_provider_id,
        "variants": [{"id": vid, "price": 1999, "is_enabled": True} for vid in variant_ids[:10]],  # Limit to first 10 variants
        "print_areas": [
            {
                "variant_ids": variant_ids[:10],  # Limit to first 10 variants
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
        return res.json()["id"]
    except requests.exceptions.HTTPError as e:
        print(f"Error creating product: {e}")
        print(f"Response content: {e.response.content}")
        if len(variant_ids) > 1:
            # Try again with just one variant
            return create_product_single_variant(shop_id, blueprint_id, print_provider_id, image_id, variant_ids[0])
        raise e

def create_product_single_variant(shop_id, blueprint_id, print_provider_id, image_id, variant_id):
    """Fallback method to create product with just a single variant"""
    global current_logo_settings
    
    product_payload = {
        "title": "Custom Product",
        "description": "A custom product with a logo.",
        "blueprint_id": blueprint_id,
        "print_provider_id": print_provider_id,
        "variants": [{"id": variant_id, "price": 1999, "is_enabled": True}],
        "print_areas": [
            {
                "variant_ids": [variant_id],
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
    res = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products.json", headers=headers, json=product_payload)
    res.raise_for_status()
    return res.json()["id"]

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

def get_ai_suggestion(user_message):
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

def adjust_logo_settings(user_message):
    """Adjust logo size and position based on user commands"""
    global current_logo_settings
    
    msg = user_message.lower()
    
    # Handle size adjustments
    if 'smaller' in msg:
        # Reduce scale by 25%
        current_logo_settings["scale"] = max(0.1, current_logo_settings["scale"] * 0.75)
    elif any(term in msg for term in ['bigger', 'larger']):
        # Increase scale by 25%
        current_logo_settings["scale"] = min(2.0, current_logo_settings["scale"] * 1.25)
    
    # Handle position adjustments
    # Check for corner positions first (these are combinations of directions)
    if 'top right' in msg or 'upper right' in msg:
        current_logo_settings["x"] = 0.8  # Move right
        current_logo_settings["y"] = 0.2  # Move up
    elif 'top left' in msg or 'upper left' in msg:
        current_logo_settings["x"] = 0.2  # Move left
        current_logo_settings["y"] = 0.2  # Move up
    elif 'bottom right' in msg or 'lower right' in msg:
        current_logo_settings["x"] = 0.8  # Move right
        current_logo_settings["y"] = 0.8  # Move down
    elif 'bottom left' in msg or 'lower left' in msg:
        current_logo_settings["x"] = 0.2  # Move left
        current_logo_settings["y"] = 0.8  # Move down
    elif 'center' in msg:
        current_logo_settings["x"] = 0.5
        current_logo_settings["y"] = 0.5
    # Handle individual direction adjustments
    else:
        if 'left' in msg:
            # Move left by reducing x by 25% of available space
            current_logo_settings["x"] = max(0.1, current_logo_settings["x"] - 0.25)
        elif 'right' in msg:
            # Move right by increasing x by 25% of available space
            current_logo_settings["x"] = min(0.9, current_logo_settings["x"] + 0.25)
        
        if 'up' in msg or 'top' in msg:
            # Move up by reducing y by 25% of available space
            current_logo_settings["y"] = max(0.1, current_logo_settings["y"] - 0.25)
        elif 'down' in msg or 'bottom' in msg:
            # Move down by increasing y by 25% of available space
            current_logo_settings["y"] = min(0.9, current_logo_settings["y"] + 0.25)
    
    # Round values to 2 decimal places for cleaner display
    current_logo_settings["scale"] = round(current_logo_settings["scale"], 2)
    current_logo_settings["x"] = round(current_logo_settings["x"], 2)
    current_logo_settings["y"] = round(current_logo_settings["y"], 2)
    
    print(f"Adjusted logo settings: {current_logo_settings}")

def extract_current_product_type(chat_history):
    """Extract the most recent product type from chat history"""
    # Look through recent messages to find a product mention
    product_types = ['t-shirt', 'shirt', 'hat', 'mug', 'tote', 'bag', 'sticker', 'poster', 'sweatshirt', 'hoodie']
    
    # Keep track of the most recent exact product name found
    exact_product_name = None
    
    # First, look for success messages with product names
    for msg in reversed(chat_history):
        if msg["role"] == "assistant" and "found a" in msg["content"].lower():
            # Extract the product type from a success message like "I found a Hat product for you!"
            content = msg["content"].lower()
            product_match = re.search(r"found a ([^!]+) product", content)
            if product_match:
                found_product = product_match.group(1).strip().lower()
                # Save the exact product name
                exact_product_name = found_product
                # Get the main product type
                for product in product_types:
                    if product in found_product.lower():
                        print(f"Found product type from success message: {product}")
                        return found_product
    
    # Next, check for product change messages like "Let me show you a t-shirt instead"
    for msg in reversed(chat_history):
        if msg["role"] == "assistant" and "show you a" in msg["content"].lower():
            content = msg["content"].lower()
            product_match = re.search(r"show you a ([^ ]+)", content)
            if product_match:
                product_type = product_match.group(1).strip().lower()
                print(f"Found product type from change message: {product_type}")
                return product_type
    
    # If we found an exact product name, return it
    if exact_product_name:
        print(f"Using exact product name: {exact_product_name}")
        return exact_product_name
    
    # If adjusting a logo but no product found in messages, check the last product type request
    for msg in reversed(chat_history):
        if msg["role"] == "user" and any(request in msg["content"].lower() for request in ["make it a", "i want a", "let me see a"]):
            for product in product_types:
                if product in msg["content"].lower():
                    # If user specifically asked for a product type, use that
                    if product == "shirt" and ("t-" in msg["content"].lower() or "tee" in msg["content"].lower()):
                        print(f"Found t-shirt from user request")
                        return "t-shirt"
                    elif product == "shirt" and ("sweat" in msg["content"].lower() or "hoodie" in msg["content"].lower()):
                        print(f"Found sweatshirt from user request")
                        return "sweatshirt"
                    print(f"Found {product} from user request")
                    return product
    
    # Look for any t-shirt related request as a priority
    for msg in reversed(chat_history):
        if msg["role"] == "user" and "t-shirt" in msg["content"].lower():
            print("Defaulting to t-shirt based on history")
            return "t-shirt"
    
    # Default fallback to t-shirt instead of hat
    print("Using default fallback: t-shirt")
    return "t-shirt"

def generate_logo_adjustment_response(user_message):
    """Generate a response about the logo adjustment"""
    msg = user_message.lower()
    response = "I've "
    
    # Track which adjustments were made
    size_adjusted = False
    position_adjusted = False
    position_type = None
    
    if 'smaller' in msg:
        response += "made the logo smaller"
        size_adjusted = True
    elif any(term in msg for term in ['bigger', 'larger']):
        response += "made the logo bigger"
        size_adjusted = True
    
    if 'top right' in msg or 'upper right' in msg:
        position_type = "to the top right corner"
        position_adjusted = True
    elif 'top left' in msg or 'upper left' in msg:
        position_type = "to the top left corner"
        position_adjusted = True
    elif 'bottom right' in msg or 'lower right' in msg:
        position_type = "to the bottom right corner" 
        position_adjusted = True
    elif 'bottom left' in msg or 'lower left' in msg:
        position_type = "to the bottom left corner"
        position_adjusted = True
    elif 'left' in msg:
        position_type = "to the left"
        position_adjusted = True
    elif 'right' in msg:
        position_type = "to the right"
        position_adjusted = True
    elif 'up' in msg or 'top' in msg:
        position_type = "up"
        position_adjusted = True
    elif 'down' in msg or 'bottom' in msg:
        position_type = "down"
        position_adjusted = True
    elif 'center' in msg:
        position_type = "to the center"
        position_adjusted = True
    
    # Combine the adjustments in the response
    if size_adjusted and position_adjusted:
        response += f" and moved it {position_type}"
    elif position_adjusted:
        response += f"moved the logo {position_type}"
    elif not size_adjusted:
        response += "adjusted the logo as requested"
        
    response += ". Here's what it looks like now!"
    return response

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

def handle_compound_words(search_term):
    """Break compound words into component parts and try alternatives"""
    # List of common compound words to check
    compounds = {
        'lampshade': ['lamp', 'lamp shade', 'shade'],
        'tshirt': ['t-shirt', 'tee', 'shirt'],
        'phonecases': ['phone case', 'case'],
        'waterbottle': ['water bottle', 'bottle'],
        'coffeemug': ['coffee mug', 'mug'],
        'cellphone': ['phone case', 'phone'],
        'facemask': ['face mask', 'mask'],
        'baseballcap': ['baseball cap', 'cap', 'hat'],
        'sweatshirt': ['sweatshirt', 'hoodie', 'sweater'],
        'unisexheavyblendcrewnecksweat': ['sweatshirt', 'crewneck', 'hoodie']
    }
    
    # Remove spaces and check if it's a known compound word
    no_spaces = search_term.replace(" ", "").lower()
    if no_spaces in compounds:
        return compounds[no_spaces]
    
    # Try to split at common points if it's a long term
    if len(no_spaces) > 6:
        # Try common splits
        for i in range(3, len(no_spaces)-2):
            part1 = no_spaces[:i]
            part2 = no_spaces[i:]
            if part1 in ['lamp', 'phone', 'coffee', 'water', 'face', 'base', 't', 'sweat'] or part2 in ['shade', 'case', 'mug', 'shirt', 'hat', 'mask', 'cap', 'bottle', 'sweatshirt', 'hoodie']:
                return [part1, part2, part1 + " " + part2]
    
    # Special case for sweatshirt-related terms
    if 'sweat' in no_spaces or 'hoodie' in no_spaces or 'crew' in no_spaces:
        return ['sweatshirt', 'hoodie']
    
    return []

def simplify_search_term(search_term):
    """Extract the basic product type from a complex search term"""
    if not search_term or search_term.lower() == "search_term":
        return "hat"  # Default when we get a placeholder
        
    # Common product types on Printify
    # Order matters here - check more specific types first
    basic_types = [
        'sweatshirt', 'hoodie', 'sweater',  # Put these first as they're more specific
        'hat', 'cap', 'beanie', 
        'shirt', 't-shirt', 'tee', 
        'mug', 'cup', 
        'tote', 'bag', 'backpack', 
        'phone case', 'case', 
        'poster', 'sticker', 'socks', 'pillow', 'blanket'
    ]
    
    # First check if any basic type is directly in the search term
    search_lower = search_term.lower()
    
    # Special cases for common products that might get misclassified
    if 'sweat' in search_lower or 'hoodie' in search_lower or 'crew' in search_lower:
        return 'sweatshirt'
        
    # Special case for t-shirt vs. sweatshirt
    if 'shirt' in search_lower:
        if 't-' in search_lower or 'tee' in search_lower:
            return 't-shirt'
        elif 'sweat' not in search_lower and 'hoodie' not in search_lower and 'sweater' not in search_lower:
            # If it's just "shirt" without specifics, and not a sweatshirt, default to t-shirt
            return 't-shirt'
    
    for basic_type in basic_types:
        if basic_type in search_lower:
            return basic_type
    
    # If not found, take only the last word (often the product type)
    words = search_term.split()
    if words:
        # Handle common specific product types
        if "trucker" in search_lower or "truckers" in search_lower:
            return "hat"
            
        # Check if last word is likely a color or modifier
        last_word = words[-1].lower()
        modifiers = ['red', 'blue', 'green', 'black', 'white', 'yellow', 'purple', 'pink', 'orange',
                    'custom', 'premium', 'large', 'small', 'medium', 'xl', 'xxl', 'xxxl']
        if last_word in modifiers and len(words) > 1:
            return words[-2].lower()  # Return second-to-last word
        return last_word
    
    # More intelligent default fallback based on keywords
    if 'wear' in search_lower or 'cloth' in search_lower:
        return 'sweatshirt' if 'sweat' in search_lower else 't-shirt'
    
    return "t-shirt"  # Last resort fallback

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
            
            # Check if this is a product type change request (like "make it a shirt")
            product_type_change_request = any(phrase in user_message.lower() for phrase in 
                                          ["make it a", "change to", "switch to", "i want a", 
                                           "show me a", "get me a", "now make it a", "can i see a"])
            
            # Check if this is a recommendation request
            recommendation_request = any(term in user_message.lower() 
                               for term in ['recommend', 'suggestion', 'ideas', 'what about', 
                                          'what else', 'other products', 'other options', 
                                          'what would be good', 'cool gift', 'team gift',
                                          'what should i', 'what can i', 'can you suggest',
                                          'swag', 'merchandise', 'merch'])
            
            # If this is a product type change, extract the new product type directly
            if product_type_change_request:
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
                # Get AI suggestion for other types of requests
                suggestion, ai_response = get_ai_suggestion(user_message)
                search_term = suggestion.get('search_term')
                print(f"Original search term from AI: {search_term}")  # Debug
                
                # If this is a purely conversational message, just show the conversation without creating a product
                if suggestion.get('conversational', False):
                    should_create_product = False
                    # Keep the current mockup if there is one
                    if 'mockup_url' in request.form and request.form['mockup_url']:
                        mockup_url = request.form['mockup_url']
                    return render_template('index.html', mockup_url=mockup_url, attempted_searches=attempted_searches, 
                                          search_term=search_term, image_url=image_url, chat_history=chat_history,
                                          error_message=error_message, success=success, user_message="",
                                          current_logo_settings=current_logo_settings)
                
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
                        # When a hallucinated product is requested, add a message clarifying it doesn't exist
                        not_found_message = f"I'm sorry, but I couldn't find a product called '{potential_product_name}' in our catalog. It seems I suggested a product that isn't actually available. Let me recommend something that definitely exists instead."
                        add_message_to_chat("assistant", not_found_message)
                        
                        # Try to find a semantically similar product based on category
                        product_type_keywords = ['shirt', 'sweatshirt', 'hoodie', 'hat', 'cap', 'mug', 'tote', 'bag']
                        detected_type = None
                        for keyword in product_type_keywords:
                            if keyword in potential_product_name.lower():
                                detected_type = keyword
                                break
                        
                        if detected_type:
                            category_products = product_categories.get(detected_type, [])
                            if category_products:
                                # Use the first product of the same type
                                search_term = category_products[0]['title']
                                print(f"Suggesting alternative product of same type: {search_term}")
                            else:
                                search_term = "t-shirt"  # Default fallback
                        else:
                            search_term = "t-shirt"  # Default fallback
                
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
                                
                                variants_url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
                                r = requests.get(variants_url, headers=headers)
                                r.raise_for_status()
                                response_data = r.json()
                                variant_ids = [v["id"] for v in response_data["variants"]]
                                
                                product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                mockup_url = get_mockup_image(shop_id, product_id)
                                
                                success = True
                                
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
                        blueprint_id, blueprint_title = find_blueprint_id(search_term)
                        if blueprint_id:
                            providers = get_print_providers(blueprint_id)
                            if providers:
                                print_provider_id = providers[0]['id']
                                
                                shop_id = get_shop_id()
                                image_id = upload_image(image_url)
                                
                                variants_url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
                                r = requests.get(variants_url, headers=headers)
                                r.raise_for_status()
                                response_data = r.json()
                                variant_ids = [v["id"] for v in response_data["variants"]]
                                
                                product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                mockup_url = get_mockup_image(shop_id, product_id)
                                
                                success = True
                                
                                # Only add this success message if we're not handling a logo adjustment
                                # (which would have its own message already)
                                if not suggestion.get('adjust_logo', False) and "logo" not in user_message.lower():
                                    add_message_to_chat("assistant", f"I found a {blueprint_title} product for you! Here's what it looks like with your image.")
                                
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
                            
                            variants_url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
                            r = requests.get(variants_url, headers=headers)
                            r.raise_for_status()
                            response_data = r.json()
                            variant_ids = [v["id"] for v in response_data["variants"]]
                            
                            product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                            mockup_url = get_mockup_image(shop_id, product_id)
                            success = True
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
                                    
                                    variants_url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
                                    r = requests.get(variants_url, headers=headers)
                                    r.raise_for_status()
                                    response_data = r.json()
                                    variant_ids = [v["id"] for v in response_data["variants"]]
                                    
                                    product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                    mockup_url = get_mockup_image(shop_id, product_id)
                                    success = True
                                    error_message = None
                except Exception as e:
                    error_message = f"Error: {str(e)}"
    
    # Clear user message after processing and include current logo settings in the template context
    return render_template('index.html', mockup_url=mockup_url, attempted_searches=attempted_searches, 
                          search_term=search_term, image_url=image_url, chat_history=chat_history,
                          error_message=error_message, success=success, user_message="",
                          current_logo_settings=current_logo_settings)

if __name__ == '__main__':
    app.run(debug=True, port=5001)