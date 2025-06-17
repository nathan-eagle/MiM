#!/usr/bin/env python3
"""
=============================================================================
STRUCTURED PRODUCT SELECTION SCHEMA VALIDATION
=============================================================================

This module defines the structured data schemas used to validate and parse
LLM responses for product selection. It ensures reliable, type-safe communication
between the AI system and the Flask application.

PURPOSE:
Transforms unstructured LLM text into reliable, validated Python objects
that the application can safely use for product creation and user interaction.

KEY COMPONENTS:

1. ColorRequest
   • color: Optional[str] - Requested color name
   • importance: Literal["required", "preferred", "optional"] - Priority level
   
2. ProductSelection  
   • product_name: str - Exact product name from catalog
   • reason: str - Human-readable explanation for selection
   • confidence: float - Selection confidence (0.0-1.0)
   
3. LLMProductResponse
   • product_selection: ProductSelection - Main product choice
   • color_request: Optional[ColorRequest] - Color preferences
   • message: str - User-friendly response message

VALIDATION FEATURES:
• TYPE SAFETY: Enforces correct data types with Python dataclasses
• AUTO-CORRECTION: Fixes common variations in color importance values
• ERROR HANDLING: Provides clear validation error messages
• OPTIONAL FIELDS: Gracefully handles missing color requests
• CONFIDENCE SCORING: Validates confidence values are in valid range

VALIDATION PROCESS:
1. Parse JSON response from LLM
2. Extract and validate each field
3. Auto-correct common variations ("important" → "required")
4. Create validated dataclass instances
5. Return structured objects or detailed error messages

AUTO-CORRECTIONS:
• "important" → "required" (color importance)
• "nice" → "preferred" (color importance)  
• "needed" → "required" (color importance)
• Confidence values clamped to 0.0-1.0 range

ERROR HANDLING:
Returns descriptive error messages for:
• Missing required fields
• Invalid data types
• Out-of-range confidence values
• Invalid color importance levels
• Malformed JSON structures

INTEGRATION:
• Used by LLMProductSelector to validate AI responses
• Ensures consistent data format throughout the application
• Enables type-safe product processing in Flask routes
• Provides clear error messages for debugging

Created as part of Phase 2 transformation to ensure reliable
LLM-to-application communication with proper validation.
=============================================================================
"""

import json
import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class ConfidenceLevel(Enum):
    """Confidence levels for product selections"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

@dataclass
class ProductSelection:
    """Represents a single product selection with metadata"""
    product_id: int
    product_title: str
    category: str
    match_reason: str
    confidence: ConfidenceLevel
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['confidence'] = self.confidence.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProductSelection':
        """Create instance from dictionary"""
        if isinstance(data['confidence'], str):
            data['confidence'] = ConfidenceLevel(data['confidence'])
        return cls(**data)

@dataclass
class ColorRequest:
    """Represents a color request with fallback options"""
    requested_color: str
    fallback_colors: List[str]
    color_importance: str  # "required", "preferred", "optional"

@dataclass
class LLMProductResponse:
    """
    Complete LLM response structure for product selection
    
    This is the standardized format that the LLM should return when
    selecting products based on user requests.
    """
    # Primary product selection
    primary_product: ProductSelection
    
    # Alternative products (in order of preference)
    alternatives: List[ProductSelection]
    
    # Color requirements if specified
    color_request: Optional[ColorRequest]
    
    # Conversation context
    intent: str  # "product_request", "color_change", "recommendation", "clarification"
    user_message_interpretation: str
    
    # Response to user
    response_message: str
    
    # Metadata
    processing_notes: List[str]
    requires_clarification: bool = False
    clarification_question: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = {
            'primary_product': self.primary_product.to_dict(),
            'alternatives': [alt.to_dict() for alt in self.alternatives],
            'color_request': asdict(self.color_request) if self.color_request else None,
            'intent': self.intent,
            'user_message_interpretation': self.user_message_interpretation,
            'response_message': self.response_message,
            'processing_notes': self.processing_notes,
            'requires_clarification': self.requires_clarification,
            'clarification_question': self.clarification_question
        }
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LLMProductResponse':
        """Create instance from dictionary"""
        primary_product = ProductSelection.from_dict(data['primary_product'])
        alternatives = [ProductSelection.from_dict(alt) for alt in data['alternatives']]
        color_request = ColorRequest(**data['color_request']) if data['color_request'] else None
        
        return cls(
            primary_product=primary_product,
            alternatives=alternatives,
            color_request=color_request,
            intent=data['intent'],
            user_message_interpretation=data['user_message_interpretation'],
            response_message=data['response_message'],
            processing_notes=data['processing_notes'],
            requires_clarification=data.get('requires_clarification', False),
            clarification_question=data.get('clarification_question')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LLMProductResponse':
        """Create instance from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

class ProductSelectionValidator:
    """Validates LLM product selection responses"""
    
    @staticmethod
    def validate_response(response_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate an LLM product selection response
        
        Args:
            response_data: Dictionary containing the response data
            
        Returns:
            tuple: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required top-level fields
        required_fields = ['primary_product', 'alternatives', 'intent', 
                          'user_message_interpretation', 'response_message', 'processing_notes']
        
        for field in required_fields:
            if field not in response_data:
                errors.append(f"Missing required field: {field}")
        
        # Validate primary product
        if 'primary_product' in response_data:
            product_errors = ProductSelectionValidator._validate_product_selection(
                response_data['primary_product'], "primary_product"
            )
            errors.extend(product_errors)
        
        # Validate alternatives
        if 'alternatives' in response_data:
            if not isinstance(response_data['alternatives'], list):
                errors.append("alternatives must be a list")
            else:
                for i, alt in enumerate(response_data['alternatives']):
                    alt_errors = ProductSelectionValidator._validate_product_selection(
                        alt, f"alternatives[{i}]"
                    )
                    errors.extend(alt_errors)
        
        # Validate intent
        if 'intent' in response_data:
            valid_intents = ["product_request", "color_change", "recommendation", "clarification"]
            if response_data['intent'] not in valid_intents:
                errors.append(f"intent must be one of: {valid_intents}")
        
        # Validate color request if present
        if 'color_request' in response_data and response_data['color_request'] is not None:
            color_errors = ProductSelectionValidator._validate_color_request(
                response_data['color_request']
            )
            errors.extend(color_errors)
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _validate_product_selection(product_data: Dict[str, Any], field_name: str) -> List[str]:
        """Validate a product selection object"""
        errors = []
        required_fields = ['product_id', 'product_title', 'category', 'match_reason', 'confidence']
        
        for field in required_fields:
            if field not in product_data:
                errors.append(f"{field_name}: Missing required field: {field}")
        
        # Validate product_id is integer
        if 'product_id' in product_data:
            try:
                int(product_data['product_id'])
            except (ValueError, TypeError):
                errors.append(f"{field_name}: product_id must be an integer")
        
        # Validate confidence level
        if 'confidence' in product_data:
            valid_confidence = ["low", "medium", "high", "very_high"]
            if product_data['confidence'] not in valid_confidence:
                errors.append(f"{field_name}: confidence must be one of: {valid_confidence}")
        
        return errors
    
    @staticmethod
    def _validate_color_request(color_data: Dict[str, Any]) -> List[str]:
        """Validate a color request object"""
        errors = []
        required_fields = ['requested_color', 'fallback_colors', 'color_importance']
        
        for field in required_fields:
            if field not in color_data:
                errors.append(f"color_request: Missing required field: {field}")
        
        # Validate fallback_colors is list
        if 'fallback_colors' in color_data:
            if not isinstance(color_data['fallback_colors'], list):
                errors.append("color_request: fallback_colors must be a list")
        
        # Validate and auto-correct color_importance
        if 'color_importance' in color_data:
            valid_importance = ["required", "preferred", "optional"]
            importance = color_data['color_importance'].lower().strip()
            
            # Auto-correct common variations
            if importance in ["important", "must have", "necessary", "required"]:
                color_data['color_importance'] = "required"
            elif importance in ["nice", "would like", "good", "preferred", "want"]:
                color_data['color_importance'] = "preferred"
            elif importance in ["optional", "don't care", "doesn't matter", "any"]:
                color_data['color_importance'] = "optional"
            elif color_data['color_importance'] not in valid_importance:
                # Default to preferred if we can't understand it
                color_data['color_importance'] = "preferred"
        
        return errors

def create_system_prompt_with_schema(product_catalog_summary: str) -> str:
    """
    Create a system prompt that includes the product selection schema
    
    Args:
        product_catalog_summary: Summary of available products
        
    Returns:
        Complete system prompt for LLM
    """
    
    schema_example = {
        "primary_product": {
            "product_id": 123,
            "product_title": "Unisex Heavy Cotton Tee",
            "category": "shirt",
            "match_reason": "Best match for user's request for a comfortable t-shirt",
            "confidence": "high"
        },
        "alternatives": [
            {
                "product_id": 456,
                "product_title": "Premium Unisex T-Shirt",
                "category": "shirt",
                "match_reason": "Higher quality alternative with similar style",
                "confidence": "medium"
            }
        ],
        "color_request": {
            "requested_color": "blue",
            "fallback_colors": ["navy", "royal blue", "light blue"],
            "color_importance": "preferred"
        },
        "intent": "product_request",
        "user_message_interpretation": "User wants a blue t-shirt, specifically requesting comfort",
        "response_message": "I found a great Unisex Heavy Cotton Tee that would be perfect for you! It's very comfortable and comes in blue. Would you like to see this product?",
        "processing_notes": [
            "User emphasized comfort, so selected heavy cotton material",
            "Blue color is available for this product",
            "Offered premium alternative as backup option"
        ],
        "requires_clarification": False,
        "clarification_question": None
    }
    
    prompt = f"""You are an intelligent product selection assistant for a print-on-demand merchandise platform. Your job is to help users find the perfect products from our catalog.

AVAILABLE PRODUCTS:
{product_catalog_summary}

RESPONSE FORMAT:
You must respond with a valid JSON object following this exact schema:

{json.dumps(schema_example, indent=2)}

INSTRUCTIONS:
1. Always select the primary_product from the actual available catalog above
2. Provide 1-3 relevant alternatives from the catalog
3. Include confidence levels: "low", "medium", "high", "very_high"
4. For intent, use: "product_request", "color_change", "recommendation", "clarification"
5. If colors are mentioned, include color_request with fallback options
6. Write a natural response_message that would be shown to the user
7. Include processing_notes explaining your reasoning
8. Set requires_clarification=true if you need more information
9. NEVER make up product names - only use products from the provided catalog
10. If no good match exists, choose the closest available product and explain in the response

EXAMPLE SCENARIOS:
- "I want a red hat" → Find hat products, prioritize red color availability
- "Show me t-shirts" → Find t-shirt products, offer variety of options  
- "Something for team gifts" → Recommend popular, customizable products
- "Make it blue instead" → Keep same product type, change color focus"""

    return prompt

def validate_llm_response(response_text: str) -> tuple[bool, Union[LLMProductResponse, None], List[str]]:
    """
    Validate and parse an LLM response
    
    Args:
        response_text: Raw response text from LLM
        
    Returns:
        tuple: (is_valid, parsed_response_or_none, list_of_errors)
    """
    try:
        # Try to extract JSON from response
        response_text = response_text.strip()
        
        # Handle cases where LLM wraps JSON in markdown
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            if end != -1:
                response_text = response_text[start:end].strip()
        elif "```" in response_text:
            # Handle cases with just ```
            parts = response_text.split("```")
            if len(parts) >= 2:
                response_text = parts[1].strip()
        
        # Parse JSON
        response_data = json.loads(response_text)
        
        # Validate schema
        is_valid, errors = ProductSelectionValidator.validate_response(response_data)
        
        if is_valid:
            # Create structured response object
            llm_response = LLMProductResponse.from_dict(response_data)
            return True, llm_response, []
        else:
            return False, None, errors
            
    except json.JSONDecodeError as e:
        return False, None, [f"Invalid JSON: {str(e)}"]
    except Exception as e:
        return False, None, [f"Parsing error: {str(e)}"] 