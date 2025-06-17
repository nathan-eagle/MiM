#!/usr/bin/env python3
"""
=============================================================================
LLM-DRIVEN INTELLIGENT PRODUCT SELECTION SYSTEM
=============================================================================

This module provides the LLMProductSelector class that uses GPT-4o-mini to
intelligently select products from the complete Printify catalog. This replaces
all legacy string matching heuristics with natural language understanding.

CORE INNOVATION:
Transforms user requests like "I want a cozy hoodie in blue" into structured
product selections with confidence scoring and automatic error correction.

KEY FEATURES:
• NATURAL LANGUAGE PROCESSING: Understands complex, conversational requests
• CATALOG CONTEXT: Uses complete product catalog for accurate selections  
• STRUCTURED RESPONSES: Returns JSON with product, color, and confidence data
• AUTO-CORRECTION: Fixes invalid products by selecting similar alternatives
• CONFIDENCE SCORING: Provides selection confidence for quality assurance
• ERROR HANDLING: Graceful fallback with detailed error messages

ARCHITECTURE:
• LLMProductSelector: Main class with OpenAI integration
• Structured JSON schema validation via product_selection_schema.py
• Product catalog integration for context and validation
• Confidence-based selection with fallback mechanisms

RESPONSE FORMAT:
{
    "product_selection": {
        "product_name": "Unisex Cotton Crew Tee",
        "reason": "Perfect for custom designs...",
        "confidence": 0.95
    },
    "color_request": {
        "color": "blue", 
        "importance": "preferred"
    },
    "message": "I found a great cotton t-shirt for you!"
}

HOW IT WORKS:
1. Receives user message ("I want a blue shirt")
2. Loads product catalog context (1,100+ products) 
3. Sends structured prompt to GPT-4o-mini with catalog info
4. Parses and validates JSON response
5. Auto-corrects invalid product selections
6. Returns structured response with confidence scores

ADVANTAGES OVER LEGACY SYSTEM:
• No hardcoded product dictionaries to maintain
• Handles typos, abbreviations, and complex descriptions
• Understands context and user intent
• Automatically adapts to new products in catalog
• Provides human-like product reasoning

INTEGRATION:
• Called by get_ai_suggestion() in main Flask app
• Replaces detect_simple_product_request() and related functions
• Works with ProductCatalog for product validation
• Validates responses using product_selection_schema.py

Created as part of Phase 2 transformation to eliminate string matching
and enable intelligent, conversational product selection.
=============================================================================
"""

import json
import logging
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime

import openai
from dotenv import load_dotenv

from product_catalog import create_product_catalog, Product
from product_selection_schema import (
    LLMProductResponse, 
    ProductSelection, 
    ColorRequest,
    validate_llm_response,
    create_system_prompt_with_schema
)

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

class LLMProductSelector:
    """
    Intelligent product selection using LLM with complete catalog context
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the LLM Product Selector
        
        Args:
            api_key: OpenAI API key (uses env var if not provided)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key required")
        
        # Initialize OpenAI client (old pattern for compatibility)
        openai.api_key = self.api_key
        
        # Initialize product catalog
        self.catalog = create_product_catalog()
        
        # Load catalog (will use cache if available)
        self.catalog.load_catalog()
        
        # Create catalog summary for LLM
        self.catalog_summary = self._create_catalog_summary()
        
        logger.info("LLM Product Selector initialized")
    
    def get_product_selection(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]] = None
    ) -> Tuple[bool, Optional[LLMProductResponse], Optional[str]]:
        """
        Get intelligent product selection from LLM based on user message
        
        Args:
            user_message: The user's message/request
            conversation_history: Previous conversation context
            
        Returns:
            Tuple of (success, response, error_message)
        """
        try:
            # Create system prompt with catalog context
            system_prompt = create_system_prompt_with_schema(self.catalog_summary)
            
            # Build conversation messages
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Add conversation history if provided
            if conversation_history:
                messages.extend(conversation_history[-5:])  # Last 5 messages for context
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Get LLM response
            response = openai.chat.completions.create(
                model="gpt-4o-mini",  # Use GPT-4 for better reasoning
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent responses
                max_tokens=1000
            )
            
            # Extract JSON response
            llm_response_text = response.choices[0].message.content
            
            # Validate and parse response
            is_valid, parsed_response, errors = validate_llm_response(llm_response_text)
            
            if not is_valid:
                logger.error(f"Invalid LLM response: {errors}")
                return False, None, f"Invalid LLM response: {errors}"
            
            # Verify selected product exists in catalog
            if parsed_response.primary_product:
                product = self.catalog.get_product_by_id(parsed_response.primary_product.product_id)
                if not product:
                    logger.warning(f"LLM selected non-existent product ID: {parsed_response.primary_product.product_id}")
                    # Try to find a similar product
                    similar_products = self.catalog.search_products(
                        parsed_response.primary_product.product_title, 
                        limit=1
                    )
                    if similar_products:
                        # Update response with actual product
                        actual_product = similar_products[0]
                        parsed_response.primary_product.product_id = actual_product.id
                        parsed_response.primary_product.product_title = actual_product.title
                        parsed_response.processing_notes.append(
                            f"Corrected product selection to available product: {actual_product.title}"
                        )
                    else:
                        return False, None, "Selected product not found in catalog"
            
            logger.info(f"Successfully selected product: {parsed_response.primary_product.product_title}")
            return True, parsed_response, None
            
        except Exception as e:
            logger.error(f"Error in LLM product selection: {e}")
            return False, None, str(e)
    
    def _create_catalog_summary(self) -> str:
        """
        Create a concise summary of the product catalog for LLM context
        
        Returns:
            String summary of available products
        """
        try:
            categories = self.catalog.get_categories()
            
            summary_lines = ["AVAILABLE PRODUCTS:\n"]
            
            for category, products in categories.items():
                # Limit to top 10 products per category to avoid token limits
                top_products = products[:10]
                product_list = []
                
                for product in top_products:
                    # Get basic info for each product
                    product_info = f"ID:{product.id} - {product.title}"
                    product_list.append(product_info)
                
                summary_lines.append(f"{category.upper()} ({len(products)} total):")
                summary_lines.extend([f"  {p}" for p in product_list])
                
                if len(products) > 10:
                    summary_lines.append(f"  ... and {len(products) - 10} more {category} products")
                
                summary_lines.append("")  # Empty line between categories
            
            # Add summary statistics
            total_products = sum(len(products) for products in categories.values())
            summary_lines.append(f"TOTAL: {total_products} products across {len(categories)} categories")
            
            return "\n".join(summary_lines)
            
        except Exception as e:
            logger.error(f"Error creating catalog summary: {e}")
            return "Error loading product catalog"
    
    def search_products_for_llm(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search products and return in a format suitable for LLM context
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of product dictionaries
        """
        try:
            products = self.catalog.search_products(query, limit=limit)
            
            llm_products = []
            for product in products:
                llm_products.append({
                    "id": product.id,
                    "title": product.title,
                    "category": product.category,
                    "description": product.description,
                    "tags": product.tags,
                    "available": product.available
                })
            
            return llm_products
            
        except Exception as e:
            logger.error(f"Error searching products for LLM: {e}")
            return []
    
    def get_product_variants_for_llm(self, product_id: int) -> List[Dict]:
        """
        Get product variants in a format suitable for LLM context
        
        Args:
            product_id: Product ID
            
        Returns:
            List of variant dictionaries
        """
        try:
            variants = self.catalog.get_product_variants(product_id)
            
            llm_variants = []
            for variant in variants:
                llm_variants.append({
                    "id": variant.id,
                    "title": variant.title,
                    "color": variant.color,
                    "size": variant.size,
                    "available": variant.available
                })
            
            return llm_variants
            
        except Exception as e:
            logger.error(f"Error getting variants for LLM: {e}")
            return []

# Convenience function for easy integration
def get_llm_product_selection(
    user_message: str, 
    conversation_history: List[Dict[str, str]] = None
) -> Tuple[bool, Optional[LLMProductResponse], Optional[str]]:
    """
    Convenience function to get LLM product selection
    
    Args:
        user_message: User's message
        conversation_history: Previous conversation context
        
    Returns:
        Tuple of (success, response, error_message)
    """
    try:
        selector = LLMProductSelector()
        return selector.get_product_selection(user_message, conversation_history)
    except Exception as e:
        logger.error(f"Error in convenience function: {e}")
        return False, None, str(e) 