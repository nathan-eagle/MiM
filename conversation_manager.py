#!/usr/bin/env python3
"""
=============================================================================
LLM-DRIVEN CONVERSATION MANAGER
=============================================================================

This module provides intelligent conversation flow management using LLM
decision-making instead of hardcoded conversation patterns. It replaces
all manual conversation detection and response generation with AI-driven
natural conversation flow.

CORE INNOVATION:
Transforms static conversation patterns into dynamic, context-aware dialogue
that adapts to user intent and maintains conversation continuity.

KEY FEATURES:
• INTELLIGENT FLOW: LLM decides conversation direction and responses
• CONTEXT AWARENESS: Maintains full conversation history and product context
• LOGO ADJUSTMENTS: Natural language logo positioning and sizing
• PRODUCT CHANGES: Seamless product type and color transitions
• RECOMMENDATION ENGINE: Smart product suggestions based on context
• ERROR RECOVERY: Graceful handling of failed requests with alternatives

ARCHITECTURE:
• ConversationManager: Main class managing all conversation flow
• Context tracking with product memory and conversation history
• LLM-driven decision making for all conversation responses
• Integration with product catalog for informed recommendations

CONVERSATION TYPES HANDLED:
• Product requests ("I want a blue shirt")
• Logo adjustments ("make it smaller", "move it to the top right")
• Product changes ("change it to a mug", "show me a hoodie instead")
• Color requests ("make it red", "what colors are available?")
• Recommendations ("what would be good for a team?")
• General questions and conversation

ADVANTAGES OVER LEGACY SYSTEM:
• No hardcoded conversation patterns to maintain
• Handles complex, multi-part requests naturally
• Adapts to new conversation types automatically
• Provides contextual, relevant responses
• Maintains conversation continuity and flow

INTEGRATION:
• Used by main Flask app to handle all conversation decisions
• Replaces generate_logo_adjustment_response() and related functions
• Works with ProductCatalog and LLMProductSelector
• Maintains product memory and conversation state

Created as part of Phase 4 transformation to eliminate hardcoded
conversation patterns and enable intelligent dialogue management.
=============================================================================
"""

import os
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import openai
from product_catalog import ProductCatalog
from llm_product_selection import LLMProductSelector

@dataclass
class ConversationContext:
    """
    Structured context for conversation management.
    
    Contains all information needed for intelligent conversation flow:
    • Current product state and available options
    • User preferences and conversation history  
    • Logo settings and customization options
    • Error states and recovery information
    """
    current_product: Optional[Dict] = None
    available_colors: List[str] = None
    logo_settings: Dict = None
    conversation_history: List[Dict] = None
    last_error: Optional[str] = None
    user_preferences: Dict = None
    
    def __post_init__(self):
        if self.available_colors is None:
            self.available_colors = []
        if self.logo_settings is None:
            self.logo_settings = {"scale": 1.0, "x": 0.5, "y": 0.5}
        if self.conversation_history is None:
            self.conversation_history = []
        if self.user_preferences is None:
            self.user_preferences = {}

class ConversationManager:
    """
    Intelligent conversation flow manager using LLM decision-making.
    
    This class replaces all hardcoded conversation patterns with AI-driven
    dialogue management that understands context and user intent.
    """
    
    def __init__(self, product_catalog: ProductCatalog):
        """
        Initialize the conversation manager.
        
        Args:
            product_catalog: ProductCatalog instance for product context
        """
        self.product_catalog = product_catalog
        self.product_selector = LLMProductSelector(product_catalog)
        
        # Initialize OpenAI client
        openai.api_key = os.getenv('OPENAI_API_KEY')
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
    
    def manage_conversation(
        self, 
        user_message: str, 
        context: ConversationContext
    ) -> Tuple[str, Dict, bool]:
        """
        Manage conversation flow using intelligent LLM decision-making.
        
        This is the main entry point that replaces all hardcoded conversation
        patterns. The LLM analyzes the user message and conversation context
        to determine the appropriate response and actions.
        
        Args:
            user_message: The user's input message
            context: Current conversation context and state
            
        Returns:
            Tuple of (response_message, action_data, should_create_product)
            
        The LLM determines:
        • What type of request this is (product/logo/color/conversation)
        • How to respond naturally and helpfully
        • What actions need to be taken (product creation, logo adjustment, etc.)
        • Whether to create/update a product or just respond conversationally
        """
        try:
            # Create comprehensive context for LLM decision-making
            conversation_prompt = self._build_conversation_prompt(user_message, context)
            
            # Get LLM decision on conversation flow
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self._get_conversation_system_prompt()},
                    {"role": "user", "content": conversation_prompt}
                ],
                temperature=0.1  # Lower temperature for more consistent responses
            )
            
            # Parse LLM response
            llm_response = response.choices[0].message.content
            conversation_decision = self._parse_conversation_response(llm_response)
            
            return self._execute_conversation_decision(conversation_decision, context)
            
        except Exception as e:
            print(f"Error in conversation management: {e}")
            # Fallback to basic response
            return self._fallback_response(user_message, context)
    
    def _get_conversation_system_prompt(self) -> str:
        """
        Get the system prompt for conversation management.
        
        This prompt instructs the LLM on how to analyze conversation context
        and make intelligent decisions about response and actions.
        """
        return """You are an intelligent conversation manager for a custom merchandise creation system.

Your job is to analyze user messages and conversation context to determine:
1. What type of request this is
2. How to respond naturally and helpfully  
3. What actions need to be taken
4. Whether to create/update a product

CONVERSATION TYPES:
• PRODUCT_REQUEST: User wants a new/different product ("I want a blue shirt")
• LOGO_ADJUSTMENT: User wants to modify logo ("make it smaller", "move it left")
• COLOR_CHANGE: User wants different color ("make it red", "try blue instead")
• RECOMMENDATION: User wants suggestions ("what would be good for a team?")
• QUESTION: User asking about options ("what colors are available?")
• CONVERSATION: General chat or feedback ("that looks great!")

RESPONSE FORMAT (JSON):
{
    "conversation_type": "PRODUCT_REQUEST|LOGO_ADJUSTMENT|COLOR_CHANGE|RECOMMENDATION|QUESTION|CONVERSATION",
    "user_intent": "Brief description of what user wants",
    "response_message": "Natural, helpful response to user",
    "action_required": "PRODUCT_CREATION|LOGO_ADJUSTMENT|COLOR_CHANGE|SHOW_OPTIONS|NONE",
    "action_data": {
        "product_name": "specific product if needed",
        "color": "color if specified",
        "logo_adjustments": {"scale": 1.0, "x": 0.5, "y": 0.5},
        "alternatives": ["list of alternatives if needed"]
    },
    "should_create_product": true/false,
    "confidence": 0.95
}

Be natural, helpful, and conversational. Consider the full context when responding."""

    def _build_conversation_prompt(self, user_message: str, context: ConversationContext) -> str:
        """
        Build comprehensive conversation prompt with full context.
        
        Provides the LLM with all necessary context to make informed
        conversation decisions including product state, history, and options.
        """
        prompt_parts = [
            f"USER MESSAGE: {user_message}",
            "",
            "CURRENT CONTEXT:"
        ]
        
        # Add current product context
        if context.current_product:
            prompt_parts.extend([
                f"Current Product: {context.current_product.get('title', 'Unknown')}",
                f"Product ID: {context.current_product.get('id', 'Unknown')}"
            ])
        else:
            prompt_parts.append("Current Product: None")
        
        # Add available colors
        if context.available_colors:
            colors_text = ", ".join(context.available_colors[:10])  # Limit for prompt length
            if len(context.available_colors) > 10:
                colors_text += f" (and {len(context.available_colors) - 10} more)"
            prompt_parts.append(f"Available Colors: {colors_text}")
        
        # Add logo settings
        logo = context.logo_settings
        prompt_parts.append(
            f"Logo Settings: Scale={logo['scale']}, X={logo['x']}, Y={logo['y']}"
        )
        
        # Add recent conversation history (last 4 messages for context)
        if context.conversation_history:
            prompt_parts.append("\nRECENT CONVERSATION:")
            for msg in context.conversation_history[-4:]:
                role = msg['role'].upper()
                content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                prompt_parts.append(f"{role}: {content}")
        
        # Add error context if present
        if context.last_error:
            prompt_parts.append(f"\nLAST ERROR: {context.last_error}")
        
        prompt_parts.append("\nAnalyze this message and provide your conversation management decision:")
        
        return "\n".join(prompt_parts)
    
    def _parse_conversation_response(self, llm_response: str) -> Dict:
        """
        Parse LLM conversation management response.
        
        Extracts structured decision data from LLM response, with
        fallback parsing if JSON is malformed.
        """
        try:
            # Try to parse as JSON first
            if llm_response.strip().startswith('{'):
                return json.loads(llm_response)
            
            # If not JSON, extract a basic conversation decision
            return {
                "conversation_type": "CONVERSATION",
                "user_intent": "General conversation",
                "response_message": llm_response,
                "action_required": "NONE",
                "action_data": {},
                "should_create_product": False,
                "confidence": 0.8
            }
            
        except json.JSONDecodeError:
            # Fallback parsing for malformed JSON
            return {
                "conversation_type": "CONVERSATION", 
                "user_intent": "Unable to parse intent",
                "response_message": llm_response,
                "action_required": "NONE",
                "action_data": {},
                "should_create_product": False,
                "confidence": 0.5
            }
    
    def _execute_conversation_decision(
        self, 
        decision: Dict, 
        context: ConversationContext
    ) -> Tuple[str, Dict, bool]:
        """
        Execute the conversation decision made by the LLM.
        
        Takes the LLM's structured decision and converts it into
        appropriate actions and responses.
        """
        response_message = decision.get("response_message", "I'll help you with that!")
        action_data = decision.get("action_data", {})
        should_create_product = decision.get("should_create_product", False)
        
        # Handle logo adjustments
        if decision.get("action_required") == "LOGO_ADJUSTMENT":
            logo_adjustments = action_data.get("logo_adjustments", {})
            if logo_adjustments:
                context.logo_settings.update(logo_adjustments)
                action_data["logo_settings"] = context.logo_settings
        
        # Handle color changes
        elif decision.get("action_required") == "COLOR_CHANGE":
            requested_color = action_data.get("color")
            if requested_color:
                action_data["requested_color"] = requested_color
        
        # Handle product creation/changes
        elif decision.get("action_required") == "PRODUCT_CREATION":
            product_name = action_data.get("product_name")
            if product_name:
                action_data["search_term"] = product_name
        
        return response_message, action_data, should_create_product
    
    def _fallback_response(
        self, 
        user_message: str, 
        context: ConversationContext
    ) -> Tuple[str, Dict, bool]:
        """
        Fallback response when LLM conversation management fails.
        
        Provides basic conversation handling to ensure the system
        remains functional even if the LLM is unavailable.
        """
        msg_lower = user_message.lower()
        
        # Simple logo adjustment detection
        if any(word in msg_lower for word in ['smaller', 'bigger', 'left', 'right', 'up', 'down', 'center']):
            return "I've adjusted the logo as requested!", {"logo_adjustment": True}, True
        
        # Simple product request detection
        elif any(word in msg_lower for word in ['shirt', 'hat', 'mug', 'bag', 'hoodie']):
            return "Let me create that product for you!", {"product_request": True}, True
        
        # Default conversational response
        else:
            return "I'm here to help you create custom merchandise! What would you like to make?", {}, False

    def handle_logo_adjustment(
        self, 
        user_message: str, 
        current_settings: Dict
    ) -> Tuple[Dict, str]:
        """
        Handle logo adjustments using natural language understanding.
        
        This replaces the hardcoded adjust_logo_settings() function with
        LLM-driven logo positioning and sizing.
        
        Args:
            user_message: User's logo adjustment request
            current_settings: Current logo settings
            
        Returns:
            Tuple of (new_settings, response_message)
        """
        try:
            # Use LLM to understand logo adjustment request
            adjustment_prompt = f"""
User wants to adjust logo: "{user_message}"

Current logo settings:
- Scale: {current_settings.get('scale', 1.0)}
- X position: {current_settings.get('x', 0.5)} (0=left, 1=right)
- Y position: {current_settings.get('y', 0.5)} (0=top, 1=bottom)

Provide new settings as JSON:
{{
    "scale": 1.0,
    "x": 0.5,
    "y": 0.5,
    "explanation": "I moved the logo to the top right corner"
}}

Rules:
- Scale: 0.1 to 2.0 (smaller/bigger)
- X: 0.1 to 0.9 (left/right) 
- Y: 0.1 to 0.9 (up/down)
- For corners: top-left(0.2,0.2), top-right(0.8,0.2), bottom-left(0.2,0.8), bottom-right(0.8,0.8)
- Center: (0.5, 0.5)
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a logo positioning assistant. Parse user requests and provide precise positioning coordinates."},
                    {"role": "user", "content": adjustment_prompt}
                ],
                temperature=0.1
            )
            
            # Parse response
            llm_response = response.choices[0].message.content
            if llm_response.strip().startswith('{'):
                adjustment_data = json.loads(llm_response)
                
                new_settings = {
                    "scale": max(0.1, min(2.0, adjustment_data.get("scale", current_settings.get("scale", 1.0)))),
                    "x": max(0.1, min(0.9, adjustment_data.get("x", current_settings.get("x", 0.5)))),
                    "y": max(0.1, min(0.9, adjustment_data.get("y", current_settings.get("y", 0.5))))
                }
                
                explanation = adjustment_data.get("explanation", "I've adjusted the logo as requested!")
                return new_settings, explanation
            
        except Exception as e:
            print(f"Error in LLM logo adjustment: {e}")
        
        # Fallback to basic adjustment
        return self._basic_logo_adjustment(user_message, current_settings)
    
    def _basic_logo_adjustment(self, user_message: str, current_settings: Dict) -> Tuple[Dict, str]:
        """Basic logo adjustment fallback when LLM fails."""
        msg = user_message.lower()
        new_settings = current_settings.copy()
        
        # Size adjustments
        if 'smaller' in msg:
            new_settings["scale"] = max(0.1, new_settings["scale"] * 0.75)
        elif any(term in msg for term in ['bigger', 'larger']):
            new_settings["scale"] = min(2.0, new_settings["scale"] * 1.25)
        
        # Position adjustments
        if 'center' in msg:
            new_settings["x"] = 0.5
            new_settings["y"] = 0.5
        elif 'left' in msg:
            new_settings["x"] = max(0.1, new_settings["x"] - 0.25)
        elif 'right' in msg:
            new_settings["x"] = min(0.9, new_settings["x"] + 0.25)
        
        if 'up' in msg or 'top' in msg:
            new_settings["y"] = max(0.1, new_settings["y"] - 0.25)
        elif 'down' in msg or 'bottom' in msg:
            new_settings["y"] = min(0.9, new_settings["y"] + 0.25)
        
        return new_settings, "I've adjusted the logo as requested!"

    def get_intelligent_recommendations(
        self, 
        user_message: str, 
        context: ConversationContext
    ) -> Tuple[str, List[str]]:
        """
        Generate intelligent product recommendations using LLM and catalog context.
        
        This replaces hardcoded recommendation patterns with AI-driven
        suggestions based on user intent and available products.
        """
        try:
            # Get available product categories from catalog
            categories = self.product_catalog.get_categories()
            category_summary = {}
            
            for category, products in categories.items():
                category_summary[category] = len(products)
            
            recommendation_prompt = f"""
User message: "{user_message}"

Available product categories and counts:
{json.dumps(category_summary, indent=2)}

Current context:
- Current product: {context.current_product.get('title') if context.current_product else 'None'}
- Recent conversation: {context.conversation_history[-2:] if context.conversation_history else 'None'}

Provide 2-3 intelligent product recommendations with reasoning:
{{
    "recommendations": [
        {{
            "product": "Unisex Cotton Crew Tee",
            "reason": "Perfect for custom designs and team merchandise"
        }}
    ],
    "response": "Based on your needs, I'd recommend these great options..."
}}
"""

            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a merchandise recommendation expert. Suggest products that match user needs with clear reasoning."},
                    {"role": "user", "content": recommendation_prompt}
                ],
                temperature=0.3
            )
            
            llm_response = response.choices[0].message.content
            if llm_response.strip().startswith('{'):
                rec_data = json.loads(llm_response)
                recommendations = [rec["product"] for rec in rec_data.get("recommendations", [])]
                response_text = rec_data.get("response", "Here are some great options for you!")
                return response_text, recommendations
                
        except Exception as e:
            print(f"Error in intelligent recommendations: {e}")
        
        # Fallback recommendations
        return "Here are some popular options:", ["Unisex Cotton Crew Tee", "Snapback Hat", "Coffee Mug"] 