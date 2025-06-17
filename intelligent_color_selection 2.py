#!/usr/bin/env python3
"""
=============================================================================
INTELLIGENT COLOR AND VARIANT SELECTION SYSTEM
=============================================================================

This module provides LLM-driven color matching and variant selection,
replacing hardcoded color matching heuristics with intelligent natural
language understanding of color requests.

CORE INNOVATION:
Transforms rigid color matching patterns into flexible, context-aware
color selection that understands user intent and available options.

KEY FEATURES:
• NATURAL LANGUAGE: Understands color requests in natural language
• SMART MATCHING: Intelligent matching of user colors to available variants
• CONTEXT AWARENESS: Considers product type and available color options
• ALTERNATIVE SUGGESTIONS: Provides intelligent alternatives when exact matches aren't available
• COLOR DESCRIPTIONS: Rich color context with relationships and categories
• FUZZY MATCHING: Handles typos, abbreviations, and color variations

ARCHITECTURE:
• ColorSelector: Main class for intelligent color selection
• Color context and relationship mapping
• LLM-driven color matching with confidence scoring
• Integration with product catalog for variant information

COLOR MATCHING CAPABILITIES:
• Exact matches ("blue" → "Blue")
• Fuzzy matches ("navy" → "Navy Blue") 
• Contextual matches ("dark blue" → "Navy")
• Alternative suggestions ("purple" → "Violet, Lavender")
• Color relationships ("warm colors" → "Red, Orange, Yellow")

ADVANTAGES OVER LEGACY SYSTEM:
• No hardcoded color lists to maintain
• Handles complex color descriptions naturally
• Understands color relationships and categories
• Provides intelligent alternatives and suggestions
• Adapts to new color names automatically

INTEGRATION:
• Used by Flask app to replace get_variants_for_product() logic
• Works with ProductCatalog for variant information
• Provides structured color selection responses
• Handles color availability and alternatives

Created as part of Phase 5 transformation to eliminate color matching
heuristics and enable intelligent color understanding.
=============================================================================
"""

import os
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import openai

@dataclass
class ColorMatch:
    """
    Represents a color match result with confidence and alternatives.
    """
    matched_color: Optional[str] = None
    confidence: float = 0.0
    alternatives: List[str] = None
    explanation: str = ""
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []

@dataclass
class VariantSelection:
    """
    Represents variant selection results with color context.
    """
    variant_ids: List[int] = None
    selected_color: Optional[str] = None
    available_colors: List[str] = None
    color_match: Optional[ColorMatch] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.variant_ids is None:
            self.variant_ids = []
        if self.available_colors is None:
            self.available_colors = []

class IntelligentColorSelector:
    """
    Intelligent color selection using LLM natural language understanding.
    
    This class replaces hardcoded color matching with AI-driven color
    selection that understands user intent and available options.
    """
    
    def __init__(self):
        """Initialize the intelligent color selector."""
        # Initialize OpenAI client
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
    
    def select_color_variants(
        self,
        all_variants: List[Dict],
        requested_color: Optional[str] = None,
        product_context: Optional[Dict] = None
    ) -> VariantSelection:
        """
        Intelligently select color variants using LLM understanding.
        
        This is the main method that replaces the hardcoded color matching
        logic in get_variants_for_product(). It uses LLM to understand
        color requests and match them to available variants.
        
        Args:
            all_variants: List of all available product variants
            requested_color: User's color request (optional)
            product_context: Additional product context (optional)
            
        Returns:
            VariantSelection with matched variants and color information
        """
        try:
            # Extract available colors from variants
            available_colors = self._extract_available_colors(all_variants)
            
            # If no specific color requested, return all variants
            if not requested_color:
                return VariantSelection(
                    variant_ids=[v["id"] for v in all_variants],
                    available_colors=available_colors
                )
            
            # Use LLM to match requested color to available colors
            color_match = self._match_color_with_llm(
                requested_color, 
                available_colors, 
                product_context
            )
            
            # Select variants based on color match
            if color_match.matched_color:
                selected_variants = self._filter_variants_by_color(
                    all_variants, 
                    color_match.matched_color
                )
                
                return VariantSelection(
                    variant_ids=[v["id"] for v in selected_variants],
                    selected_color=color_match.matched_color,
                    available_colors=available_colors,
                    color_match=color_match
                )
            else:
                # No match found - provide alternatives
                return VariantSelection(
                    variant_ids=[],
                    available_colors=available_colors,
                    color_match=color_match,
                    error_message=f"Color '{requested_color}' not available. {color_match.explanation}"
                )
                
        except Exception as e:
            print(f"Error in intelligent color selection: {e}")
            # Fallback to basic selection
            return self._fallback_color_selection(all_variants, requested_color)
    
    def _extract_available_colors(self, variants: List[Dict]) -> List[str]:
        """
        Extract and clean available colors from variants.
        
        This method intelligently processes variant color information
        to create a clean list of available colors.
        """
        colors = set()
        
        for variant in variants:
            color = variant.get("options", {}).get("color", "")
            if color:
                # Clean and normalize color names
                # Extract primary color (before slash or other separators)
                primary_color = color.split('/')[0].strip()
                primary_color = primary_color.split(' patch')[0].strip()
                
                if primary_color:
                    colors.add(primary_color.title())
        
        return sorted(list(colors))
    
    def _match_color_with_llm(
        self,
        requested_color: str,
        available_colors: List[str],
        product_context: Optional[Dict] = None
    ) -> ColorMatch:
        """
        Use LLM to intelligently match requested color to available colors.
        
        This replaces all hardcoded color matching logic with AI understanding
        of color relationships, synonyms, and user intent.
        """
        try:
            # Build context for LLM color matching
            color_prompt = f"""
User requested color: "{requested_color}"

Available colors for this product:
{json.dumps(available_colors, indent=2)}

Product context: {product_context.get('title', 'Unknown product') if product_context else 'Unknown product'}

Your task: Match the requested color to the best available color, or suggest alternatives.

Provide response as JSON:
{{
    "matched_color": "exact color name from available list or null",
    "confidence": 0.95,
    "alternatives": ["alternative1", "alternative2"],
    "explanation": "Why this match was chosen or why no match exists"
}}

Matching rules:
1. Prefer exact matches (case-insensitive)
2. Match color families (blue → Navy Blue, Light Blue)
3. Consider synonyms (red → Crimson, navy → Navy Blue)
4. If no good match, suggest 2-3 closest alternatives
5. Confidence: 1.0=exact, 0.8=good match, 0.5=fair match, 0.0=no match
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a color matching expert. Match user color requests to available product colors with intelligent reasoning."},
                    {"role": "user", "content": color_prompt}
                ],
                temperature=0.1
            )
            
            # Parse LLM response
            llm_response = response.choices[0].message.content
            if llm_response.strip().startswith('{'):
                color_data = json.loads(llm_response)
                
                return ColorMatch(
                    matched_color=color_data.get("matched_color"),
                    confidence=min(1.0, max(0.0, color_data.get("confidence", 0.0))),
                    alternatives=color_data.get("alternatives", []),
                    explanation=color_data.get("explanation", "")
                )
            
        except Exception as e:
            print(f"Error in LLM color matching: {e}")
        
        # Fallback to basic matching
        return self._basic_color_match(requested_color, available_colors)
    
    def _basic_color_match(self, requested_color: str, available_colors: List[str]) -> ColorMatch:
        """
        Basic color matching fallback when LLM fails.
        
        Provides simple exact and partial matching as a safety net.
        """
        requested_lower = requested_color.lower()
        
        # Try exact match (case-insensitive)
        for color in available_colors:
            if requested_lower == color.lower():
                return ColorMatch(
                    matched_color=color,
                    confidence=1.0,
                    explanation=f"Exact match found for '{requested_color}'"
                )
        
        # Try partial match
        partial_matches = []
        for color in available_colors:
            if requested_lower in color.lower() or color.lower() in requested_lower:
                partial_matches.append(color)
        
        if partial_matches:
            return ColorMatch(
                matched_color=partial_matches[0],
                confidence=0.7,
                alternatives=partial_matches[1:3],
                explanation=f"Found partial match for '{requested_color}'"
            )
        
        # No match found
        return ColorMatch(
            matched_color=None,
            confidence=0.0,
            alternatives=available_colors[:3],
            explanation=f"No match found for '{requested_color}'. Try one of these available colors."
        )
    
    def _filter_variants_by_color(self, variants: List[Dict], target_color: str) -> List[Dict]:
        """
        Filter variants to match the target color.
        
        Returns variants that match the specified color, with exact matches first.
        """
        exact_matches = []
        partial_matches = []
        
        target_lower = target_color.lower()
        
        for variant in variants:
            color = variant.get("options", {}).get("color", "")
            
            if color.lower() == target_lower:
                exact_matches.append(variant)
            elif target_lower in color.lower():
                partial_matches.append(variant)
        
        # Return exact matches first, then partial matches
        return exact_matches + partial_matches
    
    def _fallback_color_selection(
        self, 
        all_variants: List[Dict], 
        requested_color: Optional[str]
    ) -> VariantSelection:
        """
        Fallback color selection when LLM processing fails.
        
        Provides basic functionality to ensure the system remains operational.
        """
        available_colors = self._extract_available_colors(all_variants)
        
        if not requested_color:
            return VariantSelection(
                variant_ids=[v["id"] for v in all_variants],
                available_colors=available_colors
            )
        
        # Basic matching
        color_match = self._basic_color_match(requested_color, available_colors)
        
        if color_match.matched_color:
            selected_variants = self._filter_variants_by_color(
                all_variants, 
                color_match.matched_color
            )
            return VariantSelection(
                variant_ids=[v["id"] for v in selected_variants],
                selected_color=color_match.matched_color,
                available_colors=available_colors,
                color_match=color_match
            )
        else:
            return VariantSelection(
                variant_ids=[],
                available_colors=available_colors,
                color_match=color_match,
                error_message=f"Color '{requested_color}' not available."
            )

    def get_color_recommendations(
        self,
        product_context: Optional[Dict] = None,
        user_preferences: Optional[Dict] = None
    ) -> Tuple[str, List[str]]:
        """
        Generate intelligent color recommendations based on context.
        
        This provides smart color suggestions based on product type,
        user preferences, and popular color combinations.
        """
        try:
            recommendation_prompt = f"""
Product context: {product_context.get('title', 'Custom merchandise') if product_context else 'Custom merchandise'}
User preferences: {user_preferences if user_preferences else 'None specified'}

Suggest 3-5 popular colors for this type of product with reasoning.

Provide response as JSON:
{{
    "recommendations": [
        {{
            "color": "Navy Blue",
            "reason": "Professional and versatile for business use"
        }}
    ],
    "response": "For this type of product, I'd recommend these popular colors..."
}}
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a color recommendation expert for custom merchandise."},
                    {"role": "user", "content": recommendation_prompt}
                ],
                temperature=0.3
            )
            
            llm_response = response.choices[0].message.content
            if llm_response.strip().startswith('{'):
                rec_data = json.loads(llm_response)
                recommendations = [rec["color"] for rec in rec_data.get("recommendations", [])]
                response_text = rec_data.get("response", "Here are some great color options!")
                return response_text, recommendations
                
        except Exception as e:
            print(f"Error in color recommendations: {e}")
        
        # Fallback recommendations
        return "Here are some popular colors:", ["Black", "White", "Navy Blue", "Red", "Gray"] 