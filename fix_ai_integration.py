#!/usr/bin/env python3

def fix_ai_integration():
    with open('babygirl_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the specific line to replace
    old_line = "        # Select base response (skip if we already have an opinion response)"
    new_section = """        # Try AI response first (for eligible mentions)
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
            
            # Clean message for AI (remove bot mention)
            clean_message = msg_lower.replace('@babygirl_bf_bot', '').strip()
            if not clean_message:
                clean_message = "mentioned me"
            
            ai_response = generate_ai_response(clean_message, context_info)
        
        # Use AI response if available, otherwise fall back to static responses
        if ai_response and not is_spam and not opinion_request:
            base_response = ai_response
            logger.info(f"🤖 Using AI response for {username}")
        else:
            # Fall back to static responses
            # Select base response (skip if we already have an opinion response)"""
    
    if old_line in content:
        content = content.replace(old_line, new_section)
        
        # Also update the modifier condition to exclude AI responses
        old_modifier = "        # Add relationship-aware modifiers (except for spam and opinion requests)\n        if not is_spam and not opinion_request:"
        new_modifier = "        # Add relationship-aware modifiers (except for spam, opinion requests, and AI responses)\n        if not is_spam and not opinion_request and not ai_response:"
        content = content.replace(old_modifier, new_modifier)
        
        with open('babygirl_bot.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ AI integration fixed! Your bot will now use AI responses.")
        return True
    else:
        print("❌ Could not find the target line to modify")
        return False

if __name__ == "__main__":
    fix_ai_integration() 