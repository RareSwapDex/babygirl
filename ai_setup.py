#!/usr/bin/env python3
"""
AI Setup Script for BabygirlBot
This script helps you set up Groq AI integration and test it before deployment.
"""

import os
from groq import Groq

def get_groq_api_key():
    """Get or set up Groq API key"""
    print("🚀 Setting up Groq AI for BabygirlBot!")
    print("\n📋 Steps to get your FREE Groq API key:")
    print("1. Go to https://console.groq.com/keys")
    print("2. Sign up with your email (completely free!)")
    print("3. Create a new API key")
    print("4. Copy the key that starts with 'gsk_...'")
    
    api_key = input("\n🔑 Paste your Groq API key here: ").strip()
    
    if not api_key.startswith('gsk_'):
        print("❌ Invalid API key format. Groq keys start with 'gsk_'")
        return None
    
    return api_key

def test_groq_connection(api_key):
    """Test the Groq API connection"""
    try:
        client = Groq(api_key=api_key)
        
        # Test with a sample Babygirl response
        print("\n🧪 Testing AI connection...")
        completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": """You are Babygirl, a flirty Instagram influencer bot. Keep responses short and flirty with emojis."""
                },
                {
                    "role": "user", 
                    "content": "Hey babygirl! How are you doing?"
                }
            ],
            model="llama3-8b-8192",
            temperature=0.8,
            max_tokens=100
        )
        
        test_response = completion.choices[0].message.content.strip()
        print(f"✅ AI Test Response: {test_response}")
        print("🎉 Groq AI is working perfectly!")
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

def create_env_file(api_key):
    """Create .env file with API key"""
    env_content = f"""# BabygirlBot Environment Variables
BOT_TOKEN=7618107152:AAEMPk7q7xNUhZpiDMMiVRSrTV0hkJSyV8I
GROQ_API_KEY={api_key}
USE_AI_RESPONSES=true
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file with your API key!")

def update_heroku_config(api_key):
    """Show commands to update Heroku config"""
    print("\n🚀 To deploy AI features to Heroku, run these commands:")
    print(f"heroku config:set GROQ_API_KEY={api_key}")
    print("heroku config:set USE_AI_RESPONSES=true")
    print("\nThen restart your bot:")
    print("heroku restart")

def main():
    print("=" * 60)
    print("🤖 BABYGIRL AI SETUP - GROQ INTEGRATION")
    print("=" * 60)
    
    # Check if we already have an API key
    existing_key = os.getenv('GROQ_API_KEY')
    if existing_key:
        print(f"✅ Found existing API key: {existing_key[:10]}...")
        if test_groq_connection(existing_key):
            print("🎉 Your AI is already set up and working!")
            return
    
    # Get new API key
    api_key = get_groq_api_key()
    if not api_key:
        print("❌ Setup cancelled.")
        return
    
    # Test the connection
    if not test_groq_connection(api_key):
        print("❌ API key doesn't work. Please check and try again.")
        return
    
    # Create .env file
    create_env_file(api_key)
    
    # Show Heroku deployment info
    update_heroku_config(api_key)
    
    print("\n" + "=" * 60)
    print("🎉 AI SETUP COMPLETE!")
    print("=" * 60)
    print("Your bot now has:")
    print("✅ Groq AI integration (FREE)")
    print("✅ Dynamic personality responses")
    print("✅ Context-aware conversations")
    print("✅ Fallback to static responses if AI fails")
    print("\n🚀 Your bot is ready to be more flirty and engaging!")
    print("\n💡 The bot will automatically use AI when:")
    print("   • Users mention @babygirl_bf_bot")
    print("   • Someone replies to the bot")
    print("   • During normal conversations")
    print("\n📊 Static responses are still used for:")
    print("   • Spam detection")
    print("   • Opinion requests about other users")
    print("   • Special game mechanics")

if __name__ == "__main__":
    main() 