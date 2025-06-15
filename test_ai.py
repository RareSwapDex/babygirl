#!/usr/bin/env python3
import os
from groq import Groq

# Set up the API key
os.environ['GROQ_API_KEY'] = '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'
os.environ['USE_AI_RESPONSES'] = 'true'

print("🚀 Testing Groq AI integration...")

try:
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    
    completion = client.chat.completions.create(
        messages=[
            {
                "role": "system", 
                "content": "You are Babygirl, a flirty Instagram influencer bot. Keep responses short and flirty with emojis."
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
    
    response = completion.choices[0].message.content.strip()
    print(f"✅ AI Test Response: {response}")
    print("🎉 Groq AI is working perfectly!")
    print("\n🚀 Your bot is ready for AI-powered responses!")
    
except Exception as e:
    print(f"❌ AI test failed: {e}") 