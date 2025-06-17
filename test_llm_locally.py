#!/usr/bin/env python3
"""
Local LLM Testing Script for MiM Product Selection

This script allows you to test the LLM product selection logic locally 
without needing to deploy to Vercel each time.

Usage:
    python test_llm_locally.py
    
Environment Variables:
    - OPENAI_API_KEY_LOCAL: Your local/development OpenAI API key
    - OPENAI_API_KEY_PROD: Your production OpenAI API key (optional)
    - USE_LOCAL_KEYS: Set to 'true' to use local keys, 'false' for production
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to Python path so we can import from flaskApp
sys.path.append('.')

# API Key Toggle
USE_LOCAL_KEYS = os.getenv('USE_LOCAL_KEYS', 'true').lower() == 'true'

if USE_LOCAL_KEYS:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY_LOCAL') or os.getenv('OPENAI_API_KEY')
    print("🔧 Using LOCAL API keys")
else:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY_PROD') or os.getenv('OPENAI_API_KEY')
    print("🚀 Using PRODUCTION API keys")

if not OPENAI_API_KEY:
    print("❌ Error: No OpenAI API key found!")
    print("Set OPENAI_API_KEY_LOCAL or OPENAI_API_KEY in your .env file")
    sys.exit(1)

# Configure OpenAI
import openai
openai.api_key = OPENAI_API_KEY

# Import the LLM product selection function
try:
    from llm_product_selection import get_llm_product_selection
    print("✅ Successfully imported LLM product selection system")
except ImportError as e:
    print(f"❌ Failed to import LLM system: {e}")
    print("Falling back to basic OpenAI testing...")
    get_llm_product_selection = None

def test_basic_openai():
    """Test basic OpenAI connectivity"""
    print("\n🧪 Testing basic OpenAI connectivity...")
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'API connection successful' if you can read this."}
            ]
        )
        result = response.choices[0].message.content
        print(f"✅ OpenAI API Response: {result}")
        return True
    except Exception as e:
        print(f"❌ OpenAI API Error: {e}")
        return False

def test_llm_product_selection(user_message, conversation_history=None):
    """Test the LLM product selection system"""
    if get_llm_product_selection is None:
        print("❌ LLM product selection system not available")
        return None
        
    print(f"\n🧪 Testing LLM Product Selection...")
    print(f"📝 User Message: '{user_message}'")
    
    if conversation_history is None:
        conversation_history = []
    
    try:
        success, llm_response, error = get_llm_product_selection(user_message, conversation_history)
        
        if success and llm_response:
            print(f"✅ LLM Success!")
            print(f"🎯 Selected Product: {llm_response.primary_product.product_title}")
            print(f"🏷️  Product ID: {llm_response.primary_product.product_id}")
            print(f"📂 Category: {llm_response.primary_product.category}")
            print(f"🎯 Confidence: {llm_response.primary_product.confidence}")
            print(f"💬 Response: {llm_response.response_message}")
            return llm_response
        else:
            print(f"❌ LLM Failed: {error}")
            return None
            
    except Exception as e:
        print(f"❌ LLM Test Error: {e}")
        return None

def test_fallback_openai_selection(user_message, conversation_history=None):
    """Test the fallback OpenAI selection (similar to get_ai_suggestion_old)"""
    print(f"\n🧪 Testing Fallback OpenAI Selection...")
    print(f"📝 User Message: '{user_message}'")
    
    if conversation_history is None:
        conversation_history = []
    
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that helps users find products on Printify. Your task is to extract the product type and relevant details from the user's message. Return a JSON with 'search_term' and optionally 'image_url' if mentioned. Focus on the main product type (hat, shirt, mug, etc.) and key attributes."},
                *conversation_history,
                {"role": "user", "content": user_message}
            ]
        )
        
        ai_message = response.choices[0].message.content
        print(f"🤖 Raw AI Response: {ai_message}")
        
        # Try to extract JSON
        import json
        import re
        
        json_match = re.search(r'```json\n(.*?)\n```', ai_message, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = re.search(r'{.*}', ai_message, re.DOTALL)
            if json_str:
                json_str = json_str.group(0)
            else:
                print("❌ No JSON found in response")
                return None
                
        suggestion = json.loads(json_str)
        print(f"✅ Extracted JSON: {suggestion}")
        return suggestion
        
    except Exception as e:
        print(f"❌ Fallback Test Error: {e}")
        return None

def run_test_scenarios():
    """Run a series of test scenarios"""
    print("\n" + "="*60)
    print("🚀 RUNNING LLM PRODUCT SELECTION TESTS")
    print("="*60)
    
    # Test scenarios based on the user's reported issues
    test_cases = [
        {
            "message": "hat",
            "description": "Simple product request",
            "conversation": []
        },
        {
            "message": "let's try a Vintage Washed Baseball Cap",
            "description": "Specific product change request",
            "conversation": [
                {"role": "user", "content": "hat"},
                {"role": "assistant", "content": "I found a Low Profile Baseball Cap product for you!"}
            ]
        },
        {
            "message": "That isn't a bucket hat. That's the same hat. Let's try a Vintage Washed Baseball Cap?",
            "description": "User correction with specific product request",
            "conversation": [
                {"role": "user", "content": "hat"},
                {"role": "assistant", "content": "I found a Low Profile Baseball Cap product for you!"},
                {"role": "user", "content": "let's try a Vintage Bucket Hat"},
                {"role": "assistant", "content": "I found a Low Profile Baseball Cap product for you!"}
            ]
        },
        {
            "message": "NO! I want the Zip Up Hoodie",
            "description": "Strong user correction",
            "conversation": [
                {"role": "user", "content": "hoodie"},
                {"role": "assistant", "content": "I found a Unisex Pullover Hoodie product for you!"}
            ]
        },
        {
            "message": "make it dark green",
            "description": "Color change request",
            "conversation": [
                {"role": "user", "content": "hat"},
                {"role": "assistant", "content": "I found a Low Profile Baseball Cap product for you!"}
            ]
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*20} TEST {i}: {test_case['description']} {'='*20}")
        
        # Test with LLM system if available
        llm_result = test_llm_product_selection(test_case["message"], test_case["conversation"])
        
        # Test with fallback system
        fallback_result = test_fallback_openai_selection(test_case["message"], test_case["conversation"])
        
        print(f"\n📊 COMPARISON:")
        if llm_result:
            print(f"   LLM System: {llm_result.primary_product.product_title}")
        else:
            print(f"   LLM System: FAILED")
            
        if fallback_result:
            print(f"   Fallback System: {fallback_result.get('search_term', 'NO SEARCH TERM')}")
        else:
            print(f"   Fallback System: FAILED")

def interactive_mode():
    """Interactive testing mode"""
    print("\n" + "="*60)
    print("🎮 INTERACTIVE MODE - Type 'quit' to exit")
    print("="*60)
    
    conversation_history = []
    
    while True:
        user_input = input("\n💬 Enter your message: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
            
        if not user_input:
            continue
            
        # Add user message to conversation
        conversation_history.append({"role": "user", "content": user_input})
        
        # Test with both systems
        print(f"\n🔄 Processing: '{user_input}'")
        
        llm_result = test_llm_product_selection(user_input, conversation_history[-5:])  # Last 5 messages
        fallback_result = test_fallback_openai_selection(user_input, conversation_history[-5:])
        
        # Add assistant response to conversation (use LLM if available, otherwise fallback)
        if llm_result:
            conversation_history.append({"role": "assistant", "content": llm_result.response_message})
        elif fallback_result:
            conversation_history.append({"role": "assistant", "content": f"I found a {fallback_result.get('search_term', 'product')} for you!"})

if __name__ == "__main__":
    print("🧪 MiM Local LLM Testing Script")
    print(f"🔑 API Key: {'***' + OPENAI_API_KEY[-4:] if OPENAI_API_KEY else 'NOT SET'}")
    
    # Test basic connectivity first
    if not test_basic_openai():
        print("❌ Cannot proceed without working OpenAI API")
        sys.exit(1)
    
    # Run test scenarios
    run_test_scenarios()
    
    # Interactive mode
    try:
        interactive_mode()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    
    print("\n✅ Testing complete!") 