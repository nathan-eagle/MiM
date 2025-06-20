import os
import logging
import json
import time
import openai
import requests
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, render_template, redirect, url_for, jsonify

# Add parent directory to path for imports
import sys
sys.path.append('..')
from chat_tracker import chat_tracker, track_chat_message
from optimized_system_prompt import get_system_prompt_for_request

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API Configuration
USE_LOCAL_KEYS = os.getenv('USE_LOCAL_KEYS', 'false').lower() == 'true'
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY_LOCAL' if USE_LOCAL_KEYS else 'OPENAI_API_KEY_PROD') or os.getenv('OPENAI_API_KEY')
PRINTIFY_API_TOKEN = os.getenv('PRINTIFY_API_TOKEN')

if not OPENAI_API_KEY or not PRINTIFY_API_TOKEN:
    raise ValueError("Missing required environment variables: OPENAI_API_KEY and/or PRINTIFY_API_TOKEN")

openai.api_key = OPENAI_API_KEY

# Printify API headers
headers = {
    "Authorization": f"Bearer {PRINTIFY_API_TOKEN}",
    "Content-Type": "application/json",
    "User-Agent": "PythonScript"
}

# Application state
chat_history = []
current_logo_settings = {"scale": 1.0, "x": 0.5, "y": 0.5}
debug_logs = []

def load_optimized_cache():
    """Load the optimized product cache"""
    try:
        with open('../product_cache.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading optimized cache: {e}")
        return {}

def add_debug_log(message):
    """Add debug message to logs"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted_message = f"[{timestamp}] {message}"
    debug_logs.append(formatted_message)
    if len(debug_logs) > 20:
        debug_logs.pop(0)
    logger.info(message)

def add_message_to_chat(role, content):
    """Add message to chat history with tracking"""
    global chat_history
    
    # Skip empty messages
    if not content.strip():
        return
    
    # Track the message addition
    track_chat_message(role, content)
    
    # Skip if identical to last message
    if chat_history and chat_history[-1]["role"] == role and chat_history[-1]["content"] == content:
        add_debug_log(f"🚫 Skipping duplicate message: {content[:50]}...")
        return
    
    # Add message
    chat_history.append({"role": role, "content": content})
    add_debug_log(f"💬 Added {role} message: {content[:50]}...")

def get_llm_decision(user_message, conversation_history):
    """
    SINGLE LLM DECISION POINT - handles all user requests intelligently
    
    This replaces all hardcoded detection logic with a single AI system
    that understands user intent and provides appropriate responses.
    """
    try:
        # Get optimized system prompt
        system_prompt = get_system_prompt_for_request(user_message, conversation_history)
        
        # Build messages for LLM
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (last 5 messages for context)
        if conversation_history:
            messages.extend(conversation_history[-5:])
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        # Get LLM response
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
            max_tokens=800
        )
        
        # Parse response
        llm_response = response.choices[0].message.content
        
        # Try to parse JSON response
        try:
            if "```json" in llm_response:
                start = llm_response.find("```json") + 7
                end = llm_response.find("```", start)
                if end != -1:
                    llm_response = llm_response[start:end].strip()
            
            decision = json.loads(llm_response)
            add_debug_log(f"🤖 LLM Decision: {decision.get('selected_product', 'N/A')}")
            return True, decision, None
            
        except json.JSONDecodeError:
            # If JSON parsing fails, treat as conversational response
            add_debug_log("🗣️ LLM provided conversational response")
            return True, {
                "selected_product": None,
                "response_message": llm_response,
                "conversation_only": True
            }, None
            
    except Exception as e:
        add_debug_log(f"❌ LLM decision error: {e}")
        return False, None, str(e)

def find_product_in_cache(product_name, cache):
    """Find a product in the optimized cache"""
    if not cache or not product_name:
        return None, None
    
    products = cache.get("products", {})
    
    # Try exact match first
    for product_id, product in products.items():
        if product["title"].lower() == product_name.lower():
            return int(product_id), product["title"]
    
    # Try partial match
    for product_id, product in products.items():
        if product_name.lower() in product["title"].lower():
            return int(product_id), product["title"]
    
    return None, None

def get_product_variants(blueprint_id, print_provider_id, requested_color=None):
    """Get product variants from Printify API"""
    try:
        url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/variants.json"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        
        variants = res.json()["variants"]
        
        if not requested_color:
            return [v["id"] for v in variants]
        
        # Filter by color
        matching_variants = []
        for variant in variants:
            variant_color = variant.get("options", {}).get("color", "").lower()
            if requested_color.lower() in variant_color:
                matching_variants.append(variant["id"])
        
        return matching_variants if matching_variants else [v["id"] for v in variants[:1]]
        
    except Exception as e:
        add_debug_log(f"❌ Error getting variants: {e}")
        return []

def get_print_providers(blueprint_id):
    """Get print providers for a blueprint"""
    try:
        url = f"https://api.printify.com/v1/catalog/blueprints/{blueprint_id}/print_providers.json"
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        add_debug_log(f"❌ Error getting providers: {e}")
        return []

def get_shop_id():
    """Get shop ID"""
    try:
        res = requests.get("https://api.printify.com/v1/shops.json", headers=headers)
        res.raise_for_status()
        return res.json()[0]["id"]
    except Exception as e:
        add_debug_log(f"❌ Error getting shop ID: {e}")
        return None

def upload_image(image_url):
    """Upload image to Printify"""
    default_url = "https://cdn-icons-png.flaticon.com/512/25/25231.png"
    
    if not image_url or not image_url.startswith('http'):
        image_url = default_url
    
    try:
        upload_url = "https://api.printify.com/v1/uploads/images.json"
        payload = {"url": image_url, "file_name": "logo.svg"}
        res = requests.post(upload_url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["id"]
    except Exception as e:
        add_debug_log(f"❌ Error uploading image: {e}")
        # Try default image
        payload = {"url": default_url, "file_name": "logo.svg"}
        res = requests.post(upload_url, headers=headers, json=payload)
        res.raise_for_status()
        return res.json()["id"]

def create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids):
    """Create product on Printify"""
    global current_logo_settings
    
    product_payload = {
        "title": "Custom Product",
        "description": "A custom product with a logo.",
        "blueprint_id": blueprint_id,
        "print_provider_id": print_provider_id,
        "variants": [{"id": variant_ids[0], "price": 1999, "is_enabled": True}],
        "print_areas": [{
            "variant_ids": [variant_ids[0]],
            "placeholders": [{
                "position": "front",
                "images": [{
                    "id": image_id,
                    "angle": 0,
                    "x": current_logo_settings["x"],
                    "y": current_logo_settings["y"],
                    "scale": current_logo_settings["scale"]
                }]
            }]
        }]
    }
    
    try:
        res = requests.post(f"https://api.printify.com/v1/shops/{shop_id}/products.json", 
                          headers=headers, json=product_payload)
        res.raise_for_status()
        return res.json()["id"]
    except Exception as e:
        add_debug_log(f"❌ Error creating product: {e}")
        raise

def get_mockup_image(shop_id, product_id):
    """Get mockup image from Printify"""
    for _ in range(10):
        try:
            res = requests.get(f"https://api.printify.com/v1/shops/{shop_id}/products/{product_id}.json", 
                             headers=headers)
            res.raise_for_status()
            
            images = res.json().get("images", [])
            if images:
                return images[0]["src"]
            
            time.sleep(3)
        except Exception as e:
            add_debug_log(f"❌ Error getting mockup: {e}")
            break
    
    raise Exception("Mockup not generated in time")

@app.route('/', methods=['GET', 'POST'])
def index():
    global chat_history, current_logo_settings
    
    mockup_url = None
    error_message = None
    success = False
    user_message = ""
    
    if request.method == 'POST':
        # Handle logo settings
        if 'logo_scale' in request.form:
            try:
                current_logo_settings["scale"] = max(0.1, min(2.0, float(request.form.get('logo_scale', 1.0))))
                current_logo_settings["x"] = max(0.0, min(1.0, float(request.form.get('logo_x', 0.5))))
                current_logo_settings["y"] = max(0.0, min(1.0, float(request.form.get('logo_y', 0.5))))
            except (ValueError, TypeError):
                pass
        
        # Handle reset
        if 'reset' in request.form:
            chat_history = []
            current_logo_settings = {"scale": 1.0, "x": 0.5, "y": 0.5}
            debug_logs.clear()
            chat_tracker.reset()
            add_debug_log("🔄 Conversation reset")
            
        # Handle user message
        elif 'message' in request.form and request.form['message'].strip():
            user_message = request.form['message'].strip()
            image_url = request.form.get('image_url', '').strip()
            
            add_message_to_chat("user", user_message)
            add_debug_log(f"💬 User: {user_message}")
            
            # SINGLE DECISION POINT - Let LLM handle everything
            success_llm, decision, error = get_llm_decision(user_message, chat_history)
            
            if success_llm and decision:
                # Add LLM response to chat
                response_msg = decision.get("response_message", "I'll help you with that!")
                add_message_to_chat("assistant", response_msg)
                
                # Check if this is conversation-only (no product creation)
                if decision.get("conversation_only"):
                    add_debug_log("🗣️ Conversation-only response")
                    # Return without creating product
                    return render_template('index.html', 
                                         mockup_url=mockup_url, 
                                         chat_history=chat_history,
                                         error_message=error_message, 
                                         success=success, 
                                         user_message="",
                                         current_logo_settings=current_logo_settings, 
                                         debug_logs=debug_logs)
                
                # Try to create product if LLM selected one
                selected_product = decision.get("selected_product")
                if selected_product:
                    try:
                        # Load cache and find product
                        cache = load_optimized_cache()
                        blueprint_id, product_title = find_product_in_cache(selected_product, cache)
                        
                        if blueprint_id:
                            add_debug_log(f"📦 Found product: {product_title} (ID: {blueprint_id})")
                            
                            # Get providers and create product
                            providers = get_print_providers(blueprint_id)
                            if providers:
                                print_provider_id = providers[0]['id']
                                shop_id = get_shop_id()
                                image_id = upload_image(image_url)
                                
                                # Get variants (with color preference if specified)
                                color_pref = decision.get("color_preference")
                                variant_ids = get_product_variants(blueprint_id, print_provider_id, color_pref)
                                
                                if variant_ids:
                                    # Create product and get mockup
                                    product_id = create_product(shop_id, blueprint_id, print_provider_id, image_id, variant_ids)
                                    mockup_url = get_mockup_image(shop_id, product_id)
                                    success = True
                                    
                                    add_debug_log(f"✅ Product created successfully")
                                else:
                                    error_message = "No variants available for this product."
                            else:
                                error_message = "No print providers available for this product."
                        else:
                            error_message = f"Product '{selected_product}' not found in catalog."
                            
                    except Exception as e:
                        error_message = f"Error creating product: {str(e)}"
                        add_debug_log(f"❌ Product creation error: {e}")
                        
                        # Add error message to chat
                        add_message_to_chat("assistant", f"Sorry, I encountered an error: {error_message}")
            else:
                error_message = error or "I had trouble understanding your request. Could you try rephrasing it?"
                add_message_to_chat("assistant", error_message)
    
    return render_template('index.html', 
                         mockup_url=mockup_url, 
                         chat_history=chat_history,
                         error_message=error_message, 
                         success=success, 
                         user_message="",
                         current_logo_settings=current_logo_settings, 
                         debug_logs=debug_logs)

@app.route('/debug')
def debug():
    """Debug endpoint to view chat tracking info"""
    chat_tracker.print_summary()
    return jsonify({
        "chat_history_count": len(chat_history),
        "debug_logs": debug_logs[-10:],  # Last 10 debug logs
        "duplicate_summary": chat_tracker.get_duplicate_summary()
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000) 