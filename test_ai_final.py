#!/usr/bin/env python3
import os
import sys

# Set environment variables
os.environ['GROQ_API_KEY'] = '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'
os.environ['USE_AI_RESPONSES'] = 'true'

print("🧪 Testing AI Integration...")

try:
    from babygirl_bot import generate_ai_response, groq_client, USE_AI_RESPONSES
    print(f"✅ Bot imports successful")
    print(f"🤖 Groq client: {'Connected' if groq_client else 'Not connected'}")
    print(f"🔧 AI responses enabled: {USE_AI_RESPONSES}")
    
    # Test context
    test_context = {
        'username': 'testuser',
        'chat_type': 'test',
        'is_boyfriend': False,
        'is_competition': False,
        'user_status': None,
        'user_partner': None,
        'mention_count': 0,
        'mention_method': 'text'
    }
    
    print("🎯 Testing AI response generation...")
    response = generate_ai_response("Hey babygirl, how are you doing today?", test_context)
    
    if response:
        print(f"🤖 AI Response: {response}")
        print("✅ AI integration is working perfectly!")
    else:
        print("❌ AI response failed - check the logs")
        
except Exception as e:
    print(f"❌ Error testing AI: {e}")
    sys.exit(1) 