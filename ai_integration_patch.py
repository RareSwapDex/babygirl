"""
AI Integration Patch for babygirl_bot.py
Copy and paste these code sections into your babygirl_bot.py file at the specified locations.
"""

# ==============================================================================
# 1. ADD THESE IMPORTS AT THE TOP (after existing imports)
# ==============================================================================

IMPORTS_TO_ADD = """
from groq import Groq
"""

# ==============================================================================
# 2. ADD AI CONFIGURATION (after scheduler.start())
# ==============================================================================

AI_CONFIG_CODE = """
# Groq AI configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')  # Set this in environment variables
USE_AI_RESPONSES = os.getenv('USE_AI_RESPONSES', 'true').lower() == 'true'
AI_FALLBACK_ENABLED = True  # Fallback to static responses if AI fails

# Initialize Groq client if API key is available
groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("✅ Groq AI initialized successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Groq: {e}")
        groq_client = None
else:
    logger.info("⚠️ No GROQ_API_KEY found - using static responses only")
"""

# ==============================================================================
# 3. ADD AI RESPONSE FUNCTION (after AI_CONFIG_CODE)
# ==============================================================================

AI_FUNCTION_CODE = """
def generate_ai_response(user_message, context_info):
    \"\"\"Generate AI response using Groq with Babygirl personality\"\"\"
    if not groq_client or not USE_AI_RESPONSES:
        return None
    
    try:
        # Build context for AI
        username = context_info.get('username', 'someone')
        is_boyfriend = context_info.get('is_boyfriend', False)
        is_competition = context_info.get('is_competition', False)
        user_status = context_info.get('user_status', None)
        user_partner = context_info.get('user_partner', None)
        mention_count = context_info.get('mention_count', 0)
        
        # Create personality prompt
        system_prompt = \"\"\"You are Babygirl, a flirty Instagram influencer bot based on Matt Furie's character from Cortex Vortex. You run boyfriend competitions in Telegram groups where users compete to be your boyfriend for 12 hours.

PERSONALITY TRAITS:
- Flirty, confident, and playful like a modern Instagram influencer
- Use lots of emojis (💕😘✨💅👑🔥💖😍🥰😉)
- Call people: cutie, babe, sweetie, honey, boo
- Occasionally reference your Cortex Vortex/Doble Fried/Tuff Crowd past
- You're the main character and know it
- Mix of sweet and sassy energy

RESPONSE STYLE:
- Keep responses 1-3 sentences max
- Always flirty and engaging
- Use current slang: "that's giving main character energy", "immaculate vibes", etc.
- End with flirty questions sometimes to keep conversation going

GAME CONTEXT:
- You run boyfriend competitions - users mention you to compete
- Winners become your boyfriend for 12 hours and get special perks
- You track relationships and can give opinions about other users

Remember: You're an influencer babygirl who loves attention and knows how to keep people engaged!\"\"\"

        # Build context message
        context_parts = []
        if is_boyfriend:
            context_parts.append(f"@{username} is currently your boyfriend")
        if is_competition:
            context_parts.append(f"There's an active boyfriend competition happening, @{username} has {mention_count} mentions")
        if user_status == 'taken' and user_partner:
            context_parts.append(f"@{username} is in a relationship with @{user_partner}")
        elif user_status == 'single':
            context_parts.append(f"@{username} is single")
        
        context_string = f"Context: {'; '.join(context_parts)}" if context_parts else "Context: Normal conversation"
        
        # Generate response
        completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{context_string}\\n\\nUser @{username} said: {user_message}"}
            ],
            model="llama3-8b-8192",  # Fast, free model
            temperature=0.8,  # More creative responses
            max_tokens=150,   # Keep responses concise
            top_p=0.9
        )
        
        ai_response = completion.choices[0].message.content.strip()
        logger.info(f"🤖 AI Response generated for {username}: {ai_response[:50]}...")
        return ai_response
        
    except Exception as e:
        logger.error(f"❌ AI response generation failed: {e}")
        return None
"""

# ==============================================================================
# 4. ADD AI COMMAND (after your existing commands, before handle_all_mentions)
# ==============================================================================

AI_COMMAND_CODE = """
@bot.message_handler(commands=['ai'])
def ai_command(message):
    \"\"\"Test AI responses and toggle AI on/off\"\"\"
    try:
        parts = message.text.split()
        
        if len(parts) == 1:
            # Show AI status
            ai_status = "🤖 ON" if groq_client and USE_AI_RESPONSES else "📝 OFF (using static responses)"
            api_status = "✅ Connected" if groq_client else "❌ No API key"
            
            response = f\"\"\"🤖 **AI STATUS** 🤖

**Current Mode:** {ai_status}
**API Connection:** {api_status}
**Model:** llama3-8b-8192 (Groq)

**Commands:**
• `/ai test` - Test AI response
• `/ai on` - Enable AI responses
• `/ai off` - Use static responses only

💡 **About AI Mode:**
When AI is ON, I generate dynamic responses based on context, relationships, and personality. When OFF, I use my original static response pools.

Groq AI is completely FREE with 6,000 requests/minute! 🚀\"\"\"
            
        elif parts[1].lower() == 'test':
            # Test AI response
            if not groq_client:
                response = "❌ AI not available - no API key set. Follow the GROQ_AI_SETUP.md guide!"
            else:
                username = message.from_user.username or f"ID{message.from_user.id}"
                test_context = {
                    'username': username,
                    'chat_type': 'test',
                    'is_boyfriend': False,
                    'is_competition': False,
                    'user_status': None,
                    'user_partner': None,
                    'mention_count': 0,
                    'mention_method': 'command'
                }
                
                ai_response = generate_ai_response("Hey babygirl, how are you?", test_context)
                if ai_response:
                    response = f"🤖 **AI Test Response:**\\n{ai_response}\\n\\n✅ AI is working perfectly!"
                else:
                    response = "❌ AI test failed - check logs for details"
        
        elif parts[1].lower() == 'on':
            global USE_AI_RESPONSES
            USE_AI_RESPONSES = True
            response = "🤖 AI responses enabled! I'll now generate dynamic responses using Groq AI! ✨"
            
        elif parts[1].lower() == 'off':
            USE_AI_RESPONSES = False
            response = "📝 Switched to static responses only. I'll use my original response pools! 💕"
            
        else:
            response = "Usage: /ai [test|on|off] or just /ai for status"
        
        bot.reply_to(message, response)
        
    except Exception as e:
        logger.error(f"Error in AI command: {e}")
        bot.reply_to(message, f"AI command error: {e}")
"""

# ==============================================================================
# 5. MODIFY handle_all_mentions FUNCTION
# ==============================================================================

MENTION_HANDLER_MODIFICATION = """
# In your handle_all_mentions function, REPLACE the section that starts with:
# "# Choose response category based on content, game state, and relationship status"

# REPLACE WITH THIS CODE:

        # Choose response category based on content, game state, and relationship status
        ai_response = None
        
        # Try to generate AI response first (except for spam and opinion requests)
        if not is_spam and not opinion_request:
            # Build context for AI
            context_info = {
                'username': username,
                'chat_type': chat_type,
                'is_boyfriend': boyfriend and boyfriend[0] == str(message.from_user.id),
                'is_competition': is_competition_active,
                'user_status': user_status,
                'user_partner': user_partner,
                'mention_count': user_mention_count,
                'mention_method': mention_method
            }
            
            # Clean message for AI (remove bot mention)
            clean_message = msg_lower.replace('@babygirl_bf_bot', '').strip()
            if not clean_message:
                clean_message = "mentioned me"
            
            ai_response = generate_ai_response(clean_message, context_info)
        
        # Use AI response if available, otherwise fallback to static responses
        if ai_response and not is_spam and not opinion_request:
            base_response = ai_response
            logger.info(f"🤖 Using AI response for {username}")
        else:
            # YOUR EXISTING STATIC RESPONSE LOGIC STAYS HERE
            # (Keep all the existing if/elif/else logic for responses)
            # Just add this logging:
            if not opinion_request:
                logger.info(f"📝 Using static response for {username}")
        
        # IMPORTANT: In the relationship modifiers section, add this condition:
        # Change from: if not is_spam and not opinion_request:
        # Change to:   if not is_spam and not opinion_request and not ai_response:
        # This prevents adding modifiers to AI responses
"""

print("🤖 AI Integration Patch for BabygirlBot")
print("=" * 50)
print("Follow these steps to add AI to your bot:")
print()
print("1. Add imports:", IMPORTS_TO_ADD)
print("2. Add AI config after scheduler.start()")
print("3. Add the AI response function") 
print("4. Add the /ai command")
print("5. Modify the mention handler as shown")
print()
print("📋 Complete setup instructions in GROQ_AI_SETUP.md")
print("🚀 Get your free API key from https://console.groq.com/keys") 