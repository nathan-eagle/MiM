# Local Testing Guide for MiM App

This guide shows you how to test the LLM product selection locally without deploying to Vercel each time.

## Setup

### 1. Environment Variables

Add these variables to your `.env` file:

```bash
# API Key Toggle - set to 'true' for local testing, 'false' for production
USE_LOCAL_KEYS=true

# Local/Development OpenAI API Key (for testing)
OPENAI_API_KEY_LOCAL=your_local_openai_api_key_here

# Production OpenAI API Key (optional - can use OPENAI_API_KEY for both)
OPENAI_API_KEY_PROD=your_production_openai_api_key_here

# Default OpenAI API Key (fallback)
OPENAI_API_KEY=your_openai_api_key_here

# Printify API Token
PRINTIFY_API_TOKEN=your_printify_token_here
```

### 2. API Key Toggle Behavior

- **`USE_LOCAL_KEYS=true`**: Uses `OPENAI_API_KEY_LOCAL` (falls back to `OPENAI_API_KEY`)
- **`USE_LOCAL_KEYS=false`**: Uses `OPENAI_API_KEY_PROD` (falls back to `OPENAI_API_KEY`)

This allows you to:
- Use different API keys for local testing vs production
- Track usage separately
- Test with different OpenAI accounts/quotas

## Running Local Tests

### Quick Test Script

Run the local testing script:

```bash
python test_llm_locally.py
```

This script will:
1. Test basic OpenAI connectivity
2. Run predefined test scenarios (including the problematic "let's try a Vintage Washed Baseball Cap")
3. Enter interactive mode where you can test any input

### Test Scenarios Included

The script tests these specific scenarios that were problematic:

1. **Simple product request**: "hat"
2. **Specific product change**: "let's try a Vintage Washed Baseball Cap" 
3. **User correction**: "That isn't a bucket hat. Let's try a Vintage Washed Baseball Cap?"
4. **Strong correction**: "NO! I want the Zip Up Hoodie" 
5. **Color change**: "make it dark green"

### What You'll See

For each test, you'll see:
- ✅ **LLM System Result**: What the new intelligent system returns
- 🤖 **Fallback System Result**: What the old system returns
- 📊 **Comparison**: Side-by-side results

### Interactive Mode

After running the predefined tests, you can test any input:

```
💬 Enter your message: let's try a Vintage Washed Baseball Cap
```

The script will show you exactly what both systems return.

## Debugging the Core Issue

The main issue you reported was:
- User says: "Let's try a Vintage Washed Baseball Cap"  
- LLM returns: "Low Profile Baseball Cap" (wrong!)
- Should return: "Vintage Washed Baseball Cap" 

The local testing script will help you see:
1. What the LLM is actually receiving as input
2. What it's returning as output
3. Whether the issue is in the LLM system or the app logic

## Running the Flask App Locally

To test the full Flask app locally with the API key toggle:

```bash
# Set local testing mode
export USE_LOCAL_KEYS=true

# Run the Flask app
python flaskApp/app.py
```

The app will print which API keys it's using:
- 🔧 Flask app using LOCAL API keys
- 🚀 Flask app using PRODUCTION API keys

## Next Steps

Once you identify where the LLM is failing with the local tests, we can:
1. Fix the prompt engineering
2. Adjust the product catalog search
3. Improve the conversation context handling
4. Debug the specific product selection logic

This approach lets you iterate quickly without Vercel deployments! 