#!/usr/bin/env python3

def fix_indentation():
    with open('babygirl_bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the indentation issue
    old_broken = """        else:
            # Fall back to static responses
            # Select base response (skip if we already have an opinion response)
        if not opinion_request:"""
    
    new_fixed = """        else:
            # Fall back to static responses
            # Select base response (skip if we already have an opinion response)
            if not opinion_request:"""
    
    if old_broken in content:
        content = content.replace(old_broken, new_fixed)
        
        # Also need to fix the else clause indentation
        old_else = """            if not opinion_request:
            base_response = random.choice(responses)
        else:
            base_response = response  # Use the opinion response we already generated"""
        
        new_else = """            if not opinion_request:
                base_response = random.choice(responses)
                logger.info(f"📝 Using static fallback response for {username}")
            else:
                base_response = response  # Use the opinion response we already generated"""
        
        content = content.replace(old_else, new_else)
        
        with open('babygirl_bot.py', 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("✅ Indentation fixed! AI integration should work now.")
        return True
    else:
        print("❌ Could not find the indentation issue to fix")
        return False

if __name__ == "__main__":
    fix_indentation() 