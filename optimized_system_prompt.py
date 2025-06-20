#!/usr/bin/env python3
"""
Optimized System Prompt for LLM Product Selection

This module provides an efficient system prompt that uses the optimized
product cache for better performance and reduced token usage.
"""

import json
import os
from typing import Dict, List, Optional

def load_optimized_cache() -> Dict:
    """Load the optimized product cache"""
    cache_file = "product_cache.json"
    if not os.path.exists(cache_file):
        return {}
    
    with open(cache_file, 'r') as f:
        return json.load(f)

def create_category_summary(cache: Dict) -> str:
    """Create a concise category summary for the LLM"""
    categories = cache.get("categories", {})
    total_products = cache.get("total_products", 0)
    
    summary_lines = [f"Available: {total_products} products across {len(categories)} categories"]
    
    for category, product_ids in sorted(categories.items()):
        # Get sample products for this category
        sample_products = []
        products = cache.get("products", {})
        
        for product_id in product_ids[:3]:  # Show top 3 products per category
            product = products.get(str(product_id))
            if product:
                sample_products.append(product["title"])
        
        category_line = f"• {category.upper()}: {len(product_ids)} products"
        if sample_products:
            category_line += f" (e.g., {', '.join(sample_products)})"
        
        summary_lines.append(category_line)
    
    return "\n".join(summary_lines)

def get_category_products(cache: Dict, category: str, limit: int = 10) -> List[Dict]:
    """Get products from a specific category"""
    categories = cache.get("categories", {})
    products = cache.get("products", {})
    
    product_ids = categories.get(category, [])[:limit]
    category_products = []
    
    for product_id in product_ids:
        product = products.get(str(product_id))
        if product:
            category_products.append({
                "id": product["id"],
                "title": product["title"],
                "colors": product.get("available_colors", [])
            })
    
    return category_products

def create_optimized_system_prompt(user_context: Optional[str] = None) -> str:
    """
    Create an optimized system prompt for LLM product selection
    
    Args:
        user_context: Optional context about the user's current conversation
        
    Returns:
        Optimized system prompt string
    """
    cache = load_optimized_cache()
    
    if not cache:
        return "System error: Product catalog not available."
    
    category_summary = create_category_summary(cache)
    
    prompt = f"""You are an intelligent product selection assistant for a print-on-demand platform.

PRODUCT CATALOG:
{category_summary}

INSTRUCTIONS:
1. Understand user intent from their natural language request
2. Select the BEST product match from available categories
3. Consider user preferences (color, style, use case)
4. Be conversational and helpful in your responses
5. Focus on understanding WHAT they want, not just keywords

RESPONSE FORMAT:
Always respond with valid JSON:
{{
    "selected_product": "exact product title from catalog",
    "category": "product category",
    "reasoning": "why this product matches their needs",
    "color_preference": "color if mentioned, null otherwise",
    "confidence": 0.85,
    "response_message": "friendly message to show the user",
    "requires_product_details": true
}}

EXAMPLES:
• "I want a blue shirt" → Find best shirt, note blue preference
• "something for the office" → Suggest professional items like mugs or shirts
• "team gifts" → Recommend customizable bulk items
• "make it red instead" → Keep same product type, change color

GUIDELINES:
- Be specific about product selection (use exact titles)
- Explain your reasoning clearly
- If colors mentioned, include in color_preference
- Set requires_product_details=true if you need the full product list
- Focus on user INTENT, not just keywords
- Be helpful and conversational"""

    # Add user context if provided
    if user_context:
        prompt += f"\n\nCURRENT CONTEXT:\n{user_context}"
    
    return prompt

def create_detailed_prompt_with_category(category: str, user_request: str) -> str:
    """
    Create a detailed prompt with specific category products
    
    Args:
        category: Product category to focus on
        user_request: User's original request
        
    Returns:
        Detailed system prompt with category-specific products
    """
    cache = load_optimized_cache()
    category_products = get_category_products(cache, category, limit=15)
    
    if not category_products:
        return create_optimized_system_prompt()
    
    # Create detailed product list
    product_list = []
    for product in category_products:
        colors_text = ", ".join(product["colors"][:5]) if product["colors"] else "Various colors"
        product_list.append(f"ID {product['id']}: {product['title']} (Colors: {colors_text})")
    
    products_text = "\n".join(product_list)
    
    prompt = f"""You are selecting the perfect {category} product for a user.

USER REQUEST: "{user_request}"

AVAILABLE {category.upper()} PRODUCTS:
{products_text}

INSTRUCTIONS:
1. Choose the BEST product from the list above that matches the user's request
2. Consider their specific needs, preferences, and use case
3. Match colors if mentioned in their request
4. Provide clear reasoning for your choice
5. Use the EXACT product title from the list above

RESPONSE FORMAT:
{{
    "selected_product": "exact title from list above",
    "category": "{category}",
    "reasoning": "detailed explanation of why this product fits",
    "color_preference": "color if mentioned, null otherwise",
    "confidence": 0.90,
    "response_message": "friendly message explaining your choice",
    "requires_product_details": true
}}

CRITICAL: Use the EXACT product title from the list above. Do not modify or shorten the title."""

    return prompt

# Convenience functions for common use cases
def get_system_prompt_for_request(user_message: str, conversation_history: List[Dict] = None) -> str:
    """Get optimized system prompt for a user request"""
    
    # Analyze user message to determine if we need category-specific details
    user_lower = user_message.lower()
    
    # Check for specific categories
    category_keywords = {
        "shirt": ["shirt", "tee", "t-shirt", "top"],
        "hat": ["hat", "cap", "beanie"],
        "mug": ["mug", "cup", "coffee", "tea"],
        "hoodie": ["hoodie", "sweatshirt", "pullover"],
        "bag": ["bag", "tote", "backpack"]
    }
    
    detected_category = None
    for category, keywords in category_keywords.items():
        if any(keyword in user_lower for keyword in keywords):
            detected_category = category
            break
    
    # If specific category detected, use detailed prompt
    if detected_category:
        return create_detailed_prompt_with_category(detected_category, user_message)
    
    # Otherwise, use general optimized prompt
    context = None
    if conversation_history:
        recent_messages = conversation_history[-3:]  # Last 3 messages
        context = "Recent conversation:\n" + "\n".join([
            f"{msg['role']}: {msg['content']}" for msg in recent_messages
        ])
    
    return create_optimized_system_prompt(context) 