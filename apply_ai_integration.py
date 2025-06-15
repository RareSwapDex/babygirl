#!/usr/bin/env python3
"""
Script to apply AI integration to babygirl_bot.py
This will add the AI command and modify the mention handler to use AI responses.
"""

def apply_ai_integration():
    # Read the current bot file
    with open('babygirl_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Add the AI command right before the mention handler
    ai_command = '''
@bot.message_handler(commands=['ai'])
def ai_command(message):
    """Test AI responses and toggle AI on/off"""
    try:
        parts = message.text.split()
        
        if len(parts) == 1:
            # Show AI status
            ai_status = "🤖 ON" if groq_client and USE_AI_RESPONSES else "📝 OFF (using static responses)"
            api_status = "✅ Connected" if groq_client else "❌ No API key"
            
            response = f"""🤖 **AI STATUS** 🤖

**Current Mode:** {ai_status}
**API Connection:** {api_status}
**Model:** llama3-8b-8192 (Groq)

**Commands:**
• `/ai test` - Test AI response
• `/ai on` - Enable AI responses  
• `/ai off` - Use static responses only

💡 **About AI Mode:**
When AI is ON, I generate dynamic responses based on context, relationships, and personality. When OFF, I use my original static response pools.

Groq AI is completely FREE with 6,000 requests/minute! 🚀"""
            
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

'''
    
    # Insert the AI command before the mention handler
    insert_point = "# SINGLE clean mention handler for both groups and private chats"
    content = content.replace(insert_point, ai_command + insert_point)
    
    # Now modify the response selection logic
    old_logic = '''        # Choose response category based on content, game state, and relationship status
        if is_spam:
            responses = spam_responses
            logger.info(f"🚫 SPAM DETECTED from {username}")
        elif opinion_request and target_username:
            # Generate opinion about the target user
            analysis = analyze_user_personality(target_username, str(message.chat.id))
            opinion_response = generate_user_opinion(target_username, analysis, username)
            response = opinion_response'''
    
    new_logic = '''        # Choose response category based on content, game state, and relationship status
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
            # Fallback to existing static response logic
            if is_spam:
                responses = spam_responses
                logger.info(f"🚫 SPAM DETECTED from {username}")
            elif opinion_request and target_username:
                # Generate opinion about the target user
                analysis = analyze_user_personality(target_username, str(message.chat.id))
                opinion_response = generate_user_opinion(target_username, analysis, username)
                base_response = opinion_response'''
    
    # Replace the old logic
    content = content.replace(old_logic, new_logic)
    
    # Also need to fix the response selection part
    old_selection = '''        # Select base response (skip if we already have an opinion response)
        if not opinion_request:
            base_response = random.choice(responses)
        else:
            base_response = response  # Use the opinion response we already generated
        
        # Add relationship-aware modifiers (except for spam and opinion requests)
        if not is_spam and not opinion_request:'''
    
    new_selection = '''            # Select base response for static fallback (only if not opinion request)
            if not opinion_request:
                base_response = random.choice(responses)
                logger.info(f"📝 Using static response for {username}")
        
        # Add relationship-aware modifiers (except for spam, opinion requests, and AI responses)
        if not is_spam and not opinion_request and not ai_response:'''
    
    content = content.replace(old_selection, new_selection)
    
    # Write the modified content back
    with open('babygirl_bot.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ AI integration applied successfully!")
    print("🤖 Your bot now has AI-powered responses!")
    print("📝 Static responses are used as fallback")
    print("🔧 Use /ai command to test and control AI")

if __name__ == "__main__":
    apply_ai_integration() 