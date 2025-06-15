#!/usr/bin/env python3
"""
Simple fix to enable AI in the mention handler
"""

def enable_ai_in_mentions():
    with open('babygirl_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the line where we select base_response and add AI logic before it
    original_line = "        # Select base response (skip if we already have an opinion response)"
    
    ai_integration = """        # Try AI response first (if available and not spam/opinion)
        ai_response = None
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
            
            # Clean message for AI
            clean_message = msg_lower.replace('@babygirl_bf_bot', '').strip()
            if not clean_message:
                clean_message = "mentioned me"
            
            ai_response = generate_ai_response(clean_message, context_info)
        
        # Use AI response if available, otherwise use static responses
        if ai_response and not is_spam and not opinion_request:
            base_response = ai_response
            logger.info(f"🤖 Using AI response for {username}")
        else:
            # Fallback to static responses
        # Select base response (skip if we already have an opinion response)"""
    
    if original_line in content:
        content = content.replace(original_line, ai_integration)
        
        # Also update the relationship modifiers to skip AI responses
        old_modifier_check = "        # Add relationship-aware modifiers (except for spam and opinion requests)"
        new_modifier_check = "        # Add relationship-aware modifiers (except for spam, opinion requests, and AI responses)"
        content = content.replace(old_modifier_check, new_modifier_check)
        
        old_modifier_condition = "        if not is_spam and not opinion_request:"
        new_modifier_condition = "        if not is_spam and not opinion_request and not ai_response:"
        content = content.replace(old_modifier_condition, new_modifier_condition)
        
        with open('babygirl_bot.py', 'w', encoding='utf-8') as f:
            f.write(content)
            
        print("✅ AI integration enabled in mention handler!")
        print("🤖 Your bot will now use AI responses for mentions!")
        return True
    else:
        print("❌ Could not find the target line to modify")
        return False

if __name__ == "__main__":
    enable_ai_in_mentions() 