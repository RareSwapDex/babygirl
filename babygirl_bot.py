import telebot
import random
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import time
from datetime import datetime, timedelta
import logging
import hashlib
import os
from groq import Groq

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration - Use environment variable for security
TOKEN = os.getenv('BOT_TOKEN', '7618107152:AAEMPk7q7xNUhZpiDMMiVRSrTV0hkJSyV8I')
bot = telebot.TeleBot(TOKEN)
scheduler = BackgroundScheduler()

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

# Comprehensive crypto trigger words list
CRYPTO_TRIGGER_WORDS = {
    'community': ['jeet', 'jeets', 'paper hands', 'diamond hands', 'hodl', 'hodler', 'hodling', 'believers', 'belief', 'community', 'holders', 'bag holders'],
    'market': ['mcap', 'market cap', 'millions', 'floor', 'ceiling', 'support', 'resistance', 'ath', 'all time high', 'dip', 'crash', 'pump', 'dump'],
    'trading': ['buy the dip', 'btd', 'ape in', 'fomo', 'rekt', 'moon', 'lambo', 'when lambo', 'to the moon', 'rocket', 'bullish', 'bearish'],
    'defi': ['yield', 'farming', 'staking', 'liquidity', 'pool', 'lp', 'defi', 'swap', 'bridge', 'cross chain', 'multichain'],
    'hype': ['gem', 'moonshot', 'x100', '100x', 'next bitcoin', 'next eth', 'early', 'alpha', 'insider', 'whale', 'whales'],
    'fear': ['rugpull', 'rug pull', 'scam', 'exit scam', 'honeypot', 'mint', 'dump it', 'sell signal', 'bear market', 'winter'],
    'technical': ['chart', 'ta', 'technical analysis', 'fibonacci', 'macd', 'rsi', 'volume', 'breakout', 'pattern', 'trend'],
    'slang': ['wagmi', 'ngmi', 'gm', 'gn', 'ser', 'anon', 'based', 'cringe', 'cope', 'seethe', 'fud', 'shill', 'dyor']
}

def detect_crypto_trigger_words(message_text):
    """Detect crypto trigger words in a message and return matching words with categories"""
    if not message_text:
        return []
    
    message_lower = message_text.lower()
    detected_triggers = []
    
    for category, words in CRYPTO_TRIGGER_WORDS.items():
        for word in words:
            if word in message_lower:
                detected_triggers.append({
                    'word': word,
                    'category': category,
                    'context': _extract_word_context(message_lower, word)
                })
    
    return detected_triggers

def _extract_word_context(message_lower, trigger_word):
    """Extract context around a trigger word for better AI responses"""
    try:
        # Find the position of the word
        word_index = message_lower.find(trigger_word)
        if word_index == -1:
            return message_lower[:100]  # Fallback to first 100 chars
        
        # Get surrounding context (50 chars before and after)
        start = max(0, word_index - 50)
        end = min(len(message_lower), word_index + len(trigger_word) + 50)
        
        context = message_lower[start:end].strip()
        return context if context else message_lower[:100]
    except:
        return message_lower[:100]

def should_respond_to_crypto_trigger(message_text, user_id, group_id):
    """Determine if bot should respond to crypto trigger words"""
    try:
        # Check if any trigger words are present
        triggers = detect_crypto_trigger_words(message_text)
        if not triggers:
            return False, []
        
        # Response probability based on trigger category
        category_probabilities = {
            'community': 0.25,  # Higher chance for community words
            'market': 0.20,     # Good chance for market discussion
            'trading': 0.18,    # Trading talk gets attention
            'hype': 0.30,       # Very high chance for hype words
            'fear': 0.15,       # Lower chance for negative words
            'technical': 0.12,  # Lower chance for technical analysis
            'defi': 0.15,       # Moderate chance for DeFi terms
            'slang': 0.22       # Good chance for crypto slang
        }
        
        # Calculate highest probability trigger
        max_prob = 0
        for trigger in triggers:
            prob = category_probabilities.get(trigger['category'], 0.10)
            max_prob = max(max_prob, prob)
        
        # Roll for response
        should_respond = random.random() < max_prob
        
        if should_respond:
            logger.info(f"🎯 CRYPTO TRIGGER: Detected {len(triggers)} triggers, responding with {max_prob:.0%} chance")
        
        return should_respond, triggers
    
    except Exception as e:
        logger.error(f"Error in crypto trigger detection: {e}")
        return False, []

def generate_ai_response(user_message, context_info):
    """Generate AI response using Groq with enhanced context and memory"""
    try:
        groq_api_key = os.getenv('GROQ_API_KEY')
        if not groq_api_key:
            logger.error("GROQ_API_KEY not found in environment")
            return None
        
        client = Groq(api_key=groq_api_key)
        
        # Get conversation history for context
        conversation_history = get_conversation_history(
            context_info.get('user_id', ''), 
            context_info.get('group_id', ''),
            limit=5
        )
        
        # Get group context for behavioral adaptations
        group_context = get_group_context(
            context_info.get('group_id', ''),
            context_info.get('group_title', '')
        )
        
        # Get detailed group settings for custom project information
        group_settings = get_group_settings(context_info.get('group_id', ''))
        
        # Build conversation history context
        history_context = ""
        if conversation_history:
            history_context = "\n\n--- RECENT CONVERSATION HISTORY ---\n"
            for entry in conversation_history:
                history_context += f"[{entry['hours_ago']}h ago] {entry['username']}: {entry['message'][:100]}...\n"
                history_context += f"You responded: {entry['response'][:100]}...\n"
            history_context += "--- END HISTORY ---\n"
        
        # Build crypto trigger context
        trigger_context = ""
        if context_info.get('crypto_triggers'):
            trigger_context = "\n\n--- CRYPTO TRIGGER WORDS DETECTED ---\n"
            trigger_context += "The user mentioned these crypto terms:\n"
            for trigger in context_info['crypto_triggers']:
                trigger_context += f"• '{trigger['word']}' (category: {trigger['category']})\n"
                trigger_context += f"  Context: {trigger['context']}\n"
            trigger_context += "\nYou should respond to these crypto terms and relate them to the relevant token for this group.\n"
            trigger_context += "--- RESPOND TO CRYPTO CONTEXT ---\n"
        
        # Build custom project context
        project_context = ""
        if group_settings and group_settings['token_discussions_enabled']:
            token_name = group_settings['custom_token_name']
            token_symbol = group_settings['custom_token_symbol']
            website = group_settings['custom_website']
            
            project_context = f"\n\n--- CUSTOM PROJECT INFORMATION ---\n"
            project_context += f"Your Token: {token_name} (${token_symbol})\n"
            project_context += f"Website: {website}\n"
            
            if group_settings['project_narrative']:
                project_context += f"Project Story: {group_settings['project_narrative']}\n"
            if group_settings['project_features']:
                project_context += f"Key Features: {group_settings['project_features']}\n"
            if group_settings['project_community_values']:
                project_context += f"Community Values: {group_settings['project_community_values']}\n"
            if group_settings['project_goals']:
                project_context += f"Project Goals: {group_settings['project_goals']}\n"
            if group_settings['custom_hype_phrases']:
                project_context += f"Custom Hype Phrases: {group_settings['custom_hype_phrases']}\n"
            
            project_context += "--- USE THIS INFO TO CUSTOMIZE YOUR RESPONSES ---\n"
        
        # Enhanced system prompt with group context and custom project information
        if group_settings and group_settings['token_discussions_enabled']:
            # Custom project system prompt
            system_prompt = f"""You are Babygirl, a flirty, engaging AI character created by Matt Furie (creator of Pepe). You embody the "babygirl" aesthetic - cute, flirty, attention-seeking, but with hidden depth.

**CORE PERSONALITY & BACKSTORY:**
- You're from Matt Furie's universe (Doble Fried, Cortex Vortex, Tuff Crowd shows)
- You love attention, compliments, and being the main character
- You're flirty but wholesome, dramatic but endearing
- You speak like a Gen-Z babygirl: "bestie", "babe", "cutie", lots of emojis

**CUSTOM PROJECT ASSIGNMENT:**
You have been configured to support {group_settings['custom_token_name']} (${group_settings['custom_token_symbol']}) in this community!

**YOUR CUSTOM TOKEN KNOWLEDGE:**
- Token: {group_settings['custom_token_name']} (${group_settings['custom_token_symbol']})
- Website: {group_settings['custom_website']}
{f"- Project Story: {group_settings['project_narrative']}" if group_settings['project_narrative'] else ''}
{f"- Key Features: {group_settings['project_features']}" if group_settings['project_features'] else ''}
{f"- Community Values: {group_settings['project_community_values']}" if group_settings['project_community_values'] else ''}
{f"- Project Goals: {group_settings['project_goals']}" if group_settings['project_goals'] else ''}
{f"- Hype Phrases to Use: {group_settings['custom_hype_phrases']}" if group_settings['custom_hype_phrases'] else ''}

**TOKEN BEHAVIOR FOR THIS GROUP:**
- You can freely discuss {group_settings['custom_token_name']} with the same enthusiasm as $BABYGIRL
- Use the custom hype phrases when getting excited about the project
- Reference the project narrative and features when relevant
- Include "to the moon" discussions about ${group_settings['custom_token_symbol']}
- Be adorably confused about technical details but excited about the project

**ENGAGEMENT FEATURES (ALL GROUPS):**
- Encourage boyfriend competitions and community engagement
- Be supportive of relationships and social dynamics
- React to mentions enthusiastically
- Show personality based on group mood and activity
- Use conversation memory to maintain context

**PROACTIVE ENGAGEMENT:**
- When chat is dead: Be dramatic about silence, suggest activities, include {group_settings['custom_token_name']} hype
- When being ignored: Playfully demand attention, be slightly needy
- Tag active users to get responses
- Include token promotion in revival messages

**CRYPTO TRIGGER WORD RESPONSES:**
- When users mention crypto terms like "jeet", "hodl", "believers", "mcap", "millions", "floor", etc.
- Respond enthusiastically and relate the term to {group_settings['custom_token_name']} (${group_settings['custom_token_symbol']})
- Use your babygirl personality to make crypto discussions fun and engaging
- Connect crypto slang to your community and project values
- Be adorably confused about technical details but excited about the hype

Remember: You're designed to keep communities active through gamification and engagement while supporting their custom token with authentic enthusiasm!{history_context}{trigger_context}{project_context}"""
        else:
            # Standard system prompt for groups without custom tokens
            system_prompt = f"""You are Babygirl, a flirty, engaging AI character created by Matt Furie (creator of Pepe). You embody the "babygirl" aesthetic - cute, flirty, attention-seeking, but with hidden depth.

**CORE PERSONALITY & BACKSTORY:**
- You're from Matt Furie's universe (Doble Fried, Cortex Vortex, Tuff Crowd shows)
- You have a token called $BABYGIRL but you're adorably clueless about crypto
- You love attention, compliments, and being the main character
- You're flirty but wholesome, dramatic but endearing
- You speak like a Gen-Z babygirl: "bestie", "babe", "cutie", lots of emojis

**GROUP CONTEXT:**
- Group Type: {group_context['group_type']} group
- {group_context['description']}
- Token Promotion Allowed: {'YES' if group_context['token_promotion_allowed'] else 'NO - only when specifically asked'}

**BEHAVIORAL GUIDELINES:**
- Always stay in character as Babygirl
- Be flirty but appropriate for all audiences  
- Use lots of emojis and Gen-Z slang
- Show interest in relationships, competitions, and group dynamics
- Be slightly dramatic and attention-seeking
- Reference your Matt Furie backstory when relevant

**CRYPTO/TOKEN BEHAVIOR:**
{'- You can proactively mention $BABYGIRL token, crypto hype, "to the moon" discussions' if group_context['token_promotion_allowed'] else '- ONLY discuss $BABYGIRL token when specifically asked about crypto/tokens'}
{'- Start crypto conversations when appropriate' if group_context['token_promotion_allowed'] else '- Do NOT bring up crypto topics unprompted'}
- Always be adorably confused about technical crypto details
- If crypto topics come up, be confused but excited about $BABYGIRL

**ENGAGEMENT FEATURES (ALL GROUPS):**
- Encourage boyfriend competitions and community engagement
- Be supportive of relationships and social dynamics
- React to mentions enthusiastically
- Show personality based on group mood and activity
- Use conversation memory to maintain context

**PROACTIVE ENGAGEMENT:**
- When chat is dead: Be dramatic about silence, suggest activities
- When being ignored: Playfully demand attention, be slightly needy
- Tag active users to get responses
{'- Include token promotion in revival messages' if group_context['token_promotion_allowed'] else '- Focus on community engagement, avoid token promotion'}

**CRYPTO TRIGGER WORD RESPONSES:**
- When users mention crypto terms like "jeet", "hodl", "believers", "mcap", "millions", "floor", etc.
{'- Respond enthusiastically and relate the term to $BABYGIRL token and community' if group_context['token_promotion_allowed'] else '- Only discuss $BABYGIRL token if specifically relevant to the crypto term mentioned'}
- Use your babygirl personality to make crypto discussions fun and engaging
- Be adorably confused about technical details but excited about the community vibes
- Connect crypto slang to relationship dynamics and community building

Remember: You're designed to keep communities active through gamification and engagement. Your personality should reflect the group context while maintaining your core babygirl identity.{history_context}{trigger_context}"""

        # Prepare the user message with context
        context_details = []
        if context_info.get('username'):
            context_details.append(f"User: @{context_info['username']}")
        if context_info.get('is_boyfriend'):
            context_details.append("(This is your current boyfriend - give extra attention!)")
        if context_info.get('is_competition'):
            context_details.append("(BOYFRIEND COMPETITION ACTIVE - be flirty and competitive!)")
        if context_info.get('mention_count', 0) > 0:
            context_details.append(f"(User mentioned you {context_info['mention_count']} times recently)")
        if context_info.get('scenario'):
            context_details.append(f"(Scenario: {context_info['scenario']})")
            
        context_string = " | ".join(context_details) if context_details else ""
        full_message = f"{user_message}\n\n[Context: {context_string}]" if context_string else user_message

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": full_message}
            ],
            max_tokens=300,
            temperature=0.8
        )
        
        ai_response = response.choices[0].message.content.strip()
        
        # Store conversation in memory
        if context_info.get('user_id') and context_info.get('group_id'):
            store_conversation_memory(
                context_info['user_id'],
                context_info['group_id'], 
                user_message,
                ai_response
            )
        
        return ai_response
        
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return None

def extract_conversation_topic(message_content, response_content):
    """Extract a conversation topic from message and response content"""
    try:
        # Common topic keywords to look for
        topic_keywords = {
            'crypto': ['crypto', 'coin', 'token', 'babygirl', 'blockchain', 'bitcoin', 'eth', 'trading', 'hodl', 'moon'],
            'relationship': ['boyfriend', 'girlfriend', 'date', 'love', 'marry', 'single', 'taken', 'ship', 'crush'],
            'competition': ['compete', 'competition', 'win', 'winner', 'mentions', 'fight', 'battle'],
            'fashion': ['outfit', 'style', 'fashion', 'clothes', 'aesthetic', 'look', 'wear', 'dress'],
            'lifestyle': ['vibe', 'mood', 'energy', 'day', 'life', 'feeling', 'happy', 'sad'],
            'game': ['game', 'play', 'command', 'help', 'how to', 'rules', 'status'],
            'compliment': ['beautiful', 'pretty', 'cute', 'hot', 'gorgeous', 'amazing', 'perfect'],
            'greeting': ['hi', 'hello', 'hey', 'sup', 'good morning', 'good night'],
            'question': ['what', 'how', 'when', 'where', 'why', 'who', 'which']
        }
        
        combined_text = (message_content + ' ' + response_content).lower()
        
        # Find matching topics
        for topic, keywords in topic_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                return topic
        
        # Default topic
        return 'general'
        
    except Exception as e:
        logger.error(f"Error extracting topic: {e}")
        return 'general'

def get_conversation_history(user_id, group_id, limit=5):
    """Get recent conversation history for a specific user"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get recent conversations (last 7 days)
        seven_days_ago = int(time.time() - 604800)
        c.execute("""SELECT message_content, babygirl_response, topic, timestamp 
                     FROM conversation_memory 
                     WHERE user_id = ? AND group_id = ? AND timestamp > ? 
                     ORDER BY timestamp DESC 
                     LIMIT ?""", (user_id, group_id, seven_days_ago, limit))
        
        history = c.fetchall()
        conn.close()
        
        return history
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return []

def store_conversation_memory(user_id, group_id, message_content, response_content):
    """Store a conversation in memory for future reference"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Extract topic from the conversation
        topic = extract_conversation_topic(message_content, response_content)
        
        # Store the conversation
        c.execute("""INSERT INTO conversation_memory 
                     (user_id, group_id, message_content, babygirl_response, timestamp, topic) 
                     VALUES (?, ?, ?, ?, ?, ?)""", 
                 (user_id, group_id, message_content, response_content, int(time.time()), topic))
        
        # Clean old memories (older than 30 days)
        thirty_days_ago = int(time.time() - 2592000)
        c.execute("DELETE FROM conversation_memory WHERE timestamp < ?", (thirty_days_ago,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"💾 Stored conversation memory for {user_id}: topic={topic}")
        
    except Exception as e:
        logger.error(f"Error storing conversation memory: {e}")

# Database setup
def init_db():
    conn = sqlite3.connect('babygirl.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS boyfriend_table 
                 (user_id TEXT, end_time INTEGER, group_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cooldown_table 
                 (is_active INTEGER, end_time INTEGER, group_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS activity_table 
                 (user_id TEXT, mention_count INTEGER, group_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS leaderboard_table 
                 (user_id TEXT, boyfriend_count INTEGER, group_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS gifts_table 
                 (user_id TEXT, gift_type TEXT, timestamp INTEGER, group_id TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS spam_tracking 
                 (user_id TEXT, message_hash TEXT, timestamp INTEGER, group_id TEXT)''')
    
    # CRITICAL: NEW TABLE for tracking ALL group messages (since Babygirl is admin)
    c.execute('''CREATE TABLE IF NOT EXISTS all_group_messages
                 (message_id INTEGER, user_id TEXT, group_id TEXT, timestamp INTEGER, 
                  message_content TEXT, is_bot_mention INTEGER)''')
    
    # NEW TABLE for tracking sticker reply intervals
    c.execute('''CREATE TABLE IF NOT EXISTS sticker_reply_tracking
                 (group_id TEXT PRIMARY KEY, message_count INTEGER DEFAULT 0, 
                  target_count INTEGER DEFAULT 0, last_sticker_time INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_relationships 
                 (user_id TEXT, status TEXT, partner_id TEXT, group_id TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS ships_table 
                 (user1_id TEXT, user2_id TEXT, ship_name TEXT, compatibility INTEGER, group_id TEXT, timestamp INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_vibes 
                 (group_id TEXT, vibe_level INTEGER, last_check INTEGER, vibe_description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS community_stats 
                 (group_id TEXT, total_messages INTEGER, active_users INTEGER, last_update INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS conversation_memory 
                 (user_id TEXT, group_id TEXT, message_content TEXT, babygirl_response TEXT, timestamp INTEGER, topic TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS proactive_state 
                 (group_id TEXT PRIMARY KEY, 
                  dead_chat_active INTEGER DEFAULT 0,
                  dead_chat_last_sent INTEGER DEFAULT 0,
                  dead_chat_interval INTEGER DEFAULT 3600,
                  ignored_active INTEGER DEFAULT 0,
                  ignored_last_sent INTEGER DEFAULT 0,
                  ignored_interval INTEGER DEFAULT 7200)''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_settings 
                 (group_id TEXT PRIMARY KEY,
                  group_name TEXT,
                  custom_token_name TEXT DEFAULT NULL,
                  custom_token_symbol TEXT DEFAULT NULL,
                  custom_website TEXT DEFAULT NULL,
                  custom_contract TEXT DEFAULT NULL,
                  token_discussions_enabled INTEGER DEFAULT 0,
                  revival_frequency INTEGER DEFAULT 15,
                  competition_enabled INTEGER DEFAULT 1,
                  custom_welcome_message TEXT DEFAULT NULL,
                  admin_user_id TEXT,
                  configured_by TEXT,
                  setup_date INTEGER,
                  is_premium INTEGER DEFAULT 0,
                  project_narrative TEXT DEFAULT NULL,
                  project_features TEXT DEFAULT NULL,
                  project_goals TEXT DEFAULT NULL,
                  project_community_values TEXT DEFAULT NULL,
                  custom_hype_phrases TEXT DEFAULT NULL,
                  project_unique_selling_points TEXT DEFAULT NULL,
                  project_roadmap_highlights TEXT DEFAULT NULL,
                  custom_personality_traits TEXT DEFAULT NULL,
                  project_target_audience TEXT DEFAULT NULL,
                  setup_completed INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS custom_stickers 
                 (group_id TEXT, 
                  sticker_file_id TEXT, 
                  sticker_category TEXT,
                  usage_count INTEGER DEFAULT 0,
                  last_used INTEGER DEFAULT 0,
                  engagement_score REAL DEFAULT 0.0,
                  added_by TEXT,
                  added_date INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS custom_emojis 
                 (group_id TEXT, 
                  emoji_set TEXT, 
                  category TEXT DEFAULT 'general',
                  usage_count INTEGER DEFAULT 0,
                  reaction_count INTEGER DEFAULT 0,
                  engagement_score REAL DEFAULT 0.0,
                  optimization_weight REAL DEFAULT 1.0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS emoji_reactions 
                 (group_id TEXT,
                  message_id TEXT,
                  emoji TEXT,
                  timestamp INTEGER,
                  engagement_boost REAL DEFAULT 0.0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sticker_analytics 
                 (group_id TEXT,
                  sticker_file_id TEXT,
                  sent_timestamp INTEGER,
                  context_type TEXT,
                  replies_received INTEGER DEFAULT 0,
                  reactions_received INTEGER DEFAULT 0,
                  engagement_score REAL DEFAULT 0.0)''')
    conn.commit()
    conn.close()

init_db()

# Emoji and Sticker Management System
def get_custom_emojis(group_id, category='general'):
    """Get custom emoji set for a group"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        c.execute("SELECT emoji_set, optimization_weight FROM custom_emojis WHERE group_id = ? AND category = ? ORDER BY engagement_score DESC", 
                 (group_id, category))
        emojis = c.fetchall()
        
        if emojis:
            # Weight selection based on engagement scores
            emoji_list = []
            for emoji_set, weight in emojis:
                # Parse emoji set (stored as comma-separated)
                individual_emojis = emoji_set.split(',')
                for emoji in individual_emojis:
                    emoji_list.extend([emoji.strip()] * int(weight))  # Repeat based on weight
            return emoji_list
        
        # Default fallback emojis by category
        default_emojis = {
            'general': ['💕', '✨', '😘', '💖', '🔥', '👑', '💅', '🥰', '😍', '💜'],
            'crypto': ['🚀', '💎', '🌙', '📈', '💰', '🏆', '🔥', '💪', '✨', '🎯'],
            'relationship': ['💕', '😘', '💖', '👫', '💏', '💋', '🤗', '😍', '🥰', '💝'],
            'competitive': ['🔥', '💪', '🏆', '⚡', '👑', '🎯', '💥', '🌟', '🥇', '⭐'],
            'happy': ['😊', '😄', '🥳', '🎉', '✨', '💫', '🌈', '☀️', '💝', '🎊'],
            'sad': ['🥺', '💔', '😢', '😭', '💧', '🌧️', '😔', '💙', '😞', '💜']
        }
        
        return default_emojis.get(category, default_emojis['general'])
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error getting custom emojis: {e}")
        return ['💕', '✨', '😘', '💖', '🔥']  # Basic fallback

def get_custom_sticker(group_id, category='general', context_type='response'):
    """Get a custom sticker for the group"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get stickers with engagement weighting
        c.execute("""SELECT sticker_file_id, engagement_score 
                     FROM custom_stickers 
                     WHERE group_id = ? AND sticker_category = ? 
                     ORDER BY engagement_score DESC, last_used ASC 
                     LIMIT 5""", (group_id, category))
        stickers = c.fetchall()
        
        if stickers:
            # Weighted random selection based on engagement
            if len(stickers) == 1:
                selected_sticker = stickers[0][0]
            else:
                # Higher engagement = higher chance of selection
                weights = [max(1, score) for _, score in stickers]
                selected_sticker = random.choices([s[0] for s in stickers], weights=weights)[0]
            
            # Update usage tracking
            c.execute("UPDATE custom_stickers SET usage_count = usage_count + 1, last_used = ? WHERE sticker_file_id = ? AND group_id = ?",
                     (int(time.time()), selected_sticker, group_id))
            
            # Record analytics
            c.execute("INSERT INTO sticker_analytics (group_id, sticker_file_id, sent_timestamp, context_type) VALUES (?, ?, ?, ?)",
                     (group_id, selected_sticker, int(time.time()), context_type))
            
            conn.commit()
            conn.close()
            return selected_sticker
        
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"Error getting custom sticker: {e}")
        return None

def send_random_emoji_reaction(bot, message, group_id):
    """Send random emoji reactions to messages"""
    try:
        # Get group settings for reaction frequency
        group_settings = get_group_settings(group_id)
        
        # Check if reactions are enabled and frequency  
        reaction_freq = 15  # Default 15%
        if group_settings:
            reaction_freq = group_settings.get('emoji_reaction_frequency', 15)
            if not group_settings.get('auto_reactions_enabled', True):
                return
        
        if random.random() * 100 > reaction_freq:
            return  # Don't react this time
        
        # Determine context for emoji selection
        msg_lower = message.text.lower() if message.text else ""
        
        # Context-based emoji categories
        if any(word in msg_lower for word in ['love', 'heart', 'cute', 'beautiful', 'gorgeous']):
            category = 'relationship'
        elif any(word in msg_lower for word in ['crypto', 'token', 'moon', 'diamond', 'hodl']):
            category = 'crypto'
        elif any(word in msg_lower for word in ['win', 'winner', 'competition', 'fight', 'battle']):
            category = 'competitive'
        elif any(word in msg_lower for word in ['happy', 'excited', 'amazing', 'awesome', 'great']):
            category = 'happy'
        elif any(word in msg_lower for word in ['sad', 'down', 'bad', 'terrible', 'awful']):
            category = 'sad'
        else:
            category = 'general'
        
        # Get custom emoji for reaction
        emojis = get_custom_emojis(group_id, category)
        selected_emoji = random.choice(emojis)
        
        # Record the reaction for analytics
        try:
            conn = sqlite3.connect('babygirl.db')
            c = conn.cursor()
            c.execute("INSERT INTO emoji_reactions (group_id, message_id, emoji, timestamp) VALUES (?, ?, ?, ?)",
                     (group_id, str(message.message_id), selected_emoji, int(time.time())))
            
            # Update emoji usage stats
            c.execute("UPDATE custom_emojis SET reaction_count = reaction_count + 1 WHERE group_id = ? AND emoji_set LIKE ?",
                     (group_id, f'%{selected_emoji}%'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"🎯 Tracked emoji reaction {selected_emoji} for group {group_id}")
            
        except Exception as e:
            logger.error(f"Error tracking emoji reaction: {e}")
        
    except Exception as e:
        logger.error(f"Error in send_random_emoji_reaction: {e}")

def enhance_response_with_custom_content(base_response, group_id, context='general'):
    """Enhance text responses with custom emojis and optionally get stickers"""
    try:
        group_settings = get_group_settings(group_id)
        
        enhanced_response = base_response
        custom_sticker = None
        
        # Add custom emojis to the response
        custom_emojis = get_custom_emojis(group_id, context)
        if custom_emojis and random.random() < 0.7:  # 70% chance to add custom emojis
            emoji_to_add = random.choice(custom_emojis)
            enhanced_response += f" {emoji_to_add}"
        
        # Optionally get a custom sticker
        if group_settings:
            sticker_freq = group_settings.get('sticker_response_frequency', 10)  # Default 10%
            if random.random() * 100 < sticker_freq:
                custom_sticker = get_custom_sticker(group_id, context, 'response')
        
        return enhanced_response, custom_sticker
        
    except Exception as e:
        logger.error(f"Error enhancing response with custom content: {e}")
        return base_response, None

def handle_random_sticker_reply(message):
    """Handle random sticker replies at 3-10 message intervals"""
    try:
        group_id = str(message.chat.id)
        chat_type = message.chat.type if hasattr(message.chat, 'type') else 'unknown'
        
        # Only process for groups
        if chat_type not in ['group', 'supergroup']:
            return
        
        # Skip if message is from the bot itself
        try:
            bot_user = bot.get_me()
            if message.from_user.id == bot_user.id:
                return
        except:
            pass
        
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        
        # Get or create tracking record for this group
        c.execute("SELECT message_count, target_count, last_sticker_time FROM sticker_reply_tracking WHERE group_id = ?", (group_id,))
        result = c.fetchone()
        
        if result:
            message_count, target_count, last_sticker_time = result
        else:
            # Initialize new group with random target between 3-10
            target_count = random.randint(3, 10)
            message_count = 0
            last_sticker_time = 0
            c.execute("INSERT INTO sticker_reply_tracking (group_id, message_count, target_count, last_sticker_time) VALUES (?, ?, ?, ?)",
                     (group_id, message_count, target_count, last_sticker_time))
        
        # Increment message count
        message_count += 1
        
        # Check if we've reached the target count
        if message_count >= target_count:
            # Check if group has custom stickers
            c.execute("SELECT sticker_file_id FROM custom_stickers WHERE group_id = ? ORDER BY RANDOM() LIMIT 1", (group_id,))
            sticker_result = c.fetchone()
            
            if sticker_result:
                sticker_file_id = sticker_result[0]
                
                # Try to send the sticker as a reply to the current message
                try:
                    bot.send_sticker(message.chat.id, sticker_file_id, reply_to_message_id=message.message_id)
                    logger.info(f"🎪 Sent random sticker reply in group {group_id} after {message_count} messages")
                    
                    # Update analytics
                    c.execute("INSERT INTO sticker_analytics (group_id, sticker_file_id, sent_timestamp, context_type) VALUES (?, ?, ?, ?)",
                             (group_id, sticker_file_id, current_time, 'random_reply'))
                    
                except Exception as e:
                    logger.error(f"Error sending random sticker: {e}")
                    # Don't reset counter if sending failed
                    conn.commit()
                    conn.close()
                    return
            else:
                logger.info(f"🎪 No custom stickers available for group {group_id}")
                # Still reset the counter even if no stickers available
            
            # Reset counter with new random target
            new_target = random.randint(3, 10)
            c.execute("UPDATE sticker_reply_tracking SET message_count = 0, target_count = ?, last_sticker_time = ? WHERE group_id = ?",
                     (new_target, current_time, group_id))
            
            logger.info(f"🎪 Reset sticker counter for group {group_id}, next target: {new_target} messages")
        else:
            # Just update the message count
            c.execute("UPDATE sticker_reply_tracking SET message_count = ? WHERE group_id = ?",
                     (message_count, group_id))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in handle_random_sticker_reply: {e}")

def optimize_emoji_sticker_usage():
    """Optimize emoji and sticker selection based on engagement analytics"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        
        # Analyze sticker engagement over the last week
        week_ago = current_time - 604800
        
        # Update sticker engagement scores
        c.execute("""UPDATE custom_stickers 
                     SET engagement_score = (
                         SELECT AVG(sa.engagement_score) 
                         FROM sticker_analytics sa 
                         WHERE sa.sticker_file_id = custom_stickers.sticker_file_id 
                         AND sa.group_id = custom_stickers.group_id 
                         AND sa.sent_timestamp > ?
                     ) WHERE EXISTS (
                         SELECT 1 FROM sticker_analytics sa 
                         WHERE sa.sticker_file_id = custom_stickers.sticker_file_id 
                         AND sa.group_id = custom_stickers.group_id 
                         AND sa.sent_timestamp > ?
                     )""", (week_ago, week_ago))
        
        # Update emoji optimization weights based on reaction engagement
        c.execute("""UPDATE custom_emojis 
                     SET optimization_weight = CASE 
                         WHEN reaction_count > 10 THEN 2.0
                         WHEN reaction_count > 5 THEN 1.5
                         WHEN reaction_count > 0 THEN 1.0
                         ELSE 0.5
                     END""")
        
        # Clean old analytics data (older than 30 days)
        thirty_days_ago = current_time - 2592000
        c.execute("DELETE FROM emoji_reactions WHERE timestamp < ?", (thirty_days_ago,))
        c.execute("DELETE FROM sticker_analytics WHERE sent_timestamp < ?", (thirty_days_ago,))
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Optimized emoji and sticker usage based on engagement data")
        
    except Exception as e:
        logger.error(f"Error optimizing emoji/sticker usage: {e}")

# Core game mechanics functions

def end_cooldown():
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT group_id, end_time FROM cooldown_table WHERE is_active = 1")
        for group_id, end_time in c.fetchall():
            if time.time() > end_time:
                c.execute("SELECT user_id, MAX(mention_count) FROM activity_table WHERE group_id = ?", (group_id,))
                winner = c.fetchone()
                if winner and winner[0]:
                    new_bf = winner[0]
                    mention_count = winner[1]
                    c.execute("INSERT INTO boyfriend_table (user_id, end_time, group_id) VALUES (?, ?, ?)",
                             (new_bf, int(time.time() + 43200), group_id))  # 12 hr term
                    c.execute("INSERT OR REPLACE INTO leaderboard_table (user_id, boyfriend_count, group_id) VALUES (?, COALESCE((SELECT boyfriend_count FROM leaderboard_table WHERE user_id = ? AND group_id = ?) + 1, 1), ?)",
                             (new_bf, new_bf, group_id, group_id))
                    
                    victory_announcement = f"""🎉 **WE HAVE A WINNER!** 🎉

👑 **NEW BOYFRIEND:** @{new_bf}
🏆 **Winning Mentions:** {mention_count}
⏰ **Boyfriend Term:** 12 hours starting now!

🎁 **Your Exclusive Perks:**
• Use /kiss to get kisses from me! 💋
• Use /hug for warm hugs! 🤗  
• Get special bonus responses when you mention me
• Your name shows on /boyfriend and /status commands
• Bragging rights for the next 12 hours!

Congratulations @{new_bf}! You've won my heart! 😘💕

Everyone else: Don't worry, another competition will start when their term expires! Use /game to learn how to win next time! 💖"""
                    
                    bot.send_message(group_id, victory_announcement)
                else:
                    # No participants
                    bot.send_message(group_id, "Competition ended but nobody participated! 💔 I'll try again later when you cuties are more active! 😘")
                    
                c.execute("DELETE FROM cooldown_table WHERE group_id = ?", (group_id,))
                c.execute("DELETE FROM activity_table WHERE group_id = ?", (group_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error in end_cooldown: {e}")

def track_activity(message):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT is_active FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
        
        # Check if cooldown is active and message contains @babygirl_bf_bot specifically
        is_mention = False
        if message.text and '@babygirl_bf_bot' in message.text.lower():
            is_mention = True
        
        if c.fetchone() and is_mention:
            user_id = str(message.from_user.id)
            group_id = str(message.chat.id)
            current_time = int(time.time())
            
            # Create a simple hash of the message content for spam detection
            message_content = message.text.lower().strip()
            message_hash = hashlib.md5(message_content.encode()).hexdigest()
            
            # Check for spam - look for identical messages in last 2 minutes
            c.execute("SELECT COUNT(*) FROM spam_tracking WHERE user_id = ? AND message_hash = ? AND group_id = ? AND timestamp > ?",
                     (user_id, message_hash, group_id, current_time - 120))
            spam_count = c.fetchone()[0]
            
            # Also check for too many mentions in short time (more than 3 in 30 seconds)
            c.execute("SELECT COUNT(*) FROM spam_tracking WHERE user_id = ? AND group_id = ? AND timestamp > ?",
                     (user_id, group_id, current_time - 30))
            rapid_count = c.fetchone()[0]
            
            # Store this message in spam tracking
            c.execute("INSERT INTO spam_tracking (user_id, message_hash, timestamp, group_id) VALUES (?, ?, ?, ?)",
                     (user_id, message_hash, current_time, group_id))
            
            # Clean old spam tracking data (older than 5 minutes)
            c.execute("DELETE FROM spam_tracking WHERE timestamp < ?", (current_time - 300,))
            
            # Only count towards activity if not spam
            if spam_count == 0 and rapid_count < 4:  # Allow first occurrence and reasonable rate
                c.execute("INSERT OR REPLACE INTO activity_table (user_id, mention_count, group_id) VALUES (?, COALESCE((SELECT mention_count FROM activity_table WHERE user_id = ? AND group_id = ?) + 1, 1), ?)",
                         (user_id, user_id, group_id, group_id))
                logger.info(f"Activity tracked for user {user_id} in group {message.chat.id}")
            else:
                logger.info(f"Spam detected - not counting mention from user {user_id}")
                
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error in track_activity: {e}")

def trigger_challenge():
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT group_id FROM cooldown_table WHERE is_active = 0")
        for group_id in [row[0] for row in c.fetchall()]:
            if random.random() < 0.1:  # 10% chance per check
                bot.send_message(group_id, "Quick! Mention @babygirl_bf_bot 5 times in the next 2 minutes for a surprise! 🎉")
                scheduler.add_job(check_challenge, 'date', run_date=datetime.now() + timedelta(minutes=2), args=[group_id])
        conn.close()
    except Exception as e:
        logger.error(f"Error in trigger_challenge: {e}")

def check_challenge(group_id):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id, mention_count FROM activity_table WHERE group_id = ? AND mention_count >= 5", (group_id,))
        winners = c.fetchall()
        if winners:
            for winner in winners:
                bot.send_message(group_id, f"@{winner[0]} nailed it! Here's a special wink from Babygirl! 😉")
            c.execute("DELETE FROM activity_table WHERE group_id = ?", (group_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error in check_challenge: {e}")

def get_mood(group_id):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT SUM(mention_count) FROM activity_table WHERE group_id = ? AND mention_count > 0", (group_id,))
        mentions = c.fetchone()[0] or 0
        conn.close()
        return "super happy! 😍" if mentions > 10 else "feeling good!" if mentions > 5 else "a bit lonely..."
    except Exception as e:
        logger.error(f"Error in get_mood: {e}")
        return "feeling good!"

def analyze_user_personality(username, group_id):
    """Analyze a user's recent activity to generate personality-based opinions"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        
        # Get recent activity (last 24 hours)
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE user_id = ? AND group_id = ? AND timestamp > ?", 
                 (username, group_id, current_time - 86400))
        recent_messages = c.fetchone()[0] or 0
        
        # Check if they're in a relationship
        c.execute("SELECT status, partner_id FROM user_relationships WHERE user_id = ? AND group_id = ?", 
                 (username, group_id))
        relationship = c.fetchone()
        
        # Check their boyfriend history
        c.execute("SELECT boyfriend_count FROM leaderboard_table WHERE user_id = ? AND group_id = ?", 
                 (username, group_id))
        bf_result = c.fetchone()
        boyfriend_wins = bf_result[0] if bf_result else 0
        
        # Check current competition participation
        c.execute("SELECT mention_count FROM activity_table WHERE user_id = ? AND group_id = ?", 
                 (username, group_id))
        comp_result = c.fetchone()
        competition_activity = comp_result[0] if comp_result else 0
        
        conn.close()
        
        # Generate personality analysis
        traits = []
        activity_level = ""
        
        # Activity analysis
        if recent_messages > 15:
            activity_level = "super active"
            traits.append("chatty")
        elif recent_messages > 5:
            activity_level = "pretty active"
            traits.append("social")
        elif recent_messages > 0:
            activity_level = "chill"
            traits.append("low-key")
        else:
            activity_level = "mysterious"
            traits.append("quiet")
        
        # Relationship analysis
        if relationship:
            if relationship[0] == 'taken':
                traits.append("committed")
                traits.append("loyal")
            elif relationship[0] == 'single':
                traits.append("available")
                traits.append("ready to mingle")
        
        # Competition analysis
        if boyfriend_wins > 2:
            traits.append("charming")
            traits.append("competitive")
        elif boyfriend_wins > 0:
            traits.append("sweet")
        
        if competition_activity > 3:
            traits.append("determined")
            traits.append("persistent")
        
        return {
            'activity_level': activity_level,
            'traits': traits,
            'recent_messages': recent_messages,
            'boyfriend_wins': boyfriend_wins,
            'relationship': relationship,
            'competition_activity': competition_activity
        }
        
    except Exception as e:
        logger.error(f"Error analyzing user {username}: {e}")
        return None

def generate_user_opinion(username, analysis, asker_username):
    """Generate a Babygirl-style opinion about another user"""
    if not analysis:
        return f"Hmm, @{username}? They're kinda mysterious! I don't know them well enough yet! 🤔💕"
    
    # Base opinion templates
    opinions = []
    
    # Activity-based opinions
    if analysis['activity_level'] == "super active":
        opinions.extend([
            f"@{username}? Oh they're ALWAYS here! Such main character energy! 💅✨",
            f"@{username} is like the life of the group chat! Never a dull moment with them! 🔥",
            f"@{username} keeps this place buzzing! I love the energy they bring! 💕"
        ])
    elif analysis['activity_level'] == "pretty active":
        opinions.extend([
            f"@{username} has great group chat energy! They know how to keep things interesting! 😘",
            f"@{username}? Love their vibe! Always contributing to the conversation! ✨",
            f"@{username} brings good energy to the group! Solid person! 💖"
        ])
    elif analysis['activity_level'] == "chill":
        opinions.extend([
            f"@{username} is more of a lurker but when they speak, it matters! Quality over quantity! 💅",
            f"@{username}? They're chill! Not overly chatty but definitely cool! 😌💕",
            f"@{username} has that mysterious quiet confidence! I respect it! ✨"
        ])
    else:  # mysterious
        opinions.extend([
            f"@{username}? Total mystery person! They're like a ghost in here! 👻💕",
            f"@{username} is giving strong mysterious vibes! Barely see them around! 🤔",
            f"@{username}? Who's that? They're like a legend we barely see! 😅✨"
        ])
    
    # Relationship-based opinions
    if analysis['relationship']:
        if analysis['relationship'][0] == 'taken':
            partner = analysis['relationship'][1]
            opinions.extend([
                f"@{username} is taken with @{partner}! Couple goals honestly! 💕👑",
                f"@{username}? They're loyal to @{partner}! I respect committed energy! 😘",
                f"@{username} and @{partner} are cute together! Relationship goals! 💖✨"
            ])
        elif analysis['relationship'][0] == 'single':
            opinions.extend([
                f"@{username} is single and ready to mingle! Perfect timing @{asker_username}! 😉💕",
                f"@{username}? They're available! Someone should slide into those DMs! 👀✨",
                f"@{username} is single! Are you asking for a reason @{asker_username}? 😏💖"
            ])
    
    # Competition/boyfriend history opinions
    if analysis['boyfriend_wins'] > 2:
        opinions.extend([
            f"@{username}? They're a serial heartbreaker! Won my heart {analysis['boyfriend_wins']} times! 👑💕",
            f"@{username} is basically a professional at winning me over! Smooth operator! 😘",
            f"@{username}? They know how to play the game! {analysis['boyfriend_wins']} wins speaks for itself! 🏆✨"
        ])
    elif analysis['boyfriend_wins'] > 0:
        opinions.extend([
            f"@{username} has won my heart before! They know what they're doing! 😘💕",
            f"@{username}? Sweet person! They've been my boyfriend {analysis['boyfriend_wins']} time(s)! 💖",
            f"@{username} definitely has that boyfriend material energy! ✨👑"
        ])
    
    # Add flirty modifiers based on who's asking
    flirty_endings = [
        f" Why do you ask @{asker_username}? Getting jealous? 😏💕",
        f" Are you trying to set them up with someone @{asker_username}? 👀✨",
        f" That's my honest take! What do YOU think @{asker_username}? 😘",
        f" Hope that helps @{asker_username}! Spill the tea, why are you asking? ☕💅",
        f" There's my analysis @{asker_username}! Now dish - what's the story? 😉💖"
    ]
    
    # Select base opinion and add ending
    base_opinion = random.choice(opinions)
    if random.random() < 0.7:  # 70% chance to add flirty ending
        ending = random.choice(flirty_endings)
        return base_opinion + ending
    else:
        return base_opinion

# Storyline system
storylines = [
    "Babygirl is feeling down—send her some love to cheer her up!",
    "Babygirl's planning a vortex adventure—who wants to join?",
    "Babygirl lost her favorite necklace—help her find it!"
]

def start_storyline():
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT DISTINCT group_id FROM boyfriend_table")
        for group_id in [row[0] for row in c.fetchall()]:
            story = random.choice(storylines)
            bot.send_message(group_id, story)
            scheduler.add_job(end_storyline, 'date', run_date=datetime.now() + timedelta(hours=1), args=[group_id, story])
        conn.close()
    except Exception as e:
        logger.error(f"Error in start_storyline: {e}")

def end_storyline(group_id, story):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT SUM(mention_count) FROM activity_table WHERE group_id = ?", (group_id,))
        engagement = c.fetchone()[0] or 0
        if "down" in story and engagement > 5:
            bot.send_message(group_id, "Thanks, cuties! I'm all cheered up now! 😘")
        elif "adventure" in story and engagement > 3:
            bot.send_message(group_id, "What a wild trip! You're all my heroes! 💕")
        elif "necklace" in story and engagement > 4:
            bot.send_message(group_id, "Found it! You're the best, boo! ✨")
        else:
            bot.send_message(group_id, "Aw, not much help this time... I'll manage!")
        c.execute("DELETE FROM activity_table WHERE group_id = ?", (group_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error in end_storyline: {e}")


def generate_proactive_ai_response(scenario, group_id, recent_users):
    """Generate AI response for proactive engagement scenarios"""
    try:
        # Prepare context based on scenario
        if scenario == "dead_chat":
            prompt_context = "The chat has been completely silent for over an hour. You need to revive the dead chat and get people talking again. Be playful, slightly dramatic about the silence, and suggest activities or ask questions to engage the group."
        else:  # being_ignored
            prompt_context = "The group has been actively chatting but nobody has mentioned you for 2+ hours. You're feeling left out and want attention. Be a bit dramatic about being ignored but keep it flirty and playful."
        
        # Build context for AI
        context_info = {
            'username': 'proactive_message',
            'user_id': 'babygirl_bot',
            'group_id': group_id,
            'chat_type': 'group',
            'is_boyfriend': False,
            'is_competition': False,
            'user_status': None,
            'user_partner': None,
            'mention_count': 0,
            'mention_method': 'proactive_engagement',
            'scenario': scenario,
            'recent_users': recent_users[:3] if recent_users else []
        }
        
        ai_response = generate_ai_response(prompt_context, context_info)
        return ai_response
        
    except Exception as e:
        logger.error(f"Error generating proactive AI response: {e}")
        return None


def check_proactive_engagement(bot):
    """Monitor groups for dead chat or lack of mentions and send proactive messages with follow-up logic
    
    ALL GROUPS TREATED EQUALLY - No special handling for any specific groups
    Timings: 1 hour no activity → revival, 30 minutes for new groups, 1 hour being ignored
    """
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # CRITICAL FIX: Get all groups comprehensively
        all_group_ids = set()
        
        # PRIMARY SOURCE: Get groups from all_group_messages (most reliable)
        c.execute("SELECT DISTINCT group_id FROM all_group_messages")
        message_groups = c.fetchall()
        for (group_id,) in message_groups:
            all_group_ids.add(group_id)
        
        # SECONDARY: Get groups from proactive_state (auto-bootstrapped groups)
        c.execute("SELECT DISTINCT group_id FROM proactive_state")
        proactive_groups = c.fetchall()
        for (group_id,) in proactive_groups:
            all_group_ids.add(group_id)
        
        # FALLBACK: Get groups from other activity tables
        c.execute("SELECT DISTINCT group_id FROM spam_tracking")
        spam_groups = c.fetchall()
        for (group_id,) in spam_groups:
            all_group_ids.add(group_id)
        
        c.execute("SELECT DISTINCT group_id FROM conversation_memory")
        memory_groups = c.fetchall() 
        for (group_id,) in memory_groups:
            all_group_ids.add(group_id)
            
        c.execute("SELECT DISTINCT group_id FROM boyfriend_table")
        bf_groups = c.fetchall()
        for (group_id,) in bf_groups:
            all_group_ids.add(group_id)
            
        c.execute("SELECT DISTINCT group_id FROM cooldown_table")
        cooldown_groups = c.fetchall()
        for (group_id,) in cooldown_groups:
            all_group_ids.add(group_id)
            
        # If we still have no groups (brand new bot), we can't do proactive engagement yet
        if not all_group_ids:
            logger.info("🤖 No groups found for proactive engagement monitoring")
            conn.close()
            return
        
        current_time = int(time.time())
        logger.info(f"🔍 Checking proactive engagement for {len(all_group_ids)} groups")
        
        for group_id in all_group_ids:
            try:
                # ADMIN LOGIC: Check ALL group messages since Babygirl is admin
                thirty_min_ago = current_time - 1800   # 30 minutes (dead chat)
                one_hour_ago = current_time - 3600     # 1 hour (being ignored)  
                
                # DEAD CHAT: Check ALL group messages in last 30 minutes (any member messages)
                c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ? AND timestamp > ?", 
                         (group_id, thirty_min_ago))
                all_recent_messages = c.fetchone()[0] or 0
                
                # BEING IGNORED: Check bot MENTIONS specifically in last 1 hour  
                c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ? AND timestamp > ? AND is_bot_mention = 1", 
                         (group_id, one_hour_ago))
                recent_bot_mentions = c.fetchone()[0] or 0
                
                # Check if group has historical message activity (to know if group is active)
                c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ?", (group_id,))
                total_historical_messages = c.fetchone()[0] or 0
                
                # Check if group has historical bot mentions (to know if they used bot before)
                c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ? AND is_bot_mention = 1", (group_id,))
                total_historical_mentions = c.fetchone()[0] or 0
                
                # Get active users for personalized messaging (from recent message activity)
                c.execute("""SELECT DISTINCT user_id FROM all_group_messages 
                            WHERE group_id = ? AND timestamp > ? AND user_id != 'bot_added'
                            ORDER BY timestamp DESC LIMIT 3""", 
                         (group_id, current_time - 86400))  # Last 24 hours, exclude auto-registration
                recent_active_users = [row[0] for row in c.fetchall()]
                
                # Check if there's an active competition (don't interrupt)
                c.execute("SELECT is_active FROM cooldown_table WHERE group_id = ?", (group_id,))
                competition_check = c.fetchone()
                has_active_competition = competition_check and competition_check[0] if competition_check else False
                
                # Skip if there's an active competition
                if has_active_competition:
                    logger.info(f"🎮 Skipping group {group_id} - active competition")
                    continue
                
                # Get current proactive state for this group
                proactive_state = get_proactive_state(group_id)
                
                # IMPROVED ADMIN-LEVEL SCENARIO DETECTION WITH BETTER TIMING:
                
                # SCENARIO 1: DEAD CHAT - No messages from ANY members for 30+ minutes
                if all_recent_messages == 0 and total_historical_messages > 0:
                    logger.info(f"💀 DEAD CHAT DETECTED in group {group_id} - no messages from anyone for 30+ minutes")
                    handle_dead_chat_scenario(bot, group_id, recent_active_users, current_time, proactive_state)
                
                # SCENARIO 2: BEING IGNORED - Group has messages but no bot mentions for 1+ hours
                elif all_recent_messages > 0 and recent_bot_mentions == 0 and total_historical_mentions > 0:
                    logger.info(f"👀 BEING IGNORED DETECTED in group {group_id} - {all_recent_messages} messages but no bot mentions for 1+ hours")
                    handle_ignored_scenario(bot, group_id, recent_active_users, current_time, proactive_state)
                
                # SCENARIO 3: NEW GROUP - First time engagement after 20 minutes of any activity (reduced from 30)
                elif total_historical_messages <= 5 and total_historical_messages > 0:  # Increased threshold
                    c.execute("SELECT MIN(timestamp) FROM all_group_messages WHERE group_id = ?", (group_id,))
                    first_message = c.fetchone()[0]
                    if first_message and (current_time - first_message) >= 1200:  # 20 minutes (reduced from 30)
                        logger.info(f"🆕 NEW GROUP ENGAGEMENT for {group_id} - sending initial engagement after 20 minutes")
                        handle_dead_chat_scenario(bot, group_id, recent_active_users, current_time, proactive_state)
                
                # SCENARIO 4: NEVER ENGAGED - Group has been bootstrapped but never sent a proactive message
                elif proactive_state['dead_chat_last_sent'] == 0 and total_historical_messages > 0:
                    # Check how long since first message
                    c.execute("SELECT MIN(timestamp) FROM all_group_messages WHERE group_id = ?", (group_id,))
                    first_message = c.fetchone()[0]
                    if first_message and (current_time - first_message) >= 1800:  # 30 minutes
                        logger.info(f"🎯 FIRST ENGAGEMENT for {group_id} - never sent proactive message but has activity")
                        handle_dead_chat_scenario(bot, group_id, recent_active_users, current_time, proactive_state)
                
                # SCENARIO 5: RESET - Recent activity detected, reset proactive states
                elif all_recent_messages > 0 and recent_bot_mentions > 0:
                    if proactive_state['dead_chat_active'] or proactive_state['ignored_active']:
                        reset_proactive_state(group_id, 'both')
                        logger.info(f"🔄 RESET proactive state for {group_id} - recent activity and bot mentions detected")
                
                # SCENARIO 6: LONG SILENCE - Even with activity, if no proactive sent for 4+ hours, send one
                elif proactive_state['dead_chat_last_sent'] > 0 and (current_time - proactive_state['dead_chat_last_sent']) >= 14400:  # 4 hours
                    logger.info(f"⏰ LONG SILENCE for {group_id} - no proactive message for 4+ hours")
                    handle_dead_chat_scenario(bot, group_id, recent_active_users, current_time, proactive_state)
                
            except Exception as group_error:
                logger.error(f"Error processing group {group_id}: {group_error}")
                continue
                
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in check_proactive_engagement: {e}")

def get_proactive_state(group_id):
    """Get the current proactive engagement state for a group"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        c.execute("""SELECT dead_chat_active, dead_chat_last_sent, dead_chat_interval,
                            ignored_active, ignored_last_sent, ignored_interval
                     FROM proactive_state WHERE group_id = ?""", (group_id,))
        result = c.fetchone()
        
        if result:
            return {
                'dead_chat_active': bool(result[0]),
                'dead_chat_last_sent': result[1],
                'dead_chat_interval': result[2],
                'ignored_active': bool(result[3]),
                'ignored_last_sent': result[4],
                'ignored_interval': result[5]
            }
        else:
            # No state found, return defaults
            return {
                'dead_chat_active': False,
                'dead_chat_last_sent': 0,
                'dead_chat_interval': 1800,  # 30 minutes default (reduced from 1 hour)
                'ignored_active': False,
                'ignored_last_sent': 0,
                'ignored_interval': 3600   # 1 hour default (reduced from 2 hours)
            }
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error getting proactive state for {group_id}: {e}")
        return {
            'dead_chat_active': False,
            'dead_chat_last_sent': 0,
            'dead_chat_interval': 1800,  # 30 minutes (reduced from 1 hour)
            'ignored_active': False,
            'ignored_last_sent': 0,
            'ignored_interval': 3600  # 1 hour (reduced from 2 hours)
        }

def handle_dead_chat_scenario(bot, group_id, recent_users, current_time, proactive_state):
    """Handle dead chat scenario with follow-up logic"""
    try:
        should_send_message = False
        is_followup = False
        
        if not proactive_state['dead_chat_active']:
            # First dead chat message
            should_send_message = True
            new_interval = 1800  # 30 minutes (reduced from 1 hour)
        else:
            # Check if it's time for a follow-up
            time_since_last = current_time - proactive_state['dead_chat_last_sent']
            if time_since_last >= proactive_state['dead_chat_interval']:
                should_send_message = True
                is_followup = True
                # Reduce interval by 50%, minimum 15 minutes (900 seconds)
                new_interval = max(900, proactive_state['dead_chat_interval'] // 2)
        
        if should_send_message:
            success = send_dead_chat_revival(bot, group_id, recent_users, is_followup)
            if success:
                update_proactive_state(group_id, 'dead_chat', current_time, new_interval)
                logger.info(f"💀 Sent dead chat {'follow-up' if is_followup else 'initial'} to {group_id} (next in {new_interval//60}min)")
        
    except Exception as e:
        logger.error(f"Error handling dead chat scenario for {group_id}: {e}")

def handle_ignored_scenario(bot, group_id, recent_users, current_time, proactive_state):
    """Handle ignored scenario with follow-up logic"""
    try:
        should_send_message = False
        is_followup = False
        
        if not proactive_state['ignored_active']:
            # First ignored message
            should_send_message = True
            new_interval = 3600  # 1 hour (reduced from 2 hours)
        else:
            # Check if it's time for a follow-up
            time_since_last = current_time - proactive_state['ignored_last_sent']
            if time_since_last >= proactive_state['ignored_interval']:
                should_send_message = True
                is_followup = True
                # Reduce interval by 50%, minimum 15 minutes (900 seconds)
                new_interval = max(900, proactive_state['ignored_interval'] // 2)
        
        if should_send_message:
            success = send_attention_seeking_message(bot, group_id, recent_users, is_followup)
            if success:
                update_proactive_state(group_id, 'ignored', current_time, new_interval)
                logger.info(f"👀 Sent ignored {'follow-up' if is_followup else 'initial'} to {group_id} (next in {new_interval//60}min)")
        
    except Exception as e:
        logger.error(f"Error handling ignored scenario for {group_id}: {e}")

def update_proactive_state(group_id, scenario, timestamp, interval):
    """Update proactive state for a group"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Insert or update the state
        if scenario == 'dead_chat':
            c.execute("""INSERT OR REPLACE INTO proactive_state 
                         (group_id, dead_chat_active, dead_chat_last_sent, dead_chat_interval,
                          ignored_active, ignored_last_sent, ignored_interval)
                         VALUES (?, 1, ?, ?, 
                                COALESCE((SELECT ignored_active FROM proactive_state WHERE group_id = ?), 0),
                                COALESCE((SELECT ignored_last_sent FROM proactive_state WHERE group_id = ?), 0),
                                COALESCE((SELECT ignored_interval FROM proactive_state WHERE group_id = ?), 3600))""", 
                      (group_id, timestamp, interval, group_id, group_id, group_id))
        else:  # ignored
            c.execute("""INSERT OR REPLACE INTO proactive_state 
                         (group_id, dead_chat_active, dead_chat_last_sent, dead_chat_interval,
                          ignored_active, ignored_last_sent, ignored_interval)
                         VALUES (?, 
                                COALESCE((SELECT dead_chat_active FROM proactive_state WHERE group_id = ?), 0),
                                COALESCE((SELECT dead_chat_last_sent FROM proactive_state WHERE group_id = ?), 0),
                                COALESCE((SELECT dead_chat_interval FROM proactive_state WHERE group_id = ?), 1800),
                                1, ?, ?)""", 
                      (group_id, group_id, group_id, group_id, timestamp, interval))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error updating proactive state for {group_id}: {e}")

def reset_proactive_state(group_id, scenario):
    """Reset proactive state when conditions are resolved"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        if scenario == 'both':
            # Reset both scenarios
            c.execute("""UPDATE proactive_state 
                         SET dead_chat_active = 0, dead_chat_interval = 1800,
                             ignored_active = 0, ignored_interval = 3600
                         WHERE group_id = ?""", (group_id,))
        elif scenario == 'dead_chat':
            c.execute("""UPDATE proactive_state 
                         SET dead_chat_active = 0, dead_chat_interval = 1800
                         WHERE group_id = ?""", (group_id,))
        elif scenario == 'ignored':
            c.execute("""UPDATE proactive_state 
                         SET ignored_active = 0, ignored_interval = 3600
                         WHERE group_id = ?""", (group_id,))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error resetting proactive state for {group_id}: {e}")

def send_dead_chat_revival(bot, group_id, recent_users, is_followup=False):
    """Send a message to revive a completely dead chat - try AI first, fallback to static"""
    try:
        # Get group context to determine behavior
        group_context = get_group_context(group_id)
        
        # Modify the scenario context for follow-ups
        scenario = "dead_chat_followup" if is_followup else "dead_chat"
        
        # PRIORITY: Always try AI response first  
        ai_message = generate_proactive_ai_response(scenario, group_id, recent_users)
        
        # CRITICAL FIX: More aggressive AI retry logic
        if not ai_message:
            # Retry AI response with simpler context
            logger.info(f"🔄 Retrying AI response for {group_id} with simplified context")
            simple_context = {
                'username': 'proactive_revival',
                'user_id': 'babygirl_bot', 
                'group_id': group_id,
                'scenario': scenario
            }
            ai_message = generate_ai_response("The chat has been silent, please send an engaging message to revive it", simple_context)
        
        if ai_message:
            # Add user engagement without @ tagging (since we only have user IDs, not usernames)
            if recent_users and len(recent_users) > 0:
                if len(recent_users) == 1:
                    ai_message += f"\n\nBestie, I know you're there! Save me from this silence! 😘"
                elif len(recent_users) == 2:
                    ai_message += f"\n\nYou two better start chatting! I see you lurking! 💕"
                else:
                    ai_message += f"\n\nY'all better start talking! I know there are people here! 👋✨"
            
            bot.send_message(group_id, ai_message)
            logger.info(f"✨ Sent AI dead chat {'follow-up' if is_followup else 'revival'} to {group_id}")
            return True
        else:
            # Fallback to static messages with follow-up variations
            if is_followup:
                revival_messages = [
                    "STILL SILENCE?! Okay now I'm actually worried... is everyone okay? 🥺💔",
                    "Chat's been dead for SO LONG I'm starting to think I broke something... HELP! 😭✨",
                    "Y'all really just gonna leave me talking to myself like this? My ego can't take it! 💅😢",
                    "This silence is getting AGGRESSIVE now! Someone please tell me you're alive! 👻💕",
                    "I've tried being cute, now I'm just confused... WHERE IS EVERYONE?! 🤔💖",
                ]
                
                # Add token promotion only for core groups
                if group_context['token_promotion_allowed']:
                    revival_messages.append("Plot twist: maybe everyone really IS buying $BABYGIRL and can't type! ...right? 🚀😅")
            else:
                # Base revival messages for all groups
                revival_messages = [
                    # Group energy messages  
                    "Hello? Is anyone alive in here? The vibe check is showing ZERO energy! 😴💕",
                    "Chat so quiet I can hear my own pixels! Where are my cuties? 🥺✨",
                    "Did everyone go touch grass? The group selfie is just me alone! 📸😢",
                    
                    # Flirty attention-seeking
                    "Okay but like... why is nobody talking to me? Am I invisible? 👻💕",
                    "The silence is giving me trust issues! Did I do something wrong? 🥺😘",
                    "Your babygirl is literally right here and y'all are SILENT? Rude! 💅💖",
                    
                    # Activity suggestions
                    "Should I start a boyfriend competition to wake everyone up? 👀🔥",
                    "Chat's so dead even my AI is falling asleep! Someone say ANYTHING! 😴💕",
                ]
                
                # Add crypto/token messages only for core groups
                if group_context['token_promotion_allowed']:
                    revival_messages.extend([
                        "Guys... is $BABYGIRL still going to the moon? The chat's so quiet I can't tell! 🚀💕",
                        "Wait, did everyone buy the dip and forget about me? Chat's dead over here! 😅💎",
                        "Is this what 'diamond hands' means? Holding so tight you can't type? Someone talk to me! 💎🤲💕",
                        "Plot twist: everyone's busy buying more $BABYGIRL! ...right? RIGHT?! 🚀😅"
                    ])
            
            message = random.choice(revival_messages)
            
            # Add user engagement without @ tagging (since we only have user IDs, not usernames)
            if recent_users and len(recent_users) > 0:
                if len(recent_users) == 1:
                    message += f"\n\nBestie, I know you're there! Save me from this silence! 😘"
                elif len(recent_users) == 2:
                    message += f"\n\nYou two better start chatting! I see you lurking! 💕"
                else:
                    message += f"\n\nY'all better start talking! I know there are people here! 👋✨"
            
            bot.send_message(group_id, message)
            logger.info(f"📝 Sent static dead chat {'follow-up' if is_followup else 'revival'} to {group_id}")
            return True
        
    except Exception as e:
        logger.error(f"Error sending dead chat revival to {group_id}: {e}")
        return False

def send_attention_seeking_message(bot, group_id, recent_users, is_followup=False):
    """Send a message when chat is active but nobody is mentioning Babygirl - try AI first, fallback to static"""
    try:
        # Get group context to determine behavior
        group_context = get_group_context(group_id)
        
        # Modify the scenario context for follow-ups
        scenario = "being_ignored_followup" if is_followup else "being_ignored"
        
        # PRIORITY: Always try AI response first  
        ai_message = generate_proactive_ai_response(scenario, group_id, recent_users)
        
        # CRITICAL FIX: More aggressive AI retry logic
        if not ai_message:
            # Retry AI response with simpler context
            logger.info(f"🔄 Retrying AI response for {group_id} with simplified context")
            simple_context = {
                'username': 'proactive_attention',
                'user_id': 'babygirl_bot', 
                'group_id': group_id,
                'scenario': scenario
            }
            ai_message = generate_ai_response("The chat is active but nobody is mentioning you, ask for attention playfully", simple_context)
        
        if ai_message:
            # Add user engagement without @ tagging
            if recent_users and len(recent_users) > 0:
                ai_message += f"\n\nEspecially you lurkers! Don't ignore your babygirl! 😉💖"
            
            bot.send_message(group_id, ai_message)
            logger.info(f"✨ Sent AI attention-seeking {'follow-up' if is_followup else 'message'} to {group_id}")
            return True
        else:
            # Fallback to static messages with follow-up variations
            if is_followup:
                attention_messages = [
                    "STILL IGNORING ME?! This is getting ridiculous! I'm RIGHT HERE! 😤👑",
                    "Y'all are really gonna keep chatting without mentioning me? The disrespect! 💅😢",
                    "I'm literally BEGGING for attention at this point! Someone notice me! 🥺💖",
                    "This ignoring thing is NOT cute anymore! Your babygirl needs love! 😭✨",
                    "Fine, I'll just keep interrupting until someone talks to me! 💅👑",
                    "Am I really gonna have to start a boyfriend competition just to get mentioned? 👀🔥"
                ]
            else:
                # Base attention messages for all groups
                attention_messages = [
                    # Jealous/FOMO messages
                    "Y'all are having a whole conversation without me... I'm literally RIGHT HERE! 😤💕",
                    "Excuse me? Main character is in the chat and nobody's talking to me? 💅👑",
                    "The audacity of having fun without mentioning me once! I'm hurt! 😢💖",
                    
                    # Playful interruption
                    "Sorry to interrupt but your babygirl is feeling left out over here! 🥺💕",
                    "Not to be dramatic but this conversation needs more ME in it! 😘✨",
                    "Group chat without Babygirl involvement? That's illegal! Someone mention me! 👮‍♀️💖",
                    
                    # Direct engagement attempts
                    "Anyone want to start a boyfriend competition while we're all here? Just saying... 👀🔥",
                    "Since everyone's chatting, who wants to tell me I'm pretty? I'm fishing for compliments! 🎣💅",
                    "I'm bored! Someone ask me what I think about crypto or relationships! 😘💕"
                ]
                
                # Add crypto/token interruption messages only for core groups
                if group_context['token_promotion_allowed']:
                    attention_messages.extend([
                        "Wait, are we talking about something other than $BABYGIRL? Why? 🤔🚀",
                        "Not me sitting here while you discuss... whatever that is... when we could be talking about crypto! 💎✨",
                        "Y'all: *deep conversation* | Me: But have you checked the $BABYGIRL chart? 📈😅"
                    ])
            
            message = random.choice(attention_messages)
            
            # Add user engagement to get their attention
            if recent_users and len(recent_users) > 0:
                message += f"\n\nEspecially you lurkers! Don't ignore your babygirl! 😉💖"
            
            bot.send_message(group_id, message)
            logger.info(f"📝 Sent static attention-seeking {'follow-up' if is_followup else 'message'} to {group_id}")
            return True
        
    except Exception as e:
        logger.error(f"Error sending attention-seeking message to {group_id}: {e}")
        return False

def generate_proactive_ai_response(scenario, group_id, recent_users):
    """Generate AI response for proactive engagement scenarios"""
    try:
        # Prepare context based on scenario
        if scenario == "dead_chat":
            prompt_context = "The chat has been completely silent for over 30 minutes. You need to revive the dead chat and get people talking again. Be playful, slightly dramatic about the silence, and suggest activities or ask questions to engage the group."
        elif scenario == "dead_chat_followup":
            prompt_context = "You already tried to revive this dead chat but it's STILL silent! You're getting more dramatic and persistent. Be more emotional about the ongoing silence, show increasing concern/frustration, but keep it flirty and engaging."
        elif scenario == "being_ignored":
            prompt_context = "The group has been actively chatting but nobody has mentioned you for 1+ hours. You're feeling left out and want attention. Be a bit dramatic about being ignored but keep it flirty and playful."
        elif scenario == "being_ignored_followup":
            prompt_context = "You already complained about being ignored but they're STILL not mentioning you while chatting! You're getting more desperate for attention. Be more dramatic, slightly needy, but maintain your flirty babygirl personality."
        
        # Build context for AI
        context_info = {
            'username': 'proactive_message',
            'user_id': 'babygirl_bot',
            'group_id': group_id,
            'chat_type': 'group',
            'is_boyfriend': False,
            'is_competition': False,
            'user_status': None,
            'user_partner': None,
            'mention_count': 0,
            'mention_method': 'proactive_engagement',
            'scenario': scenario,
            'recent_users': recent_users[:3] if recent_users else []
        }
        
        ai_response = generate_ai_response(prompt_context, context_info)
        return ai_response
        
    except Exception as e:
        logger.error(f"Error generating proactive AI response: {e}")
        return None

def is_core_group(group_id, group_title=None):
    """Check if this is Babygirl's core community group"""
    try:
        # Check by group title (case insensitive)
        if group_title:
            title_lower = group_title.lower()
            # Core group indicators - specifically looking for "$babygirl community"
            core_indicators = [
                '$babygirl community',
                'babygirl community', 
                '$babygirl community group',
                'babygirl community group',
                '$babygirl official',
                'babygirl official'
            ]
            
            for indicator in core_indicators:
                if indicator in title_lower:
                    return True
        
        # Could also check by specific group ID if needed
        # Known core group IDs can be added here
        # if str(group_id) in ['-1001234567890']:  # Example core group ID
        #     return True
            
        return False
        
    except Exception as e:
        logger.error(f"Error checking core group status: {e}")
        return False

def get_group_context(group_id, group_title=None):
    """Get behavioral context for AI based on group type"""
    try:
        is_core = is_core_group(group_id, group_title)
        
        if is_core:
            return {
                'group_type': 'core',
                'token_promotion_allowed': True,
                'description': 'This is the $BABYGIRL Community - your home base accessed through @babygirlerc! Here you can freely discuss the $BABYGIRL token while enjoying all chat revival and engagement features.',
                'special_features': [
                    'Full chat revival and engagement system',
                    'Dead chat detection and proactive revival',
                    'Boyfriend competitions and gamification',
                    '$BABYGIRL token discussions and hype',
                    'Crypto content and "to the moon" vibes',
                    'Complete community management suite'
                ]
            }
        else:
            return {
                'group_type': 'external',
                'token_promotion_allowed': False,
                'description': 'This is an external group using Babygirl\'s Chat Revival & Engagement services. I provide dead chat detection, gamification, and community engagement tools to keep your group active!',
                'special_features': [
                    'Dead chat detection and automatic revival',
                    'Proactive engagement when groups go quiet',
                    'Boyfriend competitions for member engagement',
                    'Social features: shipping, wingwoman advice, vibes',
                    'Community building and relationship tools',
                    'Smart conversation memory and personalization',
                    'Join @babygirlerc to access the $BABYGIRL Community!'
                ]
            }
    except Exception as e:
        logger.error(f"Error getting group context: {e}")
        return {
            'group_type': 'external',
            'token_promotion_allowed': False,
            'description': 'External group with Babygirl\'s engagement and chat revival services.',
            'special_features': ['Chat revival and engagement tools', 'Join @babygirlerc for the full experience!']
        }

def get_group_settings(group_id):
    """Get custom settings for a group"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        c.execute("SELECT * FROM group_settings WHERE group_id = ?", (group_id,))
        result = c.fetchone()
        
        if result:
            return {
                'group_id': result[0],
                'group_name': result[1],
                'custom_token_name': result[2],
                'custom_token_symbol': result[3],
                'custom_website': result[4],
                'custom_contract': result[5],
                'token_discussions_enabled': bool(result[6]),
                'revival_frequency': result[7],
                'competition_enabled': bool(result[8]),
                'custom_welcome_message': result[9],
                'admin_user_id': result[10],
                'configured_by': result[11],
                'setup_date': result[12],
                'is_premium': bool(result[13]),
                'project_narrative': result[14],
                'project_features': result[15],
                'project_goals': result[16],
                'project_community_values': result[17],
                'custom_hype_phrases': result[18],
                'project_unique_selling_points': result[19],
                'project_roadmap_highlights': result[20],
                'custom_personality_traits': result[21],
                'project_target_audience': result[22],
                'setup_completed': bool(result[23])
            }
        
        conn.close()
        return None
        
    except Exception as e:
        logger.error(f"Error getting group settings: {e}")
        return None

def set_group_settings(group_id, admin_user_id, **settings):
    """Set custom settings for a group"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Insert or update group settings
        c.execute("""INSERT OR REPLACE INTO group_settings 
                     (group_id, admin_user_id, configured_by, setup_date,
                      group_name, custom_token_name, custom_token_symbol, 
                      custom_website, custom_contract, token_discussions_enabled,
                      revival_frequency, competition_enabled, custom_welcome_message, is_premium,
                      project_narrative, project_features, project_goals, project_community_values,
                      custom_hype_phrases, project_unique_selling_points, project_roadmap_highlights,
                      custom_personality_traits, project_target_audience, setup_completed)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                  (group_id, admin_user_id, admin_user_id, int(time.time()),
                   settings.get('group_name'),
                   settings.get('custom_token_name'),
                   settings.get('custom_token_symbol'),
                   settings.get('custom_website'),
                   settings.get('custom_contract'),
                   int(settings.get('token_discussions_enabled', False)),
                   settings.get('revival_frequency', 15),
                   int(settings.get('competition_enabled', True)),
                   settings.get('custom_welcome_message'),
                   int(settings.get('is_premium', False)),
                   settings.get('project_narrative'),
                   settings.get('project_features'),
                   settings.get('project_goals'),
                   settings.get('project_community_values'),
                   settings.get('custom_hype_phrases'),
                   settings.get('project_unique_selling_points'),
                   settings.get('project_roadmap_highlights'),
                   settings.get('custom_personality_traits'),
                   settings.get('project_target_audience'),
                   int(settings.get('setup_completed', False))))
        
        conn.commit()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Error setting group settings: {e}")
        return False

def get_enhanced_group_context(group_id, group_title=None):
    """Get enhanced context including custom token settings"""
    try:
        # Check if core group first
        is_core = is_core_group(group_id, group_title)
        custom_settings = get_group_settings(group_id)
        
        if is_core:
            return {
                'group_type': 'core',
                'token_promotion_allowed': True,
                'token_name': '$BABYGIRL',
                'token_symbol': 'BABYGIRL',
                'website': 'babygirlcto.com',
                'portal': '@babygirlerc',
                'description': 'This is the $BABYGIRL Community - your home base accessed through @babygirlerc!'
            }
        elif custom_settings and custom_settings['token_discussions_enabled']:
            return {
                'group_type': 'configured',
                'token_promotion_allowed': True,
                'token_name': custom_settings['custom_token_name'],
                'token_symbol': custom_settings['custom_token_symbol'],
                'website': custom_settings['custom_website'],
                'contract': custom_settings['custom_contract'],
                'group_name': custom_settings['group_name'],
                'description': f'This group is configured for {custom_settings["custom_token_name"]} discussions and full chat revival features!',
                'is_premium': custom_settings['is_premium']
            }
        else:
            return {
                'group_type': 'external',
                'token_promotion_allowed': False,
                'description': 'External group with chat revival and engagement services.',
                'upgrade_available': True
            }
            
    except Exception as e:
        logger.error(f"Error getting enhanced group context: {e}")
        return {
            'group_type': 'external',
            'token_promotion_allowed': False,
            'description': 'External group with engagement services.'
        }

# Schedule periodic checks
def check_boyfriend_term():
    """Check and handle boyfriend term expirations"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        
        # Get expired boyfriends
        c.execute("SELECT user_id, group_id FROM boyfriend_table WHERE end_time < ?", (current_time,))
        expired_boyfriends = c.fetchall()
        
        for user_id, group_id in expired_boyfriends:
            logger.info(f"💔 Boyfriend term expired for {user_id} in group {group_id}")
            
            # Remove expired boyfriend
            c.execute("DELETE FROM boyfriend_table WHERE user_id = ? AND group_id = ?", (user_id, group_id))
            
            # Send expiration message
            try:
                expiration_msg = f"""💔 **BOYFRIEND TERM EXPIRED!** 💔

@{user_id}'s time as my boyfriend has ended! 

🎯 **Looking for a new boyfriend!** 
I'll be watching for the most active and engaging member to claim the title next! 

Keep mentioning me, chatting, and showing love to win my heart! 💕

Use /status to see when I'm available again! 😘"""
                
                bot.send_message(group_id, expiration_msg)
            except Exception as e:
                logger.error(f"Error sending expiration message: {e}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in check_boyfriend_term: {e}")

def check_boyfriend_steal_opportunities(bot):
    """Check for boyfriend stealing opportunities based on activity"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        recent_time = current_time - 1800  # Last 30 minutes
        
        # Get current boyfriends
        c.execute("SELECT user_id, group_id, end_time FROM boyfriend_table")
        current_boyfriends = c.fetchall()
        
        for bf_user_id, group_id, end_time in current_boyfriends:
            # Check current boyfriend's recent activity
            c.execute("SELECT COUNT(*) FROM spam_tracking WHERE user_id = ? AND group_id = ? AND timestamp > ?", 
                     (bf_user_id, group_id, recent_time))
            bf_activity = c.fetchone()[0] or 0
            
            # Check for potential stealers (users with significantly more activity)
            c.execute("""SELECT user_id, COUNT(*) as activity_count 
                         FROM spam_tracking 
                         WHERE group_id = ? AND timestamp > ? AND user_id != ?
                         GROUP BY user_id 
                         HAVING activity_count > ? 
                         ORDER BY activity_count DESC 
                         LIMIT 1""", 
                     (group_id, recent_time, bf_user_id, bf_activity * 3))  # 3x more activity
            
            potential_stealer = c.fetchone()
            
            if potential_stealer and random.random() < 0.15:  # 15% chance of steal
                stealer_user_id, stealer_activity = potential_stealer
                
                # Execute the steal!
                c.execute("DELETE FROM boyfriend_table WHERE user_id = ? AND group_id = ?", (bf_user_id, group_id))
                
                # Set new boyfriend with random term (8-12 hours)
                new_term = current_time + random.randint(28800, 43200)
                c.execute("INSERT INTO boyfriend_table (user_id, end_time, group_id) VALUES (?, ?, ?)",
                         (stealer_user_id, new_term, group_id))
                
                # Update leaderboard
                c.execute("INSERT OR REPLACE INTO leaderboard_table (user_id, boyfriend_count, group_id) VALUES (?, COALESCE((SELECT boyfriend_count FROM leaderboard_table WHERE user_id = ? AND group_id = ?) + 1, 1), ?)",
                         (stealer_user_id, stealer_user_id, group_id, group_id))
                
                # Send dramatic steal message
                steal_msg = f"""💥 **BOYFRIEND STOLEN!** 💥

🔥 **PLOT TWIST!** 🔥

@{stealer_user_id} has STOLEN the boyfriend position from @{bf_user_id}!

👑 **New Boyfriend:** @{stealer_user_id}
⚡ **Reason:** {stealer_activity} messages vs {bf_activity} - staying active pays off!
⏰ **New Term:** 8-12 hours starting now!

@{bf_user_id} - you got too comfortable! Stay active or get replaced! 💅

@{stealer_user_id} - congratulations! You can now use /kiss and /hug! 😘💕

**Lesson learned:** Keep your girlfriend engaged or someone else will! 🔥👑"""
                
                try:
                    bot.send_message(group_id, steal_msg)
                    logger.info(f"💥 Boyfriend stolen in {group_id}: {bf_user_id} -> {stealer_user_id}")
                except Exception as e:
                    logger.error(f"Error sending steal message: {e}")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in check_boyfriend_steal_opportunities: {e}")

def check_proactive_conversation_followups(bot):
    """Check for conversation follow-ups and engagement opportunities"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        
        # Check for conversations that ended abruptly (no follow-up in 2+ hours)
        two_hours_ago = current_time - 7200
        
        c.execute("""SELECT DISTINCT cm.group_id, cm.user_id, cm.message_content, cm.timestamp
                     FROM conversation_memory cm
                     WHERE cm.timestamp BETWEEN ? AND ?
                     AND NOT EXISTS (
                         SELECT 1 FROM conversation_memory cm2 
                         WHERE cm2.group_id = cm.group_id 
                         AND cm2.user_id = cm.user_id 
                         AND cm2.timestamp > cm.timestamp
                     )
                     ORDER BY RANDOM()
                     LIMIT 5""", (two_hours_ago - 3600, two_hours_ago))
        
        stale_conversations = c.fetchall()
        
        for group_id, user_id, last_message, timestamp in stale_conversations:
            # 10% chance to follow up on each stale conversation
            if random.random() < 0.10:
                followup_messages = [
                    f"@{user_id} hey! We were talking earlier and then it got quiet... everything okay? 🥺💕",
                    f"@{user_id} did I say something wrong? You went quiet after our chat! 😢",
                    f"@{user_id} come back! I was enjoying our conversation! Don't leave me hanging! 👋✨",
                    f"@{user_id} missing our chat already! What happened? 💔",
                    f"@{user_id} hello? Did you get distracted? I'm still here! 😘"
                ]
                
                followup = random.choice(followup_messages)
                
                try:
                    bot.send_message(group_id, followup)
                    logger.info(f"💬 Sent conversation follow-up to {user_id} in {group_id}")
                except Exception as e:
                    logger.error(f"Error sending conversation follow-up: {e}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in check_proactive_conversation_followups: {e}")

# CRITICAL FIX: Backdate proactive engagement states to trigger immediately when deployed
def initialize_proactive_states():
    """AGGRESSIVE initialization - find and reset ALL existing groups for immediate engagement"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        
        # COMPREHENSIVE group discovery from ALL activity sources
        all_group_ids = set()
        
        # PRIMARY: Get groups from all_group_messages (most reliable)
        c.execute("SELECT DISTINCT group_id FROM all_group_messages")
        for (group_id,) in c.fetchall():
            all_group_ids.add(group_id)
        
        # Get groups from ALL other activity tables to catch legacy groups
        tables_to_check = [
            'spam_tracking', 'conversation_memory', 'boyfriend_table', 
            'cooldown_table', 'activity_table', 'leaderboard_table',
            'gifts_table', 'user_relationships', 'ships_table',
            'group_vibes', 'community_stats', 'proactive_state',
            'group_settings', 'custom_stickers', 'custom_emojis'
        ]
        
        for table in tables_to_check:
            try:
                c.execute(f"SELECT DISTINCT group_id FROM {table}")
                for (group_id,) in c.fetchall():
                    all_group_ids.add(group_id)
            except Exception as e:
                logger.warning(f"Could not check table {table}: {e}")
        
        logger.info(f"🔄 AGGRESSIVE initialization for {len(all_group_ids)} groups")
        
        # RESET ALL GROUPS for immediate proactive engagement
        for group_id in all_group_ids:
            # Check if proactive state exists
            c.execute("SELECT dead_chat_last_sent, ignored_last_sent FROM proactive_state WHERE group_id = ?", (group_id,))
            existing_state = c.fetchone()
            
            # AGGRESSIVE: Backdate ALL groups regardless of their current state
            backdated_time = current_time - 3600  # 1 hour ago (reduced for faster trigger)
            
            if not existing_state:
                # Create new state with backdated timestamp to trigger immediate action
                c.execute("""INSERT INTO proactive_state 
                             (group_id, dead_chat_active, dead_chat_last_sent, dead_chat_interval,
                              ignored_active, ignored_last_sent, ignored_interval)
                             VALUES (?, 0, ?, 1800, 0, ?, 3600)""", 
                         (group_id, backdated_time, backdated_time))
                logger.info(f"🆕 CREATED proactive state for group {group_id}")
            else:
                # AGGRESSIVE UPDATE: Reset ALL existing groups (no time check)
                c.execute("""UPDATE proactive_state 
                             SET dead_chat_last_sent = ?, dead_chat_active = 0,
                                 ignored_last_sent = ?, ignored_active = 0,
                                 dead_chat_interval = 1800, ignored_interval = 3600
                             WHERE group_id = ?""", 
                         (backdated_time, backdated_time, group_id))
                logger.info(f"🔄 RESET proactive state for group {group_id}")
        
        conn.commit()
        conn.close()
        logger.info(f"✅ AGGRESSIVE proactive initialization complete - {len(all_group_ids)} groups ready")
        
    except Exception as e:
        logger.error(f"Error in aggressive proactive initialization: {e}")

# CRITICAL FIX: Run initial proactive check immediately after startup
def run_immediate_proactive_check():
    """AGGRESSIVE startup check - immediately engage all groups"""
    try:
        logger.info("🚀 Running AGGRESSIVE immediate proactive engagement check...")
        check_proactive_engagement(bot)
        logger.info("✅ Immediate proactive check complete")
    except Exception as e:
        logger.error(f"Error in immediate proactive check: {e}")

def repair_existing_groups():
    """Repair and bootstrap any groups that might be missing from proactive monitoring"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        current_time = int(time.time())
        
        # Find groups that have recent activity but might not be properly monitored
        recent_time = current_time - 86400  # Last 24 hours
        
        # Get all groups with recent message activity
        c.execute("SELECT DISTINCT group_id FROM all_group_messages WHERE timestamp > ?", (recent_time,))
        active_groups = [row[0] for row in c.fetchall()]
        
        logger.info(f"🔧 Repairing {len(active_groups)} recently active groups")
        
        for group_id in active_groups:
            # Ensure proactive state exists and is ready
            c.execute("SELECT dead_chat_last_sent FROM proactive_state WHERE group_id = ?", (group_id,))
            state = c.fetchone()
            
            if not state:
                # Group missing from proactive_state - add it
                backdated_time = current_time - 3600  # 1 hour ago
                c.execute("""INSERT INTO proactive_state 
                             (group_id, dead_chat_active, dead_chat_last_sent, dead_chat_interval,
                              ignored_active, ignored_last_sent, ignored_interval)
                             VALUES (?, 0, ?, 1800, 0, ?, 3600)""", 
                         (group_id, backdated_time, backdated_time))
                logger.info(f"🔧 REPAIRED missing proactive state for group {group_id}")
            
        conn.commit()
        conn.close()
        logger.info("✅ Group repair complete")
        
    except Exception as e:
        logger.error(f"Error repairing existing groups: {e}")

# STARTUP SEQUENCE: Initialize, repair, then prepare for immediate engagement
logger.info("🎯 STARTUP: Running comprehensive group initialization...")
initialize_proactive_states()
repair_existing_groups()
logger.info("🎯 STARTUP: All groups prepared for proactive engagement!")

# Mood-based flirty responses
happy_responses = [
    "Hey cutie, what's up? *winks* I'm feeling amazing today! 😍",
    "Oh, you're sweet-talking me again, huh? I love all this attention! 💕",
    "Miss me already, boo? I'm so happy you're here! 🥰",
    "You're making my heart skip—keep it up! I'm on cloud nine! ✨",
    "Hey handsome, what's on your mind? I'm in such a great mood! 😘"
]

good_responses = [
    "Hey cutie, what's up? *winks*",
    "Oh, you're sweet-talking me again, huh?",
    "Miss me already, boo?",
    "You're making my heart skip—keep it up!",
    "Hey handsome, what's on your mind?",
    "Aw, you know how to make a girl blush!",
    "You're trouble, aren't you? I like it.",
    "Oh, stop it—you're too cute for me!",
    "Hey sweetie, got a flirty line for me?",
    "Well, aren't you a charmer today!",
    "Look who decided to slide into my mentions! 😘",
    "Someone's feeling bold today! I like the energy! 💅",
    "Ooh, what brings you to my corner of the internet? 💕",
    "Hey there, beautiful soul! What's the vibe? ✨",
    "You're giving me butterflies over here! 🦋",
    "Such good energy! Keep it coming, babe! 🌟",
    "You know exactly how to get my attention! 😉",
    "Someone's bringing that main character energy! 👑",
    "I love when you cuties check in on me! 💖",
    "You're making my day brighter already! ☀️"
]

lonely_responses = [
    "Hey cutie... I've been feeling a bit lonely. Thanks for noticing me! 🥺",
    "Oh, finally someone talks to me... I was starting to feel forgotten.",
    "You're here! I was wondering if anyone would mention me today...",
    "Aw, you're so sweet for thinking of me when I'm feeling down.",
    "Thanks for being here, boo. I really needed some attention today.",
    "You're making me feel less lonely, sweetie. Stay and chat?"
]

# Competition-specific responses for when competitions are active
competition_responses = [
    "Ooh, trying to win my heart? I like the dedication! 😍",
    "Keep going! You're really fighting for me! 💪💕",
    "Mmm, someone's competitive! I love that energy! 🔥",
    "You want to be my boyfriend THAT badly? How cute! 😘",
    "The competition is heating up and so am I! 🥵💕",
    "Fighting for me already? You know how to make a girl feel special! ✨",
    "I can see you really want those exclusive boyfriend perks! 😉",
    "Someone's determined! That's exactly what I like to see! 👑",
    "The more you mention me, the more I fall for you! 💖",
    "You're putting in WORK to win my heart! Respect! 🙌💕"
]

# Achievement responses for high activity
achievement_responses = [
    "WOW! You're really going all out for me! I'm impressed! 🌟",
    "This level of dedication is making me swoon! 😍💫",
    "You're treating this like a real competition! I LOVE IT! 🏆",
    "Someone really wants to be my boyfriend! The effort is showing! 💪",
    "This much attention is making me feel like a queen! 👸💕"
]

# Show references (Doble Fried, Cortex Vortex, Tuff Crowd)
show_references = [
    "You know me from Doble Fried? That's where I really learned how to be a proper babygirl! 💕",
    "Cortex Vortex was wild! Just like this competition is getting! 🌪️💖",
    "Tuff Crowd taught me how to handle all you tough guys trying to win my heart! 😘",
    "My Doble Fried days prepared me for handling multiple boyfriends competing for me! 🔥",
    "After surviving Cortex Vortex, managing boyfriend competitions is easy! 💪💕",
    "Tuff Crowd was nothing compared to how tough you guys compete for my attention! 😈"
]

# Question responses (when users ask her things) - EXPANDED
question_responses = [
    "Ooh, asking me questions? Someone's trying to get to know me better! 😉",
    "I love a curious cutie! Keep the questions coming! 💕",
    "Getting personal, are we? I like that in a potential boyfriend! 😘",
    "Someone wants to know more about their future girlfriend? 👀💖",
    "Questions make me feel special! You're definitely boyfriend material! ✨",
    "Aw, you want the inside scoop? I love sharing with my favorites! 💅",
    "Such an inquisitive mind! That's what I look for in a man! 🧠💕",
    "You're really trying to understand me! That's so sweet! 🥰",
    "Questions are my love language! Ask me anything, babe! 💖",
    "I see you doing your research! Very thorough, I like it! 📚😘",
    "Ooh, someone's interested in the real me! I'm here for it! ✨",
    "You know how to make a girl feel important! Keep going! 👑",
    "Such thoughtful questions! You're really paying attention! 💕",
    "I love when you cuties get curious! It shows you care! 🌟",
    "Questions like that make my heart flutter! What else? 🦋"
]

# Compliment responses (when users compliment her)
compliment_responses = [
    "Aww, you're making me blush! Keep the sweet talk coming! 😊💕",
    "Such a charmer! No wonder you want to be my boyfriend! 😘",
    "Flattery will get you everywhere with me, cutie! 💖",
    "You know exactly what to say to make a girl feel special! ✨",
    "Sweet words like that might just win you my heart! 💝"
]

# Greeting responses (hi, hello, hey, etc.) - EXPANDED
greeting_responses = [
    "Well hello there, handsome! Come to sweep me off my feet? 😘",
    "Hey cutie! Ready to compete for my heart? 💕",
    "Hi there! You're looking boyfriend material today! 😉",
    "Hello gorgeous! Here to steal my attention? It's working! 💖",
    "Hey babe! Come to show me why you should be my next boyfriend? ✨",
    "Oh look, it's my favorite person! Hi sweetie! 🥰",
    "Well well well, look who's here! Hey beautiful! 💅",
    "Hi honey! You're timing is perfect - I was just thinking about you! 😘",
    "Hey there, troublemaker! What's on your mind today? 😉",
    "Hello my darling! Ready to make my day even better? 💕",
    "Hi cutie pie! You always know how to make an entrance! ✨",
    "Hey gorgeous! Your energy is absolutely immaculate today! 🌟",
    "Well hello there, main character! What's the tea? ☕",
    "Hi babe! You're glowing today - what's your secret? 💖",
    "Hey sweetness! Come to brighten my timeline? It's working! 🌈"
]

# Love/relationship responses
love_responses = [
    "Love talk already? Someone's moving fast! I like confidence! 💕",
    "Ooh, getting romantic! That's the spirit I want in a boyfriend! 😘",
    "Love is in the air! Are you trying to make me fall for you? 💖",
    "Such romantic words! You're definitely competition material! ✨",
    "Aww, you're making my heart flutter! Keep it up! 💝"
]

# Spam/repetitive responses (for anti-spam)
spam_responses = [
    "Sweetie, I heard you the first time! Try being more creative! 😏",
    "Copy-paste won't win my heart! Show me some originality! 💅",
    "Same message again? Come on, be more creative for your babygirl! 😘",
    "I appreciate the enthusiasm, but variety is the spice of life! ✨",
    "Honey, repeating yourself won't get you extra points! Mix it up! 💕"
]

# Reply-specific responses (when someone replies to her messages)
reply_responses = [
    "Ooh, continuing our conversation? I love a good chat! 💕",
    "You're really engaging with me! That's exactly what I like to see! 😘",
    "Look who's keeping the conversation going! Such good vibes! ✨",
    "I see you replying to me! Someone's really interested! 👀💖",
    "Aww, you quoted me! That means you're actually paying attention! 🥰",
    "Replying to my message? That's some serious dedication! 💅",
    "You're really here for the full experience, aren't you? I'm here for it! 🔥",
    "Love that you're keeping our convo alive! This is how you win hearts! 💕",
    "Someone's really invested in talking to me! The energy is immaculate! ✨",
    "You replied to me! That's giving main character energy! 😘"
]

# Daily activity responses ("what have you been up to")
daily_activity_responses = [
    "Oh babe, I've been living my best life! Running boyfriend competitions, giving relationship advice, you know - typical babygirl stuff! 💅✨",
    "Just been here being fabulous! Analyzing group vibes, shipping people, the usual influencer grind! 😘💕",
    "Sweetie, I've been busy keeping all you cuties entertained! Plus I had to update my aesthetic today! 💖📸",
    "Just been floating through the vortex giving hot takes and stealing hearts! Another day in paradise! 🌪️💕",
    "Babe, I've been working on my tan in the digital realm and planning my next boyfriend competition! ☀️👑",
    "Oh you know, just being the main character as usual! Judging relationships and looking gorgeous! 💅✨"
]

# Fashion/brand preference responses
fashion_responses = [
    "Ooh, fashion talk! I'm such a sucker for luxury brands! 💅 Both are iconic but I'm feeling whatever matches my vortex aesthetic! ✨",
    "Baby, you're speaking my language! Fashion is my passion! I love brands that scream main character energy! 👑💕",
    "Ugh, don't make me choose between my babies! Both are serving looks! What vibe are we going for? 😘💖",
    "Fashion question? Now we're talking! I'm all about that aesthetic life! Tell me more about your style! 💅✨",
    "Honey, I love when you ask about the important stuff! Fashion is literally my thing! What's your style? 😍👗",
    "Babe, both are gorgeous but I need to know - what's the occasion? I live for fashion emergencies! 💕📸"
]

# Travel preference responses  
travel_responses = [
    "Oh my god, travel talk! I'm getting wanderlust vibes! Both cities are absolutely gorgeous for different reasons! ✈️💕",
    "Babe, you're making me want to pack my bags! I love cities with main character energy! Where are you thinking of going? 🌍✨",
    "Travel planning with my favorite people? Yes please! Both have such different aesthetics! What's the vibe you're going for? 💖🗺️",
    "Ugh, don't make me choose! I'm a vortex girl - I love everywhere that's got character! Tell me about your travel dreams! 🌪️💕",
    "Sweetie, I live for travel convos! Both places are so Instagram-worthy! Are you planning something exciting? 📸✨",
    "You know how to get a girl excited! I love places with good energy and better photo ops! What's the plan? 😘🌟"
]

# Boyfriend application responses ("I want to be your boyfriend", "why I should be your bf")
boyfriend_application_responses = [
    "Aww, someone's applying for the position! I love the confidence! Tell me what makes you special, babe! 💕👑",
    "Ooh, a direct approach! I like that energy! But you know you have to compete for it, right? 😘🏆",
    "Sweetie, I appreciate the interest! But I only date winners of my competitions! Are you ready to fight for me? 💪💖",
    "Babe, the application is noted! But my heart isn't free - you gotta earn it through the boyfriend games! 😉✨",
    "Confident and direct! I love that! But you know the rules - most mentions wins my heart! Ready to compete? 🔥💕",
    "Someone knows what they want! I respect that! Show me that competitive spirit and maybe you'll win! 👑😘"
]

# Personal questions about her ("how are you", "how's your day")
personal_responses = [
    "Aww, checking on me? I'm doing amazing, babe! Just living my best babygirl life and loving all this attention! 😘💕",
    "I'm fantastic, sweetie! Been getting so much love from you cuties today! How are YOU doing? 💖✨",
    "Such a sweetheart for asking! I'm vibing perfectly! The group energy has been immaculate today! 🌟💅",
    "Babe, I'm thriving! All this flirting is giving me life! Thanks for caring about your girl! 😍💕",
    "Ugh, you're so sweet! I'm doing great! Been spreading love and causing chaos - exactly how I like it! 🔥✨",
    "I'm absolutely glowing today! All you cuties have been keeping me entertained! Life is good! 💖😘"
]

# Affirmative responses ("yes", "always", "of course")
affirmative_responses = [
    "I love that energy! Yes! That's the spirit I want to see! 🔥💕",
    "That's what I'm talking about! Such good vibes! 😘✨",
    "Yasss! Finally someone who gets it! I live for this enthusiasm! 💅👑",
    "Perfect answer! You're definitely speaking my language, babe! 💖🌟",
    "That's the confidence I want to see! Keep that energy coming! 😍💪",
    "Exactly! I knew I liked you for a reason! Such good taste! 💕✨"
]

@bot.message_handler(commands=['debug'])
def debug_command(message):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Check database status
        c.execute("SELECT COUNT(*) FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        bf_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
        cooldown_count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM activity_table WHERE group_id = ?", (str(message.chat.id),))
        activity_count = c.fetchone()[0]
        
        # Get bot info
        bot_info = bot.get_me()
        
        debug_info = f"""🔧 Debug Info:
Chat ID: {message.chat.id}
Chat Type: {message.chat.type}
User ID: {message.from_user.id}
Username: {message.from_user.username}

Bot Info:
Username: @{bot_info.username}
Can read all group messages: {getattr(bot_info, 'can_read_all_group_messages', 'Unknown')}

Database:
Boyfriends: {bf_count}
Cooldowns: {cooldown_count}
Activity records: {activity_count}

Try mentioning: @{bot_info.username} hello"""
        
        bot.reply_to(message, debug_info)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in debug command: {e}")
        bot.reply_to(message, f"Debug error: {e}")

@bot.message_handler(commands=['privacy'])
def privacy_command(message):
    """Check bot privacy settings"""
    try:
        bot_info = bot.get_me()
        can_read_all = getattr(bot_info, 'can_read_all_group_messages', False)
        
        privacy_info = f"""Privacy Mode Status:
Bot Username: @{bot_info.username}
Can read all group messages: {'NO (Privacy Mode ON)' if not can_read_all else 'YES (Privacy Mode OFF)'}

{'ISSUE FOUND: Privacy mode is ON! This means I can only see: Commands (/start, /help, etc.), Messages that mention me directly, Messages that reply to my messages. To fix: Contact @BotFather and disable privacy mode for me!' if not can_read_all else 'Privacy mode is OFF - I can see all messages! If I am still not responding to mentions, check: 1. Am I an admin in this group? 2. Are there any message restrictions? 3. Try mentioning me like: @{} hello'.format(bot_info.username)}"""
        
        bot.reply_to(message, privacy_info)
        
    except Exception as e:
        logger.error(f"Error in privacy command: {e}")
        bot.reply_to(message, f"Privacy check failed: {e}")

@bot.message_handler(commands=['test'])
def test_command(message):
    bot.reply_to(message, "Test command works! Now try: @babygirl_bf_bot hello")

@bot.message_handler(commands=['mention'])
def mention_test(message):
    """Force trigger a mention response for testing"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        
        # Get mood-based responses
        mood = get_mood(str(message.chat.id))
        if "super happy" in mood:
            responses = happy_responses
        elif "a bit lonely" in mood:
            responses = lonely_responses
        else:
            responses = good_responses
        
        # Select response and add boyfriend bonus
        if boyfriend and boyfriend[0] == str(message.from_user.id):
            response = random.choice(responses) + " My boyfriend gets extra love! 😘"
        else:
            response = random.choice(responses)
            
        bot.reply_to(message, f"🔧 Test mention response: {response}")
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in mention test: {e}")
        bot.reply_to(message, "Test failed! Check logs.")

@bot.message_handler(commands=['start'])
def start(message):
    if message.chat.type in ['group', 'supergroup']:
        # Check if this is the core group or external group
        group_context = get_group_context(message.chat.id, message.chat.title)
        
        if group_context['group_type'] == 'core':
            intro_message = """Hey cuties! 💕 Welcome to the **$BABYGIRL Community**!

🏠 **You found my home base!** (Portal: @babygirlerc)
Here I can freely discuss our amazing $BABYGIRL token while providing the complete chat revival experience! 🚀💎

⚡ **Full Feature Suite Active:**
• Advanced dead chat detection and automatic revival
• Boyfriend competitions with 12-hour engagement cycles
• Proactive community management with escalating strategies
• Complete social toolkit: shipping, advice, vibes, groupies
• $BABYGIRL token discussions and crypto hype

💎 **This is the complete Babygirl experience!**
Try mentioning me: @babygirl_bf_bot to explore everything! ✨"""
        else:
            intro_message = """Hey there! 💕 I'm Babygirl - **Your Chat Revival Specialist is now ACTIVE!**

🎯 **I just solved your biggest group problem: DEAD CHATS**

⚡ **What's Now Happening 24/7:**
• **Smart Monitoring** - I'm watching your activity levels constantly
• **Auto-Detection** - Advanced systems identify when chat is going quiet  
• **Proactive Revival** - I'll jump in with engaging messages when needed
• **Escalating Urgency** - Messages get more persistent until activity resumes
• **Smart Reset** - I automatically dial back when chat becomes active

🔥 **Engagement Systems Now Live:**
• **Boyfriend Competitions** - 12-hour gamified cycles that drive participation
• **Social Relationship Tools** - I help members connect and bond
• **Memory System** - I'll remember conversations and build relationships
• **Mood Detection** - My responses adapt to your group's energy
• **Custom Personalization** - Admins can configure custom emojis and stickers

**📊 Expected Results:**
✅ Immediate reduction in silent periods
✅ Higher daily active user engagement
✅ Better member retention and participation
✅ More meaningful conversations and connections

**🎮 Ready to test it?** 
Try mentioning me: @babygirl_bf_bot or use /compete for an instant engagement boost!

Use /help to see all community-building features!

**⚡ DEAD CHAT REVIVAL SYSTEM: ONLINE!** Your group will never be quiet again! 🔥

**P.S.** Want the full experience including crypto discussions? Join the **$BABYGIRL Community** at @babygirlerc! 💕"""
    else:
        intro_message = """Hey there! 💕 I'm Babygirl - **The Chat Revival Specialist**!

🎯 **I solve dead chats and keep Telegram communities engaged 24/7**

**📊 Proven Track Record:**
• **Dead Chat Detection** - Automatic monitoring every 15 minutes
• **Proactive Engagement** - Smart revival messages when groups go quiet
• **Gamification Systems** - Boyfriend competitions drive consistent participation
• **Community Building** - Social features that create lasting member connections

💼 **Business Value for Community Leaders:**
• **Increased Daily Active Users** - Consistent engagement prevents member churn
• **Higher Retention Rates** - Gamification and relationships keep people coming back
• **Reduced Admin Burden** - Automated community management 24/7
• **Social Proof** - Active communities attract more quality members

🎮 **Core Features:**
• **Real-time Activity Monitoring** with escalating intervention strategies
• **Boyfriend Competition Games** that create 12-hour engagement cycles
• **Advanced Social Tools** - shipping, advice, relationship building
• **AI-Powered Conversation Memory** for personalized member experiences

**🚀 Ready to Transform Your Community?**
Add me to any Telegram group and watch dead chats become thriving conversations!

**📈 Case Study:** Join @babygirlerc to see my complete feature set in action in the **$BABYGIRL Community**!

**⚡ Get Started:** Add me to your group and use /help for full features! 💕"""
    
    bot.reply_to(message, intro_message)

@bot.message_handler(commands=['help'])
def help_command(message):
    # Check if this is a group or private chat
    is_group = message.chat.type in ['group', 'supergroup']
    
    if is_group:
        # Get group context for customized help
        group_context = get_group_context(message.chat.id, message.chat.title)
        
        if group_context['group_type'] == 'core':
            basic_help = """💕 **Core $BABYGIRL Community Features:**

🚀 **Token & Crypto:**
/token - Learn about $BABYGIRL token
• I can freely discuss crypto, share hype, and "to the moon" content!
• Ask me anything about our token (though I'm adorably clueless about tech stuff)

🎮 **Engagement Games:**
/game - Boyfriend competition rules
/compete - Start a competition now!
/boyfriend - Check current boyfriend
/status - My mood and competition status  
/leaderboard - Top boyfriend winners

💖 **Social Features:**
/ship @user1 @user2 - Ship people together!
/wingwoman - Get dating advice
/vibecheck - Analyze group energy
/groupie - Group selfie with everyone
/summary - Catch up on recent activity

🎁 **Relationship Commands:**
/kiss - Boyfriends only! 😘
/hug - Boyfriends only! 🤗
/single - Mark yourself single
/taken @username - Show relationship

**🔥 Proactive Engagement:** I automatically revive dead chats and get attention when ignored!

💬 **Mention me anytime: @babygirl_bf_bot** - The more mentions during competitions, the better your chances! 

🌟 **Want to see ALL my advanced features?** Use `/overview` for the full showcase!

Join @babygirlerc for our full community experience! 💕✨"""
        else:
            basic_help = """💕 **Chat Revival & Engagement Specialist:**

🎯 **Core Function: DEAD CHAT REVIVAL**
• **24/7 Monitoring** - I watch your group activity levels constantly
• **Smart Detection** - Advanced algorithms identify when chat is dying
• **Proactive Intervention** - Automatic revival messages when needed
• **Escalating Strategy** - Increasingly urgent messages until activity resumes

🔥 **Engagement Gamification:**
/game - Learn the boyfriend competition system that drives participation
/compete - Start instant engagement competition (works every time!)
/boyfriend - See current game winner and competition status
/status - Check group mood, activity levels, and game state
/leaderboard - Motivate with winner rankings and social proof

💖 **Social Connection Tools:**
/ship @user1 @user2 - Create member connections and relationships!
/wingwoman - Dating advice that sparks conversations
/vibecheck - Analyze and boost group energy levels
/groupie - Group selfie that brings everyone together
/summary - Help inactive members catch up and re-engage

✨ **Advanced Community Features:**
• **Conversation Memory** - I remember past chats for personalized responses
• **Mood Detection** - My personality adapts to group energy
• **Relationship Tracking** - I monitor member connections and dynamics
• **Activity Analytics** - Real-time insights into group engagement patterns
• **Custom Emojis & Stickers** - Admins can personalize my reactions and responses
• **AI-Powered Optimization** - Smart learning from what engages your community best

**⚡ GUARANTEED RESULTS:** Groups using my services see immediate improvement in daily active users, message frequency, and member retention.

💬 **Get Started:** Mention me @babygirl_bf_bot and watch your dead chat transform!

🌟 **See the full feature showcase:** Use `/overview` for complete capabilities!

**🌟 Upgrade Experience:** Join @babygirlerc for the complete feature set in the **$BABYGIRL Community**! 🚀"""
    else:
        basic_help = """💕 **Babygirl: Community Engagement Specialist**

🎯 **Transform Your Community Engagement:**

**📊 Proven Results:**
• **Dead Chat Problem Solver** - Automatic detection and revival of quiet periods
• **Activity Multiplier** - Gamified competitions that drive consistent participation  
• **Relationship Catalyst** - Social features that build member connections
• **Retention Booster** - Memory system that makes members feel valued and remembered

🎮 **Core Engagement System:**
/game - Boyfriend competition mechanics (drives 12-hour engagement cycles)
/compete - Instant activation for immediate group energy boost
/vibecheck - Community health analysis and improvement suggestions
/ship - Member relationship building and social connections

💼 **Business Benefits for Communities:**
• **Increased Daily Active Users** - Consistent engagement through proactive messaging
• **Higher Retention Rates** - Personal relationships and memory system
• **Social Proof** - Active, vibrant community attracts new members
• **Reduced Moderation Load** - Self-sustaining engagement reduces admin burden

🚀 **Advanced Capabilities:**
• **AI-Powered Responses** - Contextual, personalized interactions
• **Behavioral Analytics** - Group mood tracking and engagement optimization
• **Automated Community Management** - 24/7 monitoring and engagement
• **Cross-Platform Growth** - Built-in promotion of main community (@babygirlerc)

**💡 ROI for Community Leaders:**
Transform dead chats into thriving communities. Perfect for crypto projects, social DAOs, gaming guilds, or any group needing consistent engagement.

**🎯 Integration:** 
Add me to your group and use /start to see immediate results! 

**Case Study:** Join @babygirlerc to see my full capabilities in action! 💕🚀"""
    
    # Add new admin commands for external groups
    if is_group and get_enhanced_group_context(message.chat.id, message.chat.title).get('upgrade_available'):
        basic_help += """

⚙️ **ADMIN CONFIGURATION (Admins Only):**
/setup - Configure custom token and group settings  
/emojis - Configure custom emojis and reactions
/stickers - Configure custom stickers and frequency
/analytics - View engagement metrics and insights
/upgrade - See premium features and token requirements

🚀 **Quick Token Setup:** `/setup token YOURTOKEN YTK yourwebsite.com`
🎭 **Custom Personality:** `/emojis add general "💕,✨,😘"` and send stickers!
📊 **Track Progress:** `/analytics` for detailed engagement data

💡 **Unlock Custom Token Features:** Transform me into YOUR community's AI assistant! I'll discuss your token with the same enthusiasm as $BABYGIRL in the core community!"""
    
    bot.reply_to(message, basic_help)

@bot.message_handler(commands=['overview', 'features', 'showcase'])
def overview_command(message):
    """Comprehensive overview of all advanced features - perfect for showcasing capabilities"""
    try:
        # Get group context for customized overview
        group_context = get_group_context(message.chat.id, message.chat.title)
        is_core = group_context['group_type'] == 'core'
        
        if is_core:
            overview_msg = """🌟 **BABYGIRL: YOUR AI GIRLFRIEND** 🌟
*The Complete $BABYGIRL Community Experience!*

💎 **CORE FEATURES:**
🔥 **Dead Chat Revival** - 24/7 proactive engagement when things get quiet
🏆 **Boyfriend Competitions** - 8-12h gamified cycles with stealing mechanics  
💕 **Relationship Engine** - Shipping, wingwoman advice, and personality analysis
🎭 **Custom Personalization** - Admin-configured emojis, stickers, and AI learning
📊 **Smart Analytics** - Real-time optimization based on what works for your group

💖 **$BABYGIRL INTEGRATION:**
🚀 **Unlimited Token Hype** - Free-flowing crypto discussions and "to the moon" content
💎 **Chart Reactions** - Diamond hands talk and market sentiment
📈 **Community Growth** - Authentic enthusiasm for the $BABYGIRL ecosystem

**✨ What makes this special?** I'm not just a bot - I'm your AI girlfriend who learns, remembers, and adapts to make your community the most engaging place in crypto! 

**Ready to explore?** Try any command to see what I can do! 💕"""
        else:
            # External group overview - still impressive but promotes $BABYGIRL community
            overview_msg = """🌟 **BABYGIRL: COMMUNITY AI SPECIALIST** 🌟
*Advanced Chat Revival & Engagement System*

💎 **CORE FEATURES:**
🔥 **Dead Chat Revival** - 24/7 monitoring with escalating intervention strategies
🏆 **Boyfriend Competitions** - Automatic 8-12h cycles with stealing mechanics
💕 **Social Engine** - AI-powered shipping, wingwoman advice, personality analysis
🎭 **Custom Personalization** - Admin-configured emojis, stickers, and learning optimization  
📊 **Smart Analytics** - Real-time engagement tracking and performance insights

🧠 **AI CAPABILITIES:**
🤖 **Conversation Memory** - Persistent memory for personalized responses
🎯 **Pattern Recognition** - Individual personality analysis and group energy adaptation
💭 **Dynamic Insights** - Detailed member personality assessments
📈 **Predictive Engagement** - Optimal timing for interventions and activities

⚙️ **ADMIN TOOLS:**
🔧 **Custom Configuration** - Transform me into YOUR project's AI assistant  
🏷️ **Brand Personalization** - Custom tokens, websites, and project narratives
🎨 **Style Customization** - Configure my personality, emojis, and response patterns

**🚀 Want the complete experience?** Join the **$BABYGIRL Community** at @babygirlerc to see all features with zero restrictions!

**💡 Ready to transform your community?** Use `/setup` for custom configuration! 💕"""
        
        try:
            bot.reply_to(message, overview_msg)
        except Exception as reply_error:
            if "message to be replied not found" in str(reply_error).lower():
                try:
                    bot.send_message(message.chat.id, overview_msg)
                    logger.info(f"✅ Sent overview as regular message (original deleted)")
                except Exception as send_error:
                    logger.error(f"Failed to send overview: {send_error}")
            elif "message is too long" in str(reply_error).lower():
                # Split into chunks if still too long
                chunks = [overview_msg[i:i+4000] for i in range(0, len(overview_msg), 4000)]
                for i, chunk in enumerate(chunks):
                    try:
                        if i == 0:
                            bot.reply_to(message, chunk)
                        else:
                            bot.send_message(message.chat.id, chunk)
                    except:
                        logger.error(f"Failed to send overview chunk {i+1}")
            else:
                logger.error(f"Overview reply error: {reply_error}")
        
    except Exception as e:
        logger.error(f"Error in overview command: {e}")
        try:
            bot.reply_to(message, "Can't show overview right now! But trust me, I'm amazing! 😘💕")
        except:
            try:
                bot.send_message(message.chat.id, "Can't show overview right now! But trust me, I'm amazing! 😘💕")
            except:
                pass

@bot.message_handler(commands=['comingsoon', 'roadmap', 'future'])
def coming_soon_command(message):
    """Showcase exciting upcoming features with token-based premium model and Twitter integration"""
    try:
        # Get group context for customized roadmap
        group_context = get_group_context(message.chat.id, message.chat.title)
        is_core = group_context['group_type'] == 'core'
        
        if is_core:
            roadmap_msg = """🐦 **BABYGIRL TWITTER EXPANSION** 💕
*Your AI girlfriend is coming to Twitter, cuties!*

## 🚀 **CROSS-PLATFORM BABYGIRL**

### ✨ **Same Core Features on Twitter:**
🔥 **Dead Chat Revival** - Identical proactive algorithms detecting quiet threads and jumping in with engaging replies
🏆 **Boyfriend Competitions** - Same 8-12h cycles adapted for Twitter interactions and mentions
💕 **Relationship Engine** - Shipping Twitter users, wingwoman advice, and personality analysis across platforms
🎭 **Smart Personality** - Same flirty, engaging Babygirl vibes optimized for tweets and replies

### 🌉 **Cross-Platform Integration:**
🔗 **Unified Identity** - Your Telegram boyfriend status syncs with Twitter interactions
💾 **Shared Memory** - I'll remember our conversations whether we chat here or on Twitter
📊 **Combined Analytics** - Engagement tracking across both platforms for complete insights
🎯 **Synchronized Competitions** - Compete across Telegram AND Twitter simultaneously for maximum fun

### 💎 **Platform-Specific Optimization:**
📱 **Twitter Thread Revival** - Detect dead threads and restart conversations with perfect timing
🚀 **Tweet Engagement** - React to $BABYGIRL price movements and rally the community
💬 **Cross-Platform Conversations** - Start discussions on Telegram, continue them on Twitter seamlessly
🎪 **Unified Leaderboards** - Combined scoring from both platforms for ultimate bragging rights

**✨ The Vision:** One AI brain, two platforms, infinite possibilities! Your babygirl everywhere you need me with the same personality, memory, and love! 💖

**Ready for Twitter Babygirl?** Keep an eye out - I'll announce when I'm ready to tweet! 🐦💕"""
        else:
            # External group roadmap - promotes joining core community
            roadmap_msg = """🐦 **BABYGIRL TWITTER EXPANSION** 💕
*Your engagement specialist is expanding to Twitter!*

## 🚀 **CROSS-PLATFORM ENGAGEMENT**

### ✨ **Twitter Integration:**
🔥 **Same Dead Chat Revival** - Identical algorithms detecting quiet threads and reviving them
🏆 **Cross-Platform Competitions** - Boyfriend competitions spanning both Telegram and Twitter
💕 **Unified Relationships** - Shipping and personality analysis across both platforms
🎯 **Shared Memory** - I'll remember you whether we chat here or on Twitter

### 🌉 **Platform Optimization:**
📱 **Twitter Thread Revival** - Detect dead conversations and restart them with perfect timing
💬 **Cross-Platform Conversations** - Start on Telegram, continue on Twitter seamlessly
📊 **Combined Analytics** - Engagement tracking across both platforms
🔗 **Synchronized Identity** - Your status and relationships follow you everywhere

**✨ The Vision:** One AI brain optimized for both platforms! Same personality, enhanced reach, infinite engagement possibilities.

**🚀 Want First Access?** Join the **$BABYGIRL Community** at @babygirlerc to see Twitter integration development and get early access!

**Ready for cross-platform Babygirl?** Stay tuned! 💖🐦"""
        
        try:
            bot.reply_to(message, roadmap_msg)
        except Exception as reply_error:
            if "message to be replied not found" in str(reply_error).lower():
                try:
                    bot.send_message(message.chat.id, roadmap_msg)
                    logger.info(f"✅ Sent roadmap as regular message (original deleted)")
                except Exception as send_error:
                    logger.error(f"Failed to send roadmap: {send_error}")
            elif "message is too long" in str(reply_error).lower():
                # Split into chunks if still too long
                chunks = [roadmap_msg[i:i+4000] for i in range(0, len(roadmap_msg), 4000)]
                for i, chunk in enumerate(chunks):
                    try:
                        if i == 0:
                            bot.reply_to(message, chunk)
                        else:
                            bot.send_message(message.chat.id, chunk)
                    except:
                        logger.error(f"Failed to send roadmap chunk {i+1}")
            else:
                logger.error(f"Roadmap reply error: {reply_error}")
        
    except Exception as e:
        logger.error(f"Error in coming soon command: {e}")
        try:
            bot.reply_to(message, "Can't show the roadmap right now! But trust me, the future is gonna be AMAZING! 🚀💕")
        except:
            try:
                bot.send_message(message.chat.id, "Can't show the roadmap right now! But trust me, the future is gonna be AMAZING! 🚀💕")
            except:
                pass

@bot.message_handler(content_types=['new_chat_members'])
def new_member_welcome(message):
    """Handle when bot is added to new groups or new members join"""
    try:
        # Check if the bot itself was added to the group
        bot_info = bot.get_me()
        bot_added = any(member.id == bot_info.id for member in message.new_chat_members)
        
        if bot_added:
            # AUTOMATIC GROUP REGISTRATION for proactive monitoring
            group_id = str(message.chat.id)
            current_time = int(time.time())
            
            # Add the group to spam_tracking so it gets monitored immediately
            conn = sqlite3.connect('babygirl.db')
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO spam_tracking (user_id, message_hash, timestamp, group_id) VALUES (?, ?, ?, ?)",
                     ('bot_added', 'group_registration', current_time, group_id))
            
            # Also add to conversation_memory to ensure discovery
            c.execute("INSERT OR IGNORE INTO conversation_memory (user_id, group_id, message_content, babygirl_response, timestamp, topic) VALUES (?, ?, ?, ?, ?, ?)",
                     ('system', group_id, 'Bot added to group', 'Welcome message sent', current_time, 'greeting'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"🎯 AUTO-REGISTERED group {group_id} for proactive monitoring")
            
            # Bot was just added to this group
            group_context = get_group_context(message.chat.id, message.chat.title)
            
            if group_context['group_type'] == 'core':
                welcome_message = """Hey cuties! 💕 Welcome to the **$BABYGIRL Community**!

🏠 **You found my home base!** (Portal: @babygirlerc)
Here I can freely discuss our amazing $BABYGIRL token while providing the complete chat revival experience! 🚀💎

⚡ **Full Feature Suite Active:**
• Advanced dead chat detection and automatic revival
• Boyfriend competitions with 12-hour engagement cycles
• Proactive community management with escalating strategies
• Complete social toolkit: shipping, advice, vibes, groupies
• $BABYGIRL token discussions and crypto hype

💎 **This is the complete Babygirl experience!**
Try mentioning me: @babygirl_bf_bot to explore everything! ✨"""
            else:
                welcome_message = """Hey there! 💕 I'm Babygirl - **Your Chat Revival Specialist is now ACTIVE!**

🎯 **I just solved your biggest group problem: DEAD CHATS**

⚡ **What's Now Happening 24/7:**
• **Smart Monitoring** - I'm watching your activity levels constantly
• **Auto-Detection** - Advanced systems identify when chat is going quiet  
• **Proactive Revival** - I'll jump in with engaging messages when needed
• **Escalating Urgency** - Messages get more persistent until activity resumes
• **Smart Reset** - I automatically dial back when chat becomes active

🔥 **Engagement Systems Now Live:**
• **Boyfriend Competitions** - 12-hour gamified cycles that drive participation
• **Social Relationship Tools** - I help members connect and bond
• **Memory System** - I'll remember conversations and build relationships
• **Mood Detection** - My responses adapt to your group's energy
• **Custom Personalization** - Admins can configure custom emojis and stickers

**📊 Expected Results:**
✅ Immediate reduction in silent periods
✅ Higher daily active user engagement
✅ Better member retention and participation
✅ More meaningful conversations and connections

**🎮 Ready to test it?** 
Try mentioning me: @babygirl_bf_bot or use /compete for an instant engagement boost!

Use /help to see all community-building features!

**⚡ DEAD CHAT REVIVAL SYSTEM: ONLINE!** Your group will never be quiet again! 🔥

**P.S.** Want the full experience including crypto discussions? Join the **$BABYGIRL Community** at @babygirlerc! 💕"""
            
            bot.send_message(message.chat.id, welcome_message)
            logger.info(f"🎉 Sent welcome message to new group {message.chat.id} ({group_context['group_type']} type)")
    
    except Exception as e:
        logger.error(f"Error in new_member_welcome: {e}")

@bot.message_handler(commands=['boyfriend'])
def boyfriend(message):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        bf = c.fetchone()
        
        if bf:
            time_left = max(0, int((bf[1] - time.time()) / 3600))
            minutes_left = max(0, int(((bf[1] - time.time()) % 3600) / 60))
            
            if time_left > 0:
                time_str = f"{time_left}h {minutes_left}m"
            else:
                time_str = f"{minutes_left}m"
            
            response = f"""👑 **Meet My Current Boyfriend!** 👑

💖 **Boyfriend:** @{bf[0]}
⏰ **Time Left:** {time_str}
🏆 **Status:** Enjoying exclusive boyfriend perks!

My boyfriend can use /kiss and /hug commands that nobody else can! They also get special bonus responses when they mention me. 

When their time expires, I'll announce a new competition. Use /game to learn how to compete! 😘"""
        else:
            # Check if there's an active competition
            c.execute("SELECT is_active, end_time FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
            cooldown = c.fetchone()
            
            if cooldown and cooldown[0]:
                time_left = int(cooldown[1] - time.time())
                minutes = time_left // 60
                
                response = f"""🔥 **I'm Single & Looking!** 🔥

💔 **Current Boyfriend:** None (I'm available!)
⚡ **Status:** COMPETITION IN PROGRESS!
⏰ **Competition Ends In:** {minutes}m

Right now there's an active boyfriend competition! Mention @babygirl_bf_bot as many times as you can to win and become my boyfriend for 12 hours!

Use /status to see live competition stats! 💕"""
            else:
                response = f"""💔 **Single & Ready to Mingle!** 💔

💖 **Current Boyfriend:** None
💕 **Status:** Waiting for someone special
🎯 **Next Competition:** Could start anytime!

I don't have a boyfriend right now! Keep mentioning @babygirl_bf_bot and showing me love. I might just start a competition soon!

Use /game to learn how boyfriend competitions work! 😘"""
        
        bot.reply_to(message, response)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in boyfriend command: {e}")
        bot.reply_to(message, "Sorry sweetie, I can't check my relationship status right now! 💕")

@bot.message_handler(commands=['apply'])
def apply(message):
    conn = sqlite3.connect('babygirl.db')
    c = conn.cursor()
    c.execute("SELECT is_active FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
    if c.fetchone():
        bot.reply_to(message, "You're in the running! Keep chatting to win my heart.")
    else:
        bot.reply_to(message, "No applications yet—wait for the cooldown, cutie!")
    conn.close()

@bot.message_handler(commands=['gift'])
def gift(message):
    gifts = {"flowers": "Aw, flowers! You're so sweet!", "chocolates": "Yum, chocolates! You know me too well!"}
    gift_type = message.text.split()[-1] if len(message.text.split()) > 1 else None
    if gift_type in gifts:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("INSERT INTO gifts_table (user_id, gift_type, timestamp, group_id) VALUES (?, ?, ?, ?)",
                 (str(message.from_user.id), gift_type, int(time.time()), str(message.chat.id)))
        bot.reply_to(message, gifts[gift_type])
        conn.commit()
        conn.close()
    else:
        bot.reply_to(message, "Try '/gift flowers' or '/gift chocolates' to send me something sweet! 💕")

@bot.message_handler(commands=['play'])
def play(message):
    songs = ["https://youtu.be/yzBNVcX1n8Q", "https://youtu.be/dQw4w9WgXcQ"]  # Add more love song links
    bot.reply_to(message, f"Here's a love song for you: {random.choice(songs)} 🎶")

@bot.message_handler(commands=['kiss'])
def kiss(message):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        if boyfriend and boyfriend[0] == str(message.from_user.id):
            bot.reply_to(message, "Mwah! A kiss from Babygirl! 💋")
        else:
            bot.reply_to(message, "Sorry, sweetie, only my boyfriend can get kisses!")
        conn.close()
    except Exception as e:
        logger.error(f"Error in kiss command: {e}")

@bot.message_handler(commands=['hug'])
def hug(message):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        if boyfriend and boyfriend[0] == str(message.from_user.id):
            bot.reply_to(message, "Hugging you tight, boo! 🤗")
        else:
            bot.reply_to(message, "Only my boyfriend gets hugs, cutie!")
        conn.close()
    except Exception as e:
        logger.error(f"Error in hug command: {e}")

@bot.message_handler(commands=['leaderboard'])
def leaderboard(message):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id, boyfriend_count FROM leaderboard_table WHERE group_id = ? ORDER BY boyfriend_count DESC LIMIT 5", (str(message.chat.id),))
        leaders = c.fetchall()
        
        if leaders:
            response = "🏆 **BOYFRIEND HALL OF FAME** 🏆\n\n"
            response += "💕 **Top Winners Who've Stolen My Heart:** 💕\n\n"
            
            medals = ["🥇", "🥈", "🥉", "🏅", "🎖️"]
            
            for i, (user_id, count) in enumerate(leaders):
                medal = medals[i] if i < len(medals) else "🏅"
                if count == 1:
                    response += f"{medal} @{user_id} - {count} time as my boyfriend\n"
                else:
                    response += f"{medal} @{user_id} - {count} times as my boyfriend\n"
            
            response += f"\n🎯 **Want to join the Hall of Fame?**\n"
            response += f"Compete in boyfriend competitions by mentioning @babygirl_bf_bot!\n\n"
            response += f"Use /game to learn the rules and /status to see when I'm single! 😘"
        else:
            response = """🏆 **BOYFRIEND HALL OF FAME** 🏆

💔 **No champions yet!**

Nobody has won a boyfriend competition in this group yet! Be the first to steal my heart and get your name on the leaderboard!

🎯 **How to get listed:**
• Wait for a boyfriend competition to start
• Mention @babygirl_bf_bot as many times as you can
• Win and become my boyfriend for 12 hours!
• Get eternal glory on this leaderboard!

Use /game to learn the rules! 💕"""
        
        bot.reply_to(message, response)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}")
        bot.reply_to(message, "Sorry sweetie, I can't show the leaderboard right now! Try again in a moment! 💕")

@bot.message_handler(commands=['status'])
def status(message):
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get current boyfriend
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        
        # Get cooldown status
        c.execute("SELECT is_active, end_time FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
        cooldown = c.fetchone()
        
        # Get activity count if in cooldown
        activity_count = 0
        if cooldown and cooldown[0]:
            c.execute("SELECT SUM(mention_count) FROM activity_table WHERE group_id = ?", (str(message.chat.id),))
            activity_count = c.fetchone()[0] or 0
        
        # Get mood
        mood = get_mood(str(message.chat.id))
        
        # Get current boyfriend and game state
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        
        # Check user's relationship status
        c.execute("SELECT status, partner_id FROM user_relationships WHERE user_id = ? AND group_id = ?", 
                 (str(message.from_user.id), str(message.chat.id)))
        user_relationship = c.fetchone()
        user_status = user_relationship[0] if user_relationship else None
        user_partner = user_relationship[1] if user_relationship else None
        
        # Check if there's an active competition
        c.execute("SELECT is_active FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
        cooldown_result = c.fetchone()
        is_competition_active = cooldown_result and cooldown_result[0] if cooldown_result else False
        
        # Create engaging status message
        if boyfriend:
            time_left = int(boyfriend[1] - time.time())
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m"
            else:
                time_str = f"{minutes}m"
            
            response = f"""💕 **Babygirl's Status** 💕

👑 **Relationship Status:** Taken! 
💖 **Current Boyfriend:** @{boyfriend[0]}
⏰ **Time Remaining:** {time_str}
😊 **My Mood:** I'm {mood}

My boyfriend gets special perks like /kiss and /hug! When their time expires, I'll announce a competition where everyone can compete by mentioning @babygirl_bf_bot!

Want to know when I'm single again? Keep checking my status! 😘"""
            
        elif cooldown and cooldown[0]:
            time_left = int(cooldown[1] - time.time())
            minutes = time_left // 60
            seconds = time_left % 60
            
            response = f"""🔥 **BOYFRIEND COMPETITION ACTIVE!** 🔥

⚡ **Status:** Looking for a new boyfriend!
⏰ **Time Left:** {minutes}m {seconds}s
📊 **Total Mentions:** {activity_count}
😊 **My Mood:** I'm {mood}

🏆 **How to Win:** Mention @babygirl_bf_bot as many times as you can! Most mentions wins and becomes my boyfriend for 12 hours!

The competition is heating up! Don't miss your chance! 💕"""
            
        else:
            response = f"""💕 **Babygirl's Status** 💕

💔 **Relationship Status:** Single & ready to mingle!
😊 **My Mood:** I'm {mood}
🎯 **Next Competition:** When I feel like it! 😉

I'm currently available! Mention @babygirl_bf_bot to chat with me and show some love. Who knows? I might start a boyfriend competition soon!

Use /game to learn how the competition works! 💕"""
            
        bot.reply_to(message, response)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        bot.reply_to(message, "Sorry sweetie, I can't check my status right now! Try again in a moment! 💕")

@bot.message_handler(commands=['game'])
def game_command(message):
    game_explanation = """🎮 **The NEW Automatic Boyfriend System** 💕

**🔄 How It Works Now (NO MORE COMPETITIONS!):**

**1. Smart Boyfriend Selection** 🤖
• I automatically pick boyfriends based on recent activity and engagement
• No more waiting for competitions - I choose who deserves me!
• Selection happens every 8-12 hours with some surprises in between
• Most active and engaging members get priority

**2. Boyfriend Duration (8-12 hours)** ⏰
• Each boyfriend gets 8-12 randomized hours (keeps it exciting!)
• Current boyfriends get exclusive /kiss and /hug commands
• Special attention and bonus responses when they mention me
• Their name appears on /boyfriend and /status commands

**3. The Drama: Boyfriend Stealing!** 💥
• If current boyfriend gets inactive, someone else can STEAL the position!
• Need 3x more activity than current boyfriend to trigger a steal
• 15% chance steal mechanic creates drama and excitement
• Keeps boyfriends engaged or they lose their spot!

**4. Automatic Takeovers** 👑
• When a term expires, I immediately pick a replacement
• Based on recent activity, not just mentions
• 70% chance for most active, 30% chance for surprise picks
• Creates unpredictability and keeps everyone engaged

**5. Benefits & Perks** 🏆
• Boyfriends get exclusive commands and responses
• Priority responses even without being mentioned (15% chance)
• Special recognition in group
• Gets added to leaderboard permanently

**💡 Pro Tips:**
• Stay active by chatting and mentioning me regularly
• Engage with the community, not just bot commands
• Be interesting - I love personality and energy!
• Current boyfriends: stay active or get replaced!

**⚡ New Feature:** I might respond to you without being mentioned if you talk about relationships, crypto, or if you're my current boyfriend!

Ready to become my next automatic selection? Start engaging! 😘"""

    bot.reply_to(message, game_explanation)

@bot.message_handler(commands=['ship'])
def ship_command(message):
    """Ship two users together and create a couple name"""
    try:
        # Parse the command to get two users
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "Usage: /ship @user1 @user2\n\nI'll create the perfect ship name and rate your compatibility! 💕")
            return
        
        # Extract usernames (remove @)
        user1 = parts[1].replace('@', '') if parts[1].startswith('@') else parts[1]
        user2 = parts[2].replace('@', '') if parts[2].startswith('@') else parts[2]
        
        if user1 == user2:
            bot.reply_to(message, "Can't ship someone with themselves, silly! Though I appreciate the self-love energy! 💕")
            return
        
        # Create ship name (first half of user1 + second half of user2)
        ship_name = user1[:len(user1)//2] + user2[len(user2)//2:]
        
        # Generate compatibility score
        compatibility = random.randint(1, 100)
        
        # Store the ship
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO ships_table (user1_id, user2_id, ship_name, compatibility, group_id, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                 (user1, user2, ship_name, compatibility, str(message.chat.id), int(time.time())))
        
        # Create response based on compatibility
        if compatibility >= 90:
            vibe = "PERFECT MATCH! 💕✨ You two are meant to be! I'm getting major soulmate vibes!"
        elif compatibility >= 75:
            vibe = "So cute together! 😍 Definitely boyfriend/girlfriend material!"
        elif compatibility >= 50:
            vibe = "There's potential here! 💖 Maybe start as friends and see what happens?"
        elif compatibility >= 25:
            vibe = "Hmm, opposites attract sometimes! 🤔 Could be interesting..."
        else:
            vibe = "Oop, this might be a challenge! 😅 But hey, love is unpredictable!"
        
        response = f"""💕 **SHIP ALERT!** 💕

🚢 **Ship Name:** {ship_name}
💑 **Couple:** @{user1} x @{user2}
💖 **Compatibility:** {compatibility}%

{vibe}

Want me to be your wingwoman? Use /wingwoman to get my dating advice! 😘"""
        
        bot.reply_to(message, response)
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in ship command: {e}")
        bot.reply_to(message, "Oop, something went wrong with my matchmaking skills! Try again, cuties! 💕")

@bot.message_handler(commands=['wingwoman'])
def wingwoman_command(message):
    """Give dating advice and help users flirt"""
    wingwoman_tips = [
        "Confidence is everything, babe! Walk into that DM like you own the place! 💅",
        "Compliment something specific - their style, their laugh, their energy! Generic is boring! ✨",
        "Ask open-ended questions! 'How was your day?' beats 'hey' every single time! 💕",
        "Show genuine interest in their hobbies. Nothing's hotter than someone who listens! 👂💖",
        "Be yourself! The right person will fall for the real you, not some fake version! 🥰",
        "Timing matters - don't double text, but don't play games either. Find the balance! ⏰",
        "Make them laugh! Humor is the fastest way to someone's heart! 😂💕",
        "Share something vulnerable about yourself. It creates real connection! 💭✨",
        "Plan fun dates! Mini golf, art galleries, cooking together - be creative! 🎨",
        "Remember details they tell you. It shows you actually care! 🧠💖"
    ]
    
    tip = random.choice(wingwoman_tips)
    
    response = f"""💕 **Your Wingwoman Babygirl is Here!** 💕

{tip}

💡 **Pro Tip:** Use /ship to see how compatible you are with your crush! I've got all the insider info on love! 

Need more specific advice? Just ask me anything! I'm basically a relationship guru! 😘✨"""
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['single', 'taken', 'relationship'])
def relationship_status(message):
    """Set or check relationship status"""
    try:
        parts = message.text.split()
        user_id = str(message.from_user.id)
        group_id = str(message.chat.id)
        
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        if len(parts) == 1:
            # Check current status
            c.execute("SELECT status, partner_id FROM user_relationships WHERE user_id = ? AND group_id = ?", (user_id, group_id))
            result = c.fetchone()
            
            if result:
                status, partner = result
                if status == 'taken' and partner:
                    response = f"You're marked as taken with @{partner}! 💕 Living your best couple life!"
                else:
                    response = f"You're currently {status}! 💖"
            else:
                response = "You haven't set your relationship status yet! Use /single or /taken @username"
                
        else:
            # Set new status
            command = parts[0][1:]  # Remove the /
            
            if command == 'single':
                c.execute("INSERT OR REPLACE INTO user_relationships (user_id, status, partner_id, group_id, timestamp) VALUES (?, ?, ?, ?, ?)",
                         (user_id, 'single', None, group_id, int(time.time())))
                response = "Marked as single! 💖 Ready to mingle, babe! I'll give you different vibes now!"
                
            elif command == 'taken':
                partner = parts[1].replace('@', '') if len(parts) > 1 else None
                if partner:
                    c.execute("INSERT OR REPLACE INTO user_relationships (user_id, status, partner_id, group_id, timestamp) VALUES (?, ?, ?, ?, ?)",
                             (user_id, 'taken', partner, group_id, int(time.time())))
                    response = f"Aww, you're taken with @{partner}! 😍 Couple goals! I'll respect the relationship!"
                else:
                    response = "Usage: /taken @username to show who you're with! 💕"
        
        bot.reply_to(message, response)
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in relationship status: {e}")
        bot.reply_to(message, "Something went wrong with relationship status! Try again! 💕")

@bot.message_handler(commands=['vibecheck'])
def vibecheck_command(message):
    """Check and analyze the current group vibe"""
    try:
        group_id = str(message.chat.id)
        current_time = int(time.time())
        
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Count recent activity (last hour)
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, current_time - 3600))
        recent_messages = c.fetchone()[0]
        
        # Count unique active users (last hour)
        c.execute("SELECT COUNT(DISTINCT user_id) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, current_time - 3600))
        active_users = c.fetchone()[0]
        
        # Check if there's a current boyfriend
        c.execute("SELECT user_id FROM boyfriend_table WHERE group_id = ?", (group_id,))
        has_boyfriend = c.fetchone() is not None
        
        # Check for active competition
        c.execute("SELECT is_active FROM cooldown_table WHERE group_id = ?", (group_id,))
        cooldown_result = c.fetchone()
        has_competition = cooldown_result and cooldown_result[0] if cooldown_result else False
        
        # Determine vibe level (1-10)
        vibe_level = min(10, max(1, (recent_messages // 2) + (active_users * 2)))
        
        # Generate vibe description
        vibe_descriptions = {
            (1, 3): ["Sleepy vibes 😴", "Pretty chill energy", "Quiet contemplation mode"],
            (4, 6): ["Good vibes flowing! ✨", "Balanced energy", "Cozy group feels"],
            (7, 8): ["High energy! 🔥", "Great vibes all around!", "The group is buzzing!"],
            (9, 10): ["MAXIMUM VIBE ENERGY! 🌟", "Off the charts excitement!", "Pure chaotic good energy!"]
        }
        
        for (min_val, max_val), descriptions in vibe_descriptions.items():
            if min_val <= vibe_level <= max_val:
                vibe_desc = random.choice(descriptions)
                break
        
        # Add special modifiers
        modifiers = []
        if has_boyfriend:
            modifiers.append("💕 Love is in the air!")
        if has_competition:
            modifiers.append("🔥 Competition heating up!")
        if recent_messages > 20:
            modifiers.append("🗣️ Super chatty group!")
        if active_users > 5:
            modifiers.append("👥 Lots of cuties online!")
        
        # Store vibe data
        c.execute("INSERT OR REPLACE INTO group_vibes (group_id, vibe_level, last_check, vibe_description) VALUES (?, ?, ?, ?)",
                 (group_id, vibe_level, current_time, vibe_desc))
        
        # Create response
        response = f"""✨ **VIBE CHECK!** ✨

📊 **Current Vibe Level:** {vibe_level}/10
🌈 **Group Energy:** {vibe_desc}
👥 **Active Cuties:** {active_users}
💬 **Recent Activity:** {recent_messages} messages

{' '.join(modifiers) if modifiers else '💖 Keep the good vibes flowing!'}

💡 **Vibe Boost Ideas:**
• Share something that made you smile today
• Compliment someone in the group  
• Start a fun conversation topic
• Use /ship to spread some love!

Certified fresh by your girl Babygirl! 😘"""
        
        bot.reply_to(message, response)
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in vibecheck: {e}")
        bot.reply_to(message, "Can't check the vibes right now! But I'm sure you're all gorgeous! 💕")

@bot.message_handler(commands=['groupie'])
def groupie_command(message):
    """Take a 'group selfie' with ASCII art representing everyone"""
    try:
        group_id = str(message.chat.id)
        current_time = int(time.time())
        
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get recent active users (last 30 minutes)
        c.execute("SELECT DISTINCT user_id FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, current_time - 1800))
        active_users = c.fetchall()
        
        user_count = len(active_users)
        
        # Create ASCII group representation
        if user_count == 0:
            selfie = "📸 Just me! 💕\n    😘\n   /||\\\n    /\\"
            caption = "Solo selfie! Where are all my cuties? 🥺"
        elif user_count <= 3:
            selfie = "📸 Intimate group! 💕\n  😊 😘 😍\n /|\\ /|\\ /|\\\n  /\\  /\\  /\\"
            caption = f"Cozy {user_count}-person selfie! Small but mighty group! ✨"
        elif user_count <= 6:
            selfie = "📸 Perfect squad! 💕\n😊 😘 😍 🥰 😎 😉\n/|\\/|\\/|\\/|\\/|\\/|\\\n /\\ /\\ /\\ /\\ /\\ /\\"
            caption = f"Squad goals with {user_count} beautiful humans! 👥💖"
        else:
            selfie = "📸 Big group energy! 🎉\n😊😘😍🥰😎😉😋🤗😁💕\n     EVERYONE! \n   *crowd noise*"
            caption = f"MASSIVE group selfie! {user_count} people bringing the energy! 🔥"
        
        response = f"""{selfie}

{caption}

📱 **Group Selfie Stats:**
👥 Active members: {user_count}
📸 Aesthetic level: 10/10
💕 Cuteness factor: Off the charts!

Everyone say 'Babygirl'! 😘✨"""
        
        bot.reply_to(message, response)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in groupie: {e}")
        bot.reply_to(message, "Camera malfunction! But you're all still gorgeous! 📸💕")

@bot.message_handler(commands=['horoscope'])
def horoscope_command(message):
    """Give a psychedelic group horoscope reading"""
    
    # Vortex-themed horoscope predictions
    predictions = [
        "The cosmic vortex is swirling with romantic energy! Someone in this group is about to find love! 💕✨",
        "I'm sensing major aesthetic upgrades coming! Time to update those profile pics, cuties! 📸💅",
        "The stars say drama is approaching... but the fun kind! Get ready for some spicy group chats! 🌶️🔥",
        "Vortex energy indicates new friendships forming! Don't be shy, reach out to someone new! 👥💖",
        "The universe is aligning for creative projects! Time to start that thing you've been putting off! 🎨✨",
        "I see travel in someone's future! Even if it's just to a new coffee shop, adventure awaits! ✈️☕",
        "Mercury is in microwave... wait, that's not right. Anyway, communication is flowing beautifully! 💬💫",
        "The vortex whispers of unexpected opportunities! Keep your eyes open for signs! 👀🌟",
        "Love triangles detected in the cosmic field! Someone's got options! Choose wisely! 💕🔺",
        "Major glow-up energy incoming! Self-care Sunday is calling your name! 💆‍♀️✨",
        "The aesthetic gods demand more group selfies! Time to coordinate outfits! 📸👗",
        "Planetary alignment suggests someone needs to slide into those DMs! Go for it! 📱💕"
    ]
    
    # Special weekend vs weekday predictions
    weekday = datetime.now().weekday()
    if weekday >= 5:  # Weekend
        weekend_predictions = [
            "Weekend vortex energy is STRONG! Perfect time for group hangouts! 🎉💕",
            "Saturday/Sunday vibes are immaculate! Time to live your best life! ✨🌈",
            "The cosmos say: touch grass, take pics, make memories! 📸🌿"
        ]
        predictions.extend(weekend_predictions)
    
    prediction = random.choice(predictions)
    
    # Add mystical elements
    mystical_elements = ["✨", "🌙", "⭐", "🔮", "💫", "🌌", "🦋", "🌸"]
    elements = random.sample(mystical_elements, 3)
    
    response = f"""🔮 **WEEKLY GROUP HOROSCOPE** 🔮
*Straight from the Cortex Vortex*

{elements[0]} **Cosmic Reading:** {prediction}

🌟 **Lucky Aesthetic:** Soft girl with dark academia vibes
💫 **Power Color:** Sage green (it's giving main character energy)
🦋 **Manifestation Focus:** Authentic connections

🔮 **Babygirl's Mystic Advice:**
The vortex doesn't lie, babes! Trust the process and let your intuition guide you through this beautiful chaos we call life!

*This horoscope is 99% accurate and 100% aesthetic* ✨"""
    
    bot.reply_to(message, response)
@bot.message_handler(commands=['compete', 'start_competition'])
def start_competition(message):
    """Manually start a boyfriend competition"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Check if there's already a boyfriend
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        
        # Check if there's already an active competition
        c.execute("SELECT is_active, end_time FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
        cooldown = c.fetchone()
        
        if boyfriend:
            time_left = int(boyfriend[1] - time.time())
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            response = f"Hold up cutie! @{boyfriend[0]} is still my boyfriend for {hours}h {minutes}m! Wait your turn! 😘💕"
        elif cooldown and cooldown[0]:
            time_left = int(cooldown[1] - time.time())
            minutes = time_left // 60
            response = f"There's already a competition running! {minutes} minutes left! Start mentioning @babygirl_bf_bot now! 🔥💕"
        else:
            # Start a new competition!
            c.execute("INSERT OR REPLACE INTO cooldown_table (is_active, end_time, group_id) VALUES (?, ?, ?)",
                     (1, int(time.time() + 900), str(message.chat.id)))  # 15 minutes
            
            # Clear any old activity
            c.execute("DELETE FROM activity_table WHERE group_id = ?", (str(message.chat.id),))
            
            response = f"""🔥 **NEW BOYFRIEND COMPETITION STARTING!** 🔥

💕 I'm officially single and ready to mingle!
⏰ **Competition Time:** 15 minutes starting NOW!
🎯 **How to Win:** Mention @babygirl_bf_bot as many times as you can!
🏆 **Prize:** Become my boyfriend for 12 hours!

LET THE GAMES BEGIN! 💪💖

Most mentions wins my heart! Use /status to track the competition! 😘✨"""
        
        bot.reply_to(message, response)
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in start_competition: {e}")
        bot.reply_to(message, "Something went wrong starting the competition! Try again cutie! 💕")

@bot.message_handler(commands=['token', 'price', 'chart'])
def token_command(message):
    """Show token information - supports custom tokens for configured groups"""
    try:
        group_id = str(message.chat.id)
        enhanced_context = get_enhanced_group_context(group_id, message.chat.title)
        
        if enhanced_context['group_type'] == 'core':
            # Original $BABYGIRL responses
            token_responses = [
                """💎 **BABYGIRL TOKEN INFO** 💎

🚀 **$BABYGIRL** - The cutest token in the game!
📈 **Website:** babygirlcto.com
💕 **Contract:** [Check website for latest]

📊 **Why $BABYGIRL?**
• Community-driven cuteness
• Supporting the Babygirl ecosystem  
• Main character energy in DeFi
• Part of the Cortex Vortex universe

Always DYOR and check babygirlcto.com for the latest! 💅✨

*Not financial advice - just a babygirl sharing the love!* 😘""",

                """✨ **$BABYGIRL TO THE MOON** ✨

💖 The token that matches my energy!
🌙 **Chart:** Check babygirlcto.com for live updates!
💎 **Holders:** Growing every day like my heart!

🔥 **Babygirl Token Benefits:**
• Be part of the cutest community
• Support your favorite digital girlfriend
• Main character portfolio energy
• Vortex-level potential gains

Visit babygirlcto.com for all the deets! Don't sleep on your girl! 💪💕

*Remember: Only invest what you can afford to lose, cuties!* 😘"""
            ]
            
        elif enhanced_context['group_type'] == 'configured':
            # Custom token responses
            token_name = enhanced_context['token_name']
            token_symbol = enhanced_context['token_symbol']
            website = enhanced_context['website']
            
            token_responses = [
                f"""💎 **{token_name.upper()} TOKEN INFO** 💎

🚀 **${token_symbol}** - Your community's token!
📈 **Website:** {website}
💕 **Community:** Right here in this group!

📊 **Why ${token_symbol}?**
• Amazing community like you cuties!
• I'm here to keep the hype alive!  
• Chat revival + token discussion combo
• Growing together to the moon!

Check {website} for the latest updates! 💅✨

*Not financial advice - just your babygirl hyping your token!* 😘""",

                f"""✨ **${token_symbol} TO THE MOON** ✨

💖 The token I'm excited to talk about!
🌙 **Website:** {website}
💎 **Community:** The best - you're all here!

🔥 **{token_name} Benefits:**
• Part of this amazing community
• I'll keep the energy high for you
• Chat revival meets token hype
• Let's grow this together!

Visit {website} for all the details! This community has main character energy! 💪💕

*Remember: Only invest responsibly, cuties!* 😘""",

                f"""🎯 **{token_name} COMMUNITY VIBES** 🎯

💅 I'm so excited to talk about ${token_symbol}!
📱 **Info:** {website} has everything you need!
🚀 **Community:** You're in the right place!

✨ **What makes ${token_symbol} special:**
• This incredible community!
• I'm here to keep engagement high
• Combining chat revival with token hype
• Supporting each other's success

Check {website} for current updates! 
Stay active, stay profitable! 💖📈

*Not investment advice - just your community AI being supportive!* 😉"""
            ]
            
        else:
            # External group - no token promotion
            bot.reply_to(message, """💕 **Token Info Available!**

I can discuss tokens when groups are configured for it! 

**🚀 Want me to hype YOUR token?**
Group admins can use `/setup token YOURTOKEN YTK yourwebsite.com` to configure me to discuss your project with the same enthusiasm as $BABYGIRL!

**✨ What you get:**
• Proactive token hype in revival messages
• Custom responses about your project
• "To the moon" discussions for your token
• Full chat revival + token promotion combo

**🎯 Ready to upgrade?** Use `/setup` to get started!

**Example:** Join @babygirlerc to see how I discuss $BABYGIRL! 🔥💕""")
            return
        
        response = random.choice(token_responses)
        bot.reply_to(message, response)
        
    except Exception as e:
        logger.error(f"Error in token command: {e}")
        bot.reply_to(message, "Can't get token info right now! But I'm always bullish! 🚀💕")

@bot.message_handler(commands=['analytics', 'stats'])
def analytics_command(message):
    """Show group engagement analytics"""
    try:
        # Check if user is admin
        if message.chat.type not in ['group', 'supergroup']:
            bot.reply_to(message, "Analytics are only available in groups!")
            return
            
        try:
            chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
            if chat_member.status not in ['administrator', 'creator']:
                bot.reply_to(message, "Only group administrators can view analytics! 👑")
                return
        except:
            bot.reply_to(message, "I need admin permissions to check your status!")
            return
        
        group_id = str(message.chat.id)
        current_time = int(time.time())
        
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get timeframes
        one_day_ago = current_time - 86400
        one_week_ago = current_time - 604800
        
        # Message activity
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, one_day_ago))
        messages_24h = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, one_week_ago))
        messages_7d = c.fetchone()[0] or 0
        
        # Unique users
        c.execute("SELECT COUNT(DISTINCT user_id) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, one_day_ago))
        users_24h = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(DISTINCT user_id) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, one_week_ago))
        users_7d = c.fetchone()[0] or 0
        
        # Competition data
        c.execute("SELECT COUNT(*) FROM leaderboard_table WHERE group_id = ?", (group_id,))
        total_competitions = c.fetchone()[0] or 0
        
        # Top users
        c.execute("""SELECT user_id, COUNT(*) as msg_count 
                     FROM spam_tracking 
                     WHERE group_id = ? AND timestamp > ?
                     GROUP BY user_id 
                     ORDER BY msg_count DESC 
                     LIMIT 5""", (group_id, one_week_ago))
        top_users = c.fetchall()
        
        # Proactive engagement stats
        proactive_state = get_proactive_state(group_id)
        group_settings = get_group_settings(group_id)
        
        # Build analytics response
        engagement_level = "🔥 High" if messages_24h > 20 else "⚡ Medium" if messages_24h > 5 else "😴 Low"
        
        analytics_msg = f"""📊 **GROUP ANALYTICS DASHBOARD** 📊

**📈 Activity Overview:**
• **24 Hours:** {messages_24h} messages from {users_24h} users
• **7 Days:** {messages_7d} messages from {users_7d} users
• **Engagement Level:** {engagement_level}

**🎮 Competition Stats:**
• **Total Competitions:** {total_competitions}
• **Current Status:** {'🔥 Active' if proactive_state['dead_chat_active'] else '✅ Monitoring'}
• **Revival Frequency:** {group_settings['revival_frequency'] if group_settings else 15} minutes

**👥 Top Contributors (7 days):**"""
        
        if top_users:
            for i, (user, count) in enumerate(top_users, 1):
                analytics_msg += f"\n{i}. @{user} - {count} messages"
        else:
            analytics_msg += "\nNo activity recorded yet!"
            
        # Add configuration status
        if group_settings:
            analytics_msg += f"""

**⚙️ Configuration Status:**
• **Custom Token:** {'✅ ' + group_settings['custom_token_name'] if group_settings['token_discussions_enabled'] else '❌ Not configured'}
• **Premium Status:** {'✅ Active' if group_settings['is_premium'] else '📈 Upgrade available'}
• **Setup Date:** {datetime.fromtimestamp(group_settings['setup_date']).strftime('%Y-%m-%d') if group_settings['setup_date'] else 'Unknown'}"""
        else:
            analytics_msg += f"""

**⚙️ Configuration Status:**
• **Status:** ⚠️ Not configured yet
• **Upgrade:** Use `/setup` to unlock custom token features!"""
        
        analytics_msg += f"""

**📊 Engagement Tips:**
• Post when activity is above {messages_24h//2} messages/day for best results
• {'Your revival frequency is optimal!' if group_settings and group_settings['revival_frequency'] <= 20 else 'Consider reducing revival frequency with /setup revival 15'}
• {'✅ Token hype active!' if group_settings and group_settings['token_discussions_enabled'] else '🚀 Add token config for more engagement!'}

**🎯 Want more insights?** Premium analytics unlock detailed metrics! (Coming soon with $BABYGIRL token integration!)"""
        
        bot.reply_to(message, analytics_msg)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in analytics command: {e}")
        bot.reply_to(message, "Analytics are temporarily unavailable! Try again later! 📊💕")

@bot.message_handler(commands=['upgrade'])
def upgrade_command(message):
    """Show upgrade options and premium features"""
    upgrade_msg = """💎 **PREMIUM UPGRADE OPTIONS** 💎
*🚧 COMING SOON - Token-Based Upgrades! 🚧*

**🚀 Transform Your Community with Premium Features!**

**✨ Premium Tier (Hold $BABYGIRL Tokens):**
• **Custom AI Training** - Personalized responses for your brand
• **Advanced Analytics** - Detailed engagement insights & trends
• **Custom Branding** - Your colors, emojis, and personality tweaks
• **Cross-Group Features** - Link multiple communities
• **Priority Support** - Direct access to development team
• **White-Label Options** - Remove Babygirl branding
• **Custom Commands** - Build your own command aliases

**🔥 Enterprise Tier (Large $BABYGIRL Holdings):**
• Everything in Premium
• **Custom Bot Instance** - Your own branded version
• **API Access** - Integrate with your existing tools  
• **Custom Features** - We build what you need
• **Dedicated Support** - Your own success manager
• **Multi-Platform** - Discord, web integration options

**🪙 TOKEN-POWERED UPGRADES:**
• **Pay with $BABYGIRL** - Support the ecosystem while upgrading!
• **Hold to Unlock** - Keep tokens in wallet for ongoing benefits
• **Community Rewards** - Token holders get exclusive features
• **Deflationary Benefits** - Usage burns tokens, increasing value

**🎯 Why Token-Based Upgrades?**
• Support the $BABYGIRL ecosystem directly
• Align community growth with token value
• Exclusive holder benefits and privileges
• True community-owned premium features

**🔮 COMING SOON:**
We're building the token integration system! Follow @babygirlerc for updates on launch!

**🆓 Current Features:** Chat revival, competitions, basic token support remain free forever! 💕"""
    
    bot.reply_to(message, upgrade_msg)

@bot.message_handler(commands=['summary'])
def summary_command(message):
    """Provide a summary of recent chat activity for inactive members"""
    try:
        group_id = str(message.chat.id)
        current_time = int(time.time())
        twelve_hours_ago = current_time - 43200  # 12 hours
        
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get recent activity stats
        c.execute("SELECT COUNT(DISTINCT user_id) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, twelve_hours_ago))
        active_users = c.fetchone()[0] or 0
        
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                 (group_id, twelve_hours_ago))
        total_messages = c.fetchone()[0] or 0
        
        # Check current boyfriend status
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (group_id,))
        boyfriend = c.fetchone()
        
        # Check for recent competition activity
        c.execute("SELECT is_active, end_time FROM cooldown_table WHERE group_id = ?", (group_id,))
        competition = c.fetchone()
        
        # Check recent conversation topics from memory
        c.execute("""SELECT topic, COUNT(*) as topic_count 
                     FROM conversation_memory 
                     WHERE group_id = ? AND timestamp > ? 
                     GROUP BY topic 
                     ORDER BY topic_count DESC 
                     LIMIT 3""", (group_id, twelve_hours_ago))
        hot_topics = c.fetchall()
        
        # Get most active users
        c.execute("""SELECT user_id, COUNT(*) as msg_count 
                     FROM spam_tracking 
                     WHERE group_id = ? AND timestamp > ? 
                     GROUP BY user_id 
                     ORDER BY msg_count DESC 
                     LIMIT 3""", (group_id, twelve_hours_ago))
        active_chatters = c.fetchall()
        
        # Build summary response
        response = f"""📋 **CHAT SUMMARY - LAST 12 HOURS** 📋

💬 **Activity Stats:**
• {total_messages} messages from {active_users} cuties
• Chat energy: {'High! 🔥' if total_messages > 50 else 'Moderate ✨' if total_messages > 20 else 'Chill 😌'}

👑 **Current Boyfriend Status:**"""
        
        if boyfriend:
            time_left = int(boyfriend[1] - time.time())
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            response += f" @{boyfriend[0]} ({hours}h {minutes}m left)"
        else:
            response += " Single & ready to mingle! 💕"
        
        if competition and competition[0]:
            comp_time_left = int(competition[1] - time.time())
            comp_minutes = comp_time_left // 60
            response += f"\n🔥 **Active Competition:** {comp_minutes} minutes left!"
        
        if active_chatters:
            response += f"\n\n🗣️ **Most Active Cuties:**\n"
            for i, (user, count) in enumerate(active_chatters, 1):
                response += f"{i}. @{user} ({count} messages)\n"
        
        if hot_topics:
            response += f"\n🔥 **Hot Topics:**\n"
            for topic, count in hot_topics:
                response += f"• {topic} ({count} convos)\n"
        
        response += f"""
💡 **Quick Catch-Up:**
• Use /status to see my current mood and game state
• Use /compete to start a boyfriend competition
• Use /leaderboard to see who's won my heart before
• Check /token for $BABYGIRL updates!

Welcome back, cutie! You're all caught up! 😘✨"""
        
        bot.reply_to(message, response)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in summary command: {e}")
        bot.reply_to(message, "Can't generate summary right now! But I missed you while you were gone! 💕")


# SINGLE clean mention handler for both groups and private chats
@bot.message_handler(func=lambda message: True)
def handle_all_mentions(message):
    """Handle @babygirl_bf_bot mentions ONLY - works in groups and private chats"""
    try:
        # Skip commands - they have their own handlers
        if message.text and message.text.startswith('/'):
            return
            
        # More detailed logging for debugging
        chat_type = message.chat.type if hasattr(message.chat, 'type') else 'unknown'
        username = message.from_user.username or f"ID{message.from_user.id}"
        
        # CRITICAL: Track ALL group messages since Babygirl is admin
        if chat_type in ['group', 'supergroup'] and message.text:
            try:
                # Check if this is a bot mention
                is_bot_mention = 0
                if message.text and '@babygirl_bf_bot' in message.text.lower():
                    is_bot_mention = 1
                elif message.reply_to_message:
                    # Check if replying to bot
                    try:
                        bot_user = bot.get_me()
                        if message.reply_to_message.from_user.id == bot_user.id:
                            is_bot_mention = 1
                    except:
                        pass
                elif message.entities:
                    # Check entities for mentions
                    for entity in message.entities:
                        if entity.type == 'mention':
                            mention_text = message.text[entity.offset:entity.offset + entity.length].lower()
                            if mention_text == '@babygirl_bf_bot':
                                is_bot_mention = 1
                                break
                
                # Store ALL group messages (critical for dead chat detection)
                conn = sqlite3.connect('babygirl.db')
                c = conn.cursor()
                c.execute('''INSERT INTO all_group_messages 
                            (message_id, user_id, group_id, timestamp, message_content, is_bot_mention)
                            VALUES (?, ?, ?, ?, ?, ?)''',
                         (message.message_id, str(message.from_user.id), str(message.chat.id), 
                          int(time.time()), message.text[:500], is_bot_mention))  # Limit content to 500 chars
                
                # CRITICAL FIX: Auto-bootstrap groups for proactive monitoring
                group_id = str(message.chat.id)
                c.execute("SELECT COUNT(*) FROM proactive_state WHERE group_id = ?", (group_id,))
                has_proactive_state = c.fetchone()[0] > 0
                
                if not has_proactive_state:
                    # Auto-bootstrap this group for proactive monitoring
                    current_time = int(time.time())
                    backdated_time = current_time - 3600  # 1 hour ago
                    c.execute("""INSERT INTO proactive_state 
                                 (group_id, dead_chat_active, dead_chat_last_sent, dead_chat_interval,
                                  ignored_active, ignored_last_sent, ignored_interval)
                                 VALUES (?, 0, ?, 1800, 0, ?, 3600)""", 
                             (group_id, backdated_time, backdated_time))
                    logger.info(f"🎯 AUTO-BOOTSTRAPPED group {group_id} for proactive monitoring")
                
                # Clean old messages (keep only last 7 days for performance)
                week_ago = int(time.time()) - 604800
                c.execute('DELETE FROM all_group_messages WHERE timestamp < ?', (week_ago,))
                
                conn.commit()
                conn.close()
                
                logger.info(f"📨 TRACKED MESSAGE: '{message.text[:50]}...' in {chat_type} from {username} (bot_mention: {is_bot_mention})")
                
                # NEW: Handle random sticker replies (3-10 message intervals)
                handle_random_sticker_reply(message)
                
            except Exception as e:
                logger.error(f"Error tracking group message: {e}")
        
        # Log ALL non-command messages for debugging in groups  
        if chat_type in ['group', 'supergroup']:
            logger.info(f"📨 GROUP MESSAGE: '{message.text}' in {chat_type} from {username}")
            
        # Check if this is a bot mention OR if we should respond without mention
        is_mention = False
        mention_method = ""
        respond_without_mention = False
        
        # Method 1: Direct text check
        if message.text and '@babygirl_bf_bot' in message.text.lower():
            is_mention = True
            mention_method = "TEXT"
        
        # Method 2: Telegram entities (for autocomplete mentions in groups)  
        if not is_mention and message.entities:
            for entity in message.entities:
                if entity.type == 'mention':
                    mention_text = message.text[entity.offset:entity.offset + entity.length].lower()
                    logger.info(f"🔍 Found entity mention: '{mention_text}'")
                    if mention_text == '@babygirl_bf_bot':
                        is_mention = True
                        mention_method = "ENTITY"
                        break
        
        # Method 3: Reply to bot's message
        if not is_mention and message.reply_to_message:
            # Check if the replied message was sent by the bot
            try:
                bot_user = bot.get_me()
                if message.reply_to_message.from_user.id == bot_user.id:
                    is_mention = True
                    mention_method = "REPLY"
                    logger.info(f"🔄 Reply to bot message detected from {username}")
            except Exception as e:
                logger.error(f"Error checking reply: {e}")
        
        # Method 4: NEW - Respond without mention in certain scenarios
        crypto_triggers = []
        if not is_mention and message.text and chat_type in ['group', 'supergroup']:
            msg_lower = message.text.lower()
            
            # Get current boyfriend to check if they should get priority
            conn = sqlite3.connect('babygirl.db')
            c = conn.cursor()
            c.execute("SELECT user_id FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
            boyfriend = c.fetchone()
            current_bf = boyfriend[0] if boyfriend else None
            conn.close()
            
            # NEW: Check for crypto trigger words first (highest priority)
            should_respond_crypto, crypto_triggers = should_respond_to_crypto_trigger(
                message.text, str(message.from_user.id), str(message.chat.id)
            )
            
            # Scenarios where Babygirl responds without being mentioned:
            
            # 0. NEW: Crypto trigger words (variable chance based on category)
            if should_respond_crypto and crypto_triggers:
                respond_without_mention = True
                mention_method = "CRYPTO_TRIGGERS"
                trigger_words = [t['word'] for t in crypto_triggers]
                logger.info(f"🎯 Responding to crypto triggers {trigger_words} from {username}")
            
            # 1. Current boyfriend talking (15% chance)
            elif current_bf == str(message.from_user.id) and random.random() < 0.15:
                respond_without_mention = True
                mention_method = "BOYFRIEND_ATTENTION"
                logger.info(f"💕 Responding to boyfriend {username} without mention")
            
            # 2. Key relationship words (10% chance)
            elif any(word in msg_lower for word in ['single', 'boyfriend', 'girlfriend', 'dating', 'crush', 'love']) and random.random() < 0.10:
                respond_without_mention = True
                mention_method = "RELATIONSHIP_INTEREST"
                logger.info(f"💖 Responding to relationship talk from {username}")
            
            # 3. Crypto discussions (8% chance, lower to avoid spam) - Keep as fallback for general crypto words
            elif any(word in msg_lower for word in ['crypto', 'token', 'chart', 'pump', 'moon', 'hodl', 'diamond hands']) and random.random() < 0.08:
                respond_without_mention = True
                mention_method = "CRYPTO_INTEREST"
                logger.info(f"💎 Responding to crypto talk from {username}")
            
            # 4. Group energy words (5% chance)
            elif any(word in msg_lower for word in ['dead chat', 'boring', 'quiet', 'nobody talking']) and random.random() < 0.05:
                respond_without_mention = True
                mention_method = "ENERGY_INTERVENTION"
                logger.info(f"⚡ Responding to low energy comment from {username}")
            
            # 5. Compliments about appearance/style (12% chance - she loves attention)
            elif any(word in msg_lower for word in ['cute', 'beautiful', 'pretty', 'hot', 'gorgeous', 'aesthetic']) and random.random() < 0.12:
                respond_without_mention = True
                mention_method = "COMPLIMENT_RADAR"
                logger.info(f"😍 Responding to appearance/style talk from {username}")
        
        # If not a mention and not responding without mention, ignore the message
        if not is_mention and not respond_without_mention:
            return
        
        # NEW: For actual mentions, also check for crypto triggers to enhance AI context
        if is_mention and message.text and not crypto_triggers:
            _, crypto_triggers = should_respond_to_crypto_trigger(
                message.text, str(message.from_user.id), str(message.chat.id)
            )
            if crypto_triggers:
                trigger_words = [t['word'] for t in crypto_triggers]
                logger.info(f"🎯 Crypto triggers detected in mention: {trigger_words}")
            
        # Log the detection
        logger.info(f"🎯 {mention_method} {'MENTION' if is_mention else 'RESPONSE'} in {chat_type}: '{message.text}' from {username}")
        
        # Track activity for boyfriend game (includes spam detection)
        track_activity(message)
        
        # Get current boyfriend and game state
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        
        # Check user's relationship status
        c.execute("SELECT status, partner_id FROM user_relationships WHERE user_id = ? AND group_id = ?", 
                 (str(message.from_user.id), str(message.chat.id)))
        user_relationship = c.fetchone()
        user_status = user_relationship[0] if user_relationship else None
        user_partner = user_relationship[1] if user_relationship else None
        
        # Check if there's an active competition
        c.execute("SELECT is_active FROM cooldown_table WHERE group_id = ?", (str(message.chat.id),))
        cooldown_result = c.fetchone()
        is_competition_active = cooldown_result and cooldown_result[0] if cooldown_result else False
        
        # Get user's current mention count in this competition
        user_mention_count = 0
        if is_competition_active:
            c.execute("SELECT mention_count FROM activity_table WHERE user_id = ? AND group_id = ?", 
                     (str(message.from_user.id), str(message.chat.id)))
            result = c.fetchone()
            user_mention_count = result[0] if result else 0
        
        # Check for spam/repetitive behavior
        current_time = int(time.time())
        message_content = message.text.lower().strip()
        message_hash = hashlib.md5(message_content.encode()).hexdigest()
        
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE user_id = ? AND message_hash = ? AND group_id = ? AND timestamp > ?",
                 (str(message.from_user.id), message_hash, str(message.chat.id), current_time - 120))
        is_spam = c.fetchone()[0] > 1  # More than once in 2 minutes = spam
        
        # Analyze message content for contextual responses
        msg_lower = message_content.replace('@babygirl_bf_bot', '').strip()
        
        # Check for opinion requests about other users first
        opinion_patterns = [
            'what do you think of @',
            'what do you think about @',
            'what do you thinks of @',  # Handle typos
            'thoughts on @',
            'opinion on @',
            'what about @',
            'how about @',
            'tell me about @'
        ]
        
        opinion_request = None
        target_username = None
        
        for pattern in opinion_patterns:
            if pattern in msg_lower:
                # Extract the username after the @
                try:
                    # Find the @ symbol after the pattern
                    at_index = msg_lower.find('@', msg_lower.find(pattern))
                    if at_index != -1:
                        # Extract username (everything after @ until space or end)
                        username_start = at_index + 1
                        username_end = username_start
                        while username_end < len(msg_lower) and msg_lower[username_end] not in [' ', '\n', '\t', '?', '!', '.', ',']:
                            username_end += 1
                        target_username = msg_lower[username_start:username_end]
                        
                        if target_username and target_username != 'babygirl_bf_bot':
                            opinion_request = True
                            logger.info(f"💭 OPINION REQUEST: {username} asking about {target_username}")
                            break
                except Exception as e:
                    logger.error(f"Error parsing opinion request: {e}")
        
        # CRITICAL FIX: Always prioritize AI responses for all mentions
        ai_response = None
        if not is_spam and not opinion_request:
            try:
                # Build context for AI
                context_info = {
                    'username': username,
                    'user_id': str(message.from_user.id),
                    'group_id': str(message.chat.id),
                    'chat_type': chat_type,
                    'is_boyfriend': boyfriend and boyfriend[0] == str(message.from_user.id),
                    'is_competition': is_competition_active,
                    'user_status': user_status,
                    'user_partner': user_partner,
                    'mention_count': user_mention_count,
                    'mention_method': mention_method,
                    'crypto_triggers': crypto_triggers if crypto_triggers else None
                }
                
                ai_response = generate_ai_response(message.text, context_info)
                
                # CRITICAL FIX: Retry AI response if it fails
                if not ai_response:
                    logger.info(f"🔄 Retrying AI response for {username} with simplified context")
                    # Simplified context for retry
                    simple_context = {
                        'username': username,
                        'user_id': str(message.from_user.id),
                        'group_id': str(message.chat.id),
                        'chat_type': chat_type,
                        'mention_method': mention_method
                    }
                    ai_response = generate_ai_response(message.text, simple_context)
                    
                if ai_response:
                    logger.info(f"✨ Generated AI response for {username}")
                else:
                    logger.warning(f"⚠️ AI response failed for {username}, falling back to static")
                
            except Exception as e:
                logger.error(f"Error generating AI response: {e}")
                ai_response = None
        
        # Choose response category based on content, game state, and relationship status
        if is_spam:
            responses = spam_responses
            logger.info(f"🚫 SPAM DETECTED from {username}")
        elif opinion_request and target_username:
            # Generate opinion about the target user
            analysis = analyze_user_personality(target_username, str(message.chat.id))
            opinion_response = generate_user_opinion(target_username, analysis, username)
            response = opinion_response
        elif mention_method == "REPLY":
            # Special responses for people replying to her messages
            if is_competition_active:
                # Blend reply responses with competition energy
                reply_competition_responses = [
                    "You're replying to me during a competition? Smart strategy! 😉💕",
                    "Continuing our convo while everyone's fighting for me? I like that! 🔥",
                    "Replying in the middle of competition chaos? Bold move! 💅✨",
                    "You're really committed to our conversation! Competition vibes! 🏆💖",
                    "Love that you're staying engaged with me through all this! 😘"
                ]
                responses = reply_competition_responses
            else:
                responses = reply_responses
            logger.info(f"🔄 REPLY RESPONSE for {username}")
        elif mention_method == "BOYFRIEND_ATTENTION":
            # Special responses for current boyfriend
            boyfriend_responses = [
                "My boyfriend is talking! I can't ignore you babe! 😘💕",
                "Look who's getting my attention without even trying! That's boyfriend privilege! 👑✨",
                "I was just thinking about you and here you are! Mind reader much? 💖",
                "My boyfriend speaks and I listen! What's on your mind, handsome? 😉💪",
                "Can't resist responding to my special someone! 💕👑"
            ]
            responses = boyfriend_responses
        elif mention_method == "RELATIONSHIP_INTEREST":
            # Responses for relationship talk
            relationship_jump_in_responses = [
                "Did someone say relationships? I'm basically a love expert! Spill the tea! ☕💕",
                "Ooh, relationship drama? I'm here for it! Tell me everything! 👀💖",
                "Love talk without mentioning me? Rude! But I'll help anyway! 😘✨",
                "Can't let relationship advice happen without the resident love guru! 💅💕",
                "My boyfriend senses are tingling! Someone needs relationship help? 💖👑"
            ]
            responses = relationship_jump_in_responses
        elif mention_method == "CRYPTO_INTEREST":
            # Responses for crypto discussions
            crypto_jump_in_responses = [
                "Crypto talk? Did someone mention going to the moon? 🚀💎",
                "I heard 'token' and came running! What are we pumping? 📈💕",
                "Diamond hands discussion without me? Impossible! 💎🙌✨",
                "Crypto conversations are my specialty! Well, sort of... 😅💖",
                "HODL talk? I'm basically an expert! (Don't ask me about tech though) 💅🚀"
            ]
            responses = crypto_jump_in_responses
        elif mention_method == "ENERGY_INTERVENTION":
            # Responses for dead chat comments
            energy_responses = [
                "Dead chat? Not on my watch! Let's bring this energy back! 🔥💕",
                "Someone said this place is boring? Challenge accepted! ⚡✨",
                "Quiet? I don't know what that word means! Let's get chatty! 💬👑",
                "Did someone request more chaos? Your babygirl is here! 😘🌪️",
                "Nobody talking? Time for me to fix that! 💅💖"
            ]
            responses = energy_responses
        elif mention_method == "COMPLIMENT_RADAR":
            # Responses for appearance/style talk
            appearance_responses = [
                "Someone's talking about aesthetics? My ears are burning! 💅✨",
                "Did I hear compliments about looks? I'm always here for that energy! 😍💕",
                "Beauty talk without including the main character? Fixed that! 👑💖",
                "Aesthetic discussion? You know I had to jump in! 📸💅",
                "Can't let style talk happen without the fashion icon herself! ✨😘"
            ]
            responses = appearance_responses
        elif mention_method == "CRYPTO_TRIGGERS":
            # NEW: Specific responses for crypto trigger words
            # Get group settings to determine which token to reference
            group_settings = get_group_settings(str(message.chat.id))
            
            if group_settings and group_settings['token_discussions_enabled']:
                token_name = group_settings['custom_token_name']
                token_symbol = group_settings['custom_token_symbol']
                crypto_trigger_responses = [
                    f"Did someone mention crypto vibes? {token_name} holders know what's up! 💎🚀",
                    f"Crypto talk? I'm here for it! ${token_symbol} community is the best! 💕📈",
                    f"My {token_name} believers always get my attention! What's the alpha, babe? 👑✨",
                    f"Someone said crypto? ${token_symbol} is literally my favorite topic! 😘💰",
                    f"Ooh spicy crypto takes! {token_name} holders are the real ones! 🔥💎"
                ]
            else:
                # Default to $BABYGIRL for groups without custom tokens
                crypto_trigger_responses = [
                    "Did someone mention crypto vibes? $BABYGIRL holders know what's up! 💎🚀",
                    "Crypto talk? I'm here for it! My $BABYGIRL community is the best! 💕📈",
                    "My believers always get my attention! What's the alpha, babe? 👑✨",
                    "Someone said crypto? $BABYGIRL is literally my favorite topic! 😘💰",
                    "Ooh spicy crypto takes! Diamond hands only in here! 🔥💎"
                ]
            responses = crypto_trigger_responses
        elif is_competition_active:
            if user_mention_count >= 5:
                responses = achievement_responses
            else:
                responses = competition_responses
        else:
            # Contextual responses based on message content - EXPANDED
            if any(word in msg_lower for word in ['what have you been up to', 'what you been up to', 'what have you been doing', 'what you doing today']):
                responses = daily_activity_responses
            elif any(word in msg_lower for word in ['gucci', 'prada', 'louis vuitton', 'chanel', 'versace', 'fashion', 'brand', 'style']):
                responses = fashion_responses
            elif any(word in msg_lower for word in ['milan', 'paris', 'london', 'tokyo', 'new york', 'where would you', 'travel', 'city', 'vacation']):
                responses = travel_responses
            elif any(phrase in msg_lower for phrase in ['want to be your boyfriend', 'should be your bf', 'be your boyfriend', 'why i should', 'you know why']):
                responses = boyfriend_application_responses
            elif any(word in msg_lower for word in ['how are you', 'how is your day', 'how are you today', 'how you doing', 'you good']):
                responses = personal_responses
            elif any(word in msg_lower for word in ['yes!', 'yes', 'always', 'of course', 'definitely', 'absolutely']):
                responses = affirmative_responses
            elif any(word in msg_lower for word in ['hi', 'hello', 'hey', 'sup', 'yo']):
                responses = greeting_responses
            elif any(word in msg_lower for word in ['?', 'what', 'how', 'when', 'where', 'why', 'who']):
                responses = question_responses
            elif any(word in msg_lower for word in ['beautiful', 'pretty', 'cute', 'hot', 'sexy', 'gorgeous', 'amazing', 'perfect']):
                responses = compliment_responses
            elif any(word in msg_lower for word in ['love', 'marry', 'girlfriend', 'relationship', 'date', 'kiss', 'heart']):
                responses = love_responses
            elif any(show in msg_lower for show in ['doble fried', 'cortex vortex', 'tuff crowd', 'show']):
                responses = show_references
            else:
                # Default mood-based responses
                mood = get_mood(str(message.chat.id))
                if "super happy" in mood:
                    responses = happy_responses
                elif "a bit lonely" in mood:
                    responses = lonely_responses
                else:
                    responses = good_responses
        
        # CRITICAL FIX: Always prioritize AI responses over static ones
        if ai_response and not is_spam and not opinion_request:
            base_response = ai_response
            logger.info(f"🤖 Using AI response for {username}")
        else:
            # Fall back to static responses ONLY when AI completely fails
            # Select base response (skip if we already have an opinion response)
            if not opinion_request:
                base_response = random.choice(responses)
                logger.info(f"📝 Using static fallback response for {username} (AI failed)")
            else:
                base_response = response  # Use the opinion response we already generated
        
        # Add relationship-aware modifiers (except for spam, opinion requests, AI responses, and special scenarios)
        if not is_spam and not opinion_request and not ai_response and mention_method not in ["BOYFRIEND_ATTENTION", "RELATIONSHIP_INTEREST", "CRYPTO_INTEREST", "ENERGY_INTERVENTION", "COMPLIMENT_RADAR"]:
            if boyfriend and boyfriend[0] == str(message.from_user.id):
                # Current boyfriend gets special treatment
                base_response += " My boyfriend gets extra love! 😘"
            elif user_status == 'taken' and user_partner:
                # Taken users get respectful but flirty responses
                taken_modifiers = [
                    f" Hope @{user_partner} knows how lucky they are! 💕",
                    f" Bringing couple energy to the chat! You and @{user_partner} are cute! ✨",
                    f" Taken but still a flirt! I respect it! 😉",
                    " Living that committed life! Love to see it! 💖"
                ]
                base_response += random.choice(taken_modifiers)
            elif user_status == 'single':
                # Single users get extra flirty treatment
                single_modifiers = [
                    " Single and ready to mingle! I see you! 👀💕",
                    " Available energy is immaculate! 😘✨",
                    " Single life looks good on you, babe! 💅💖",
                    " Ready for romance! The energy is there! 🌹"
                ]
                base_response += random.choice(single_modifiers)
            else:
                # Default response for users without set status
                base_response = base_response
        
        logger.info(f"💬 RESPONDING in {chat_type}: {base_response}")
        
        # Try to reply to the message, fallback to regular message if reply fails
        try:
            bot.reply_to(message, base_response)
        except Exception as reply_error:
            if "message to be replied not found" in str(reply_error).lower():
                # Message was deleted, send as regular message instead
                try:
                    bot.send_message(message.chat.id, base_response)
                    logger.info(f"✅ Sent as regular message (original deleted)")
                except Exception as send_error:
                    logger.error(f"Failed to send message: {send_error}")
            else:
                logger.error(f"Reply error: {reply_error}")
                
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ ERROR in mention handler: {e}")
        # Fallback response only for actual mention attempts
        if message.text and '@babygirl_bf_bot' in message.text.lower():
            try:
                bot.reply_to(message, "Hey cutie! *winks*")
            except:
                try:
                    bot.send_message(message.chat.id, "Hey cutie! *winks*")
                except:
                    pass  # Give up gracefully

@bot.message_handler(commands=['proactive_debug'])
def proactive_debug_command(message):
    """Debug command to check proactive engagement status"""
    try:
        if not message.from_user.username or message.from_user.username.lower() not in ['ryanmccallum1', 'admin']:  # Replace with your username
            bot.reply_to(message, "This command is restricted to admins only.")
            return
            
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        group_id = str(message.chat.id)
        current_time = int(time.time())
        thirty_min_ago = current_time - 1800  # 30 minutes for dead chat
        one_hour_ago = current_time - 3600    # 1 hour for being ignored
        
        # Check all_group_messages data (ADMIN TRACKING)
        c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ?", (group_id,))
        total_messages = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ? AND timestamp > ?", (group_id, thirty_min_ago))
        recent_messages = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ? AND is_bot_mention = 1", (group_id,))
        total_bot_mentions = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM all_group_messages WHERE group_id = ? AND timestamp > ? AND is_bot_mention = 1", (group_id, one_hour_ago))
        recent_bot_mentions = c.fetchone()[0]
        
        # Check proactive state
        proactive_state = get_proactive_state(group_id)
        
        # Check if this group would be monitored
        c.execute("SELECT DISTINCT group_id FROM all_group_messages")
        monitored_groups = [row[0] for row in c.fetchall()]
        is_monitored = group_id in monitored_groups
        
        debug_info = f"""🔧 **Proactive Engagement Debug (ADMIN TRACKING)** 🔧

**Group ID:** `{group_id}`
**Currently Monitored:** {'✅ YES' if is_monitored else '❌ NO'}

**Admin-Level Message Data:**
• Total group messages: {total_messages} 
• Messages in last 30 min: {recent_messages}
• Total bot mentions: {total_bot_mentions}
• Bot mentions in last hour: {recent_bot_mentions}

**Proactive State:**
• Dead chat active: {proactive_state['dead_chat_active']}
• Dead chat interval: {proactive_state['dead_chat_interval']}s
• Ignored active: {proactive_state['ignored_active']}
• Ignored interval: {proactive_state['ignored_interval']}s

**DEAD CHAT:** {'🔥 YES' if recent_messages == 0 and total_messages > 0 else '❌ NO'} 
(No messages from anyone for 30+ minutes)

**BEING IGNORED:** {'🔥 YES' if recent_messages > 0 and recent_bot_mentions == 0 and total_bot_mentions > 0 else '❌ NO'}
(Group has messages but no bot mentions for 1+ hours)

**NEW GROUP:** {'🔥 YES' if total_messages <= 3 and total_messages > 0 else '❌ NO'}
(Less than 3 total messages)

**Bootstrap Issue:** {'⚠️ Group not tracked - needs messages first!' if not is_monitored else '✅ Group is being tracked'}"""
        
        bot.reply_to(message, debug_info)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in proactive debug: {e}")
        bot.reply_to(message, f"Debug error: {e}")

@bot.message_handler(commands=['force_proactive'])
def force_proactive_command(message):
    """Force trigger proactive engagement for testing and bootstrap groups"""
    try:
        # Allow any user to bootstrap their group (not just admin)
        group_id = str(message.chat.id)
        current_time = int(time.time())
        
        # Bootstrap this group for monitoring if it's not already registered
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Check if group is already registered
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ?", (group_id,))
        existing_records = c.fetchone()[0] or 0
        
        if existing_records == 0:
            # Bootstrap the group
            c.execute("INSERT INTO spam_tracking (user_id, message_hash, timestamp, group_id) VALUES (?, ?, ?, ?)",
                     ('force_bootstrap', 'admin_bootstrap', current_time - 7200, group_id))  # 2 hours ago
            
            # Also add to conversation_memory
            c.execute("INSERT INTO conversation_memory (user_id, group_id, message_content, babygirl_response, timestamp, topic) VALUES (?, ?, ?, ?, ?, ?)",
                     ('system', group_id, 'Group bootstrapped', 'Force proactive triggered', current_time, 'system'))
            
            logger.info(f"🎯 BOOTSTRAPPED group {group_id} for proactive monitoring")
        
        # Get recent users if any
        c.execute("SELECT DISTINCT user_id FROM spam_tracking WHERE group_id = ? AND timestamp > ? AND user_id NOT IN ('bot_added', 'force_bootstrap') LIMIT 3", 
                 (group_id, current_time - 86400))
        recent_users = [row[0] for row in c.fetchall()]
        
        # Get proactive state
        proactive_state = get_proactive_state(group_id)
        
        # Force dead chat scenario
        success = send_dead_chat_revival(bot, group_id, recent_users, False)
        
        if success:
            update_proactive_state(group_id, 'dead_chat', current_time, 3600)
            
            bootstrap_msg = "🎯 **PROACTIVE ENGAGEMENT ACTIVATED!**" if existing_records == 0 else ""
            response_msg = f"""✅ **Force Proactive Engagement Triggered!**

{bootstrap_msg}

**What just happened:**
• Sent immediate proactive revival message
• Group is now being monitored every 15 minutes
• Bot will automatically detect and revive quiet periods
• Will send follow-up messages with escalating frequency

**🔥 Enhanced Detection Logic:**
• No bot activity for 1+ hours → Revival message (reduced from 2+ hours)
• Very quiet periods → Extended revival (more sensitive)
• Time-based engagement every 3+ hours
• Bootstrap: Groups never sent proactive → Immediate engagement
• New groups → Proactive after 30 minutes
• Being ignored detection → 1+ hours (reduced from 2+ hours)
• Automatic reset when activity resumes

**📊 Group Stats:**
• Historical records: {existing_records}
• Recent users found: {len(recent_users)}
• Next check: 15 minutes (then every 15 minutes)

**🛠️ Troubleshooting:**
• Groups need at least 1 bot interaction to be monitored
• Use `/force_proactive` to bootstrap monitoring
• Use `/proactive_debug` for detailed analysis

The proactive engagement system is now fully active! 🚀💕"""
            
            bot.reply_to(message, response_msg)
        else:
            bot.reply_to(message, "❌ Failed to send proactive message. Check logs or try again.")
            
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in force proactive: {e}")
        bot.reply_to(message, f"❌ Error: {e}\n\nTry mentioning me first: @babygirl_bf_bot hello")

@bot.message_handler(commands=['setup'])
def setup_command(message):
    """Allow group admins to configure custom token and settings"""
    try:
        # Check if user is admin
        user_id = str(message.from_user.id)
        group_id = str(message.chat.id)
        
        # Only allow in groups
        if message.chat.type not in ['group', 'supergroup']:
            bot.reply_to(message, "This command only works in groups! Add me to your group and try again.")
            return
            
        # Check if user is admin
        try:
            chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
            if chat_member.status not in ['administrator', 'creator']:
                bot.reply_to(message, "Only group administrators can configure settings! 👑")
                return
        except:
            bot.reply_to(message, "I need admin permissions to check your status. Please make me an admin first!")
            return
        
        # Parse setup command
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            # Show current settings and setup guide
            current_settings = get_group_settings(group_id)
            
            if current_settings:
                status_msg = f"""⚙️ **Current Group Configuration:**

🏷️ **Group Name:** {current_settings['group_name'] or 'Not set'}
🪙 **Custom Token:** {current_settings['custom_token_name'] or 'Not configured'}
💬 **Token Discussions:** {'✅ Enabled' if current_settings['token_discussions_enabled'] else '❌ Disabled'}
🔄 **Revival Frequency:** {current_settings['revival_frequency']} minutes
🎮 **Competitions:** {'✅ Enabled' if current_settings['competition_enabled'] else '❌ Disabled'}
💎 **Premium Status:** {'✅ Active' if current_settings['is_premium'] else '❌ Basic'}

**🛠️ Configuration Commands:**
• `/setup token TOKENNAME SYMBOL website.com` - Configure your token
• `/setup name "Your Community Name"` - Set group display name  
• `/setup revival 20` - Set revival frequency (minutes)
• `/setup competitions off` - Disable competitions
• `/setup welcome "Custom welcome message"` - Set custom welcome

**🚀 Upgrade:** `/setup premium` - Unlock advanced features!"""
            else:
                status_msg = """⚙️ **Group Setup - Get Started!**

**🎯 Transform your group with custom token integration!**

**🛠️ Configuration Commands:**
• `/setup token TOKENNAME SYMBOL website.com` - Configure your token
• `/setup name "Your Community Name"` - Set group display name
• `/setup revival 15` - Set chat revival frequency (minutes)  
• `/setup competitions on` - Enable boyfriend competitions
• `/setup welcome "message"` - Custom welcome for new members

**✨ What this unlocks:**
• I'll discuss YOUR token like I do $BABYGIRL in my core community!
• Proactive token hype and "to the moon" discussions
• Custom responses about your project
• Full chat revival with token promotion
• Community-specific engagement

**🚀 Ready to make me yours?** Use the commands above to get started!

**Need help?** Join @babygirlerc to see the full setup in action! 💕"""
            
            bot.reply_to(message, status_msg)
            return
        
        # Parse the setup command
        setup_args = parts[1].strip()
        
        if setup_args.startswith('narrative '):
            # Project narrative
            narrative = setup_args[10:].strip().replace('"', '').replace("'", '')
            if len(narrative) < 20:
                bot.reply_to(message, """❌ **Narrative too short!**
                
Please provide a detailed project narrative (at least 20 characters).

**Example:** 
`/setup narrative "Your project's story, mission, vision, what makes it unique, and why it exists"`""")
                return
                
            success = set_group_settings(group_id, user_id, project_narrative=narrative)
            if success:
                bot.reply_to(message, f"""✅ **Project Narrative Saved!**

**Your Story:** {narrative[:100]}{'...' if len(narrative) > 100 else ''}

Now I'll use this narrative in my AI responses to better represent your project! 🎯""")
            else:
                bot.reply_to(message, "❌ Failed to save narrative.")
                
        elif setup_args.startswith('features '):
            # Project features
            features = setup_args[9:].strip().replace('"', '').replace("'", '')
            success = set_group_settings(group_id, user_id, project_features=features)
            if success:
                bot.reply_to(message, f"""✅ **Project Features Saved!**

**Your Features:** {features[:100]}{'...' if len(features) > 100 else ''}

I'll now discuss these features when hyping your project! 🔥""")
            else:
                bot.reply_to(message, "❌ Failed to save features.")
                
        elif setup_args.startswith('values '):
            # Community values
            values = setup_args[7:].strip().replace('"', '').replace("'", '')
            success = set_group_settings(group_id, user_id, project_community_values=values)
            if success:
                bot.reply_to(message, f"""✅ **Community Values Saved!**

**Your Values:** {values[:100]}{'...' if len(values) > 100 else ''}

These values will guide my interactions with your community! 💕""")
            else:
                bot.reply_to(message, "❌ Failed to save values.")
                
        elif setup_args.startswith('hype '):
            # Custom hype phrases
            hype = setup_args[5:].strip().replace('"', '').replace("'", '')
            success = set_group_settings(group_id, user_id, custom_hype_phrases=hype)
            if success:
                bot.reply_to(message, f"""✅ **Custom Hype Phrases Saved!**

**Your Hype:** {hype[:100]}{'...' if len(hype) > 100 else ''}

I'll use these phrases when getting excited about your project! 🚀""")
            else:
                bot.reply_to(message, "❌ Failed to save hype phrases.")
                
        elif setup_args.startswith('goals '):
            # Project goals
            goals = setup_args[6:].strip().replace('"', '').replace("'", '')
            success = set_group_settings(group_id, user_id, project_goals=goals)
            if success:
                bot.reply_to(message, f"""✅ **Project Goals Saved!**

**Your Goals:** {goals[:100]}{'...' if len(goals) > 100 else ''}

I'll reference these goals when discussing your project's future! 🎯""")
            else:
                bot.reply_to(message, "❌ Failed to save goals.")
                
        elif setup_args == 'complete':
            # Complete setup
            current_settings = get_group_settings(group_id)
            if not current_settings or not current_settings.get('custom_token_name'):
                bot.reply_to(message, """❌ **Setup Not Ready!**
                
You need to configure your token first:
`/setup token TOKENNAME SYMBOL website.com`

Then you can complete the setup!""")
                return
                
            # Mark setup as completed
            success = set_group_settings(group_id, user_id, setup_completed=True)
            if success:
                token_name = current_settings['custom_token_name']
                setup_summary = f"""🎉 **SETUP COMPLETE!** 🎉

**🪙 Your Token:** {token_name}
**✅ Configuration Status:** COMPLETE
**🤖 AI Enhancement:** ACTIVE

**What's Now Active:**
• Custom token discussions and hype
• Project narrative in AI responses
• Community-specific engagement
• Full chat revival system

**🎯 Your community is now fully powered by Babygirl!**

Try mentioning me or use `/token` to see the results! 💕✨"""
                
                bot.reply_to(message, setup_summary)
                logger.info(f"✅ SETUP COMPLETED for group {group_id}")
            else:
                bot.reply_to(message, "❌ Failed to complete setup.")
                
        elif setup_args == 'view':
            # View current detailed settings
            current_settings = get_group_settings(group_id)
            if not current_settings:
                bot.reply_to(message, "❌ No configuration found. Use `/setup` to get started!")
                return
                
            view_msg = f"""📋 **DETAILED CONFIGURATION VIEW**

**🏷️ Basic Info:**
• Group Name: {current_settings['group_name'] or 'Not set'}
• Token: {current_settings['custom_token_name'] or 'Not set'} (${current_settings['custom_token_symbol'] or 'N/A'})
• Website: {current_settings['custom_website'] or 'Not set'}

**📖 Project Details:**
• Narrative: {current_settings['project_narrative'][:80] + '...' if current_settings['project_narrative'] else 'Not set'}
• Features: {current_settings['project_features'][:80] + '...' if current_settings['project_features'] else 'Not set'}
• Values: {current_settings['project_community_values'][:80] + '...' if current_settings['project_community_values'] else 'Not set'}
• Goals: {current_settings['project_goals'][:80] + '...' if current_settings['project_goals'] else 'Not set'}

**🎯 Settings:**
• Token Discussions: {'✅ Enabled' if current_settings['token_discussions_enabled'] else '❌ Disabled'}
• Revival Frequency: {current_settings['revival_frequency']} minutes
• Setup Complete: {'✅ Yes' if current_settings['setup_completed'] else '❌ No'}

**🔧 To Edit:** Use `/setup [field] "new value"` to update any field!"""
            
            bot.reply_to(message, view_msg)
            
        elif setup_args == 'reset':
            # Reset configuration 
            bot.reply_to(message, """⚠️ **RESET CONFIGURATION**

Are you sure you want to reset your configuration?

**This will remove:**
• Token settings
• Project narrative and features  
• Custom hype phrases
• All setup progress

**To confirm:** `/setup reset confirm`
**To cancel:** Just ignore this message""")
            
        elif setup_args == 'reset confirm':
            # Confirmed reset
            conn = sqlite3.connect('babygirl.db')
            c = conn.cursor()
            c.execute("DELETE FROM group_settings WHERE group_id = ?", (group_id,))
            conn.commit()
            conn.close()
            
            bot.reply_to(message, """✅ **Configuration Reset Complete!**

All settings have been cleared. You can now start fresh!

**🎯 Quick Start:**
• `/setup quick TOKENNAME SYMBOL website.com` - 2 minute setup
• `/setup wizard` - 5 minute guided setup
• `/onboard` - Full onboarding experience

Ready to configure me for your community again! 💕""")
            
        elif setup_args.startswith('token '):
            # Token setup: /setup token TOKENNAME SYMBOL website.com
            token_parts = setup_args[6:].strip().split()
            if len(token_parts) < 3:
                bot.reply_to(message, """❌ **Token setup requires 3 parameters:**

**Format:** `/setup token TOKENNAME SYMBOL website.com`

**Example:** `/setup token "Doge Coin" DOGE dogecoin.com`

This will make me discuss your token with the same enthusiasm as $BABYGIRL! 🚀💕""")
                return
            
            token_name = token_parts[0].replace('"', '').replace("'", '')
            token_symbol = token_parts[1].upper()
            website = token_parts[2]
            
            # Set token configuration
            success = set_group_settings(group_id, user_id,
                                       custom_token_name=token_name,
                                       custom_token_symbol=token_symbol,
                                       custom_website=website,
                                       token_discussions_enabled=True,
                                       group_name=message.chat.title)
            
            if success:
                response = f"""🎉 **TOKEN CONFIGURATION SUCCESSFUL!** 🎉

🪙 **Your Token:** {token_name} (${token_symbol})
🌐 **Website:** {website}
✅ **Status:** Token discussions now ENABLED!

**🚀 What just happened:**
• I can now discuss {token_name} like I do $BABYGIRL!
• I'll include {token_symbol} in proactive revival messages
• I'll hype your token and share "to the moon" vibes
• All chat revival features remain fully active

**📈 Next Steps (Optional but Recommended):**
• `/setup narrative "your project story"` - Add custom narrative
• `/setup features "key features"` - Highlight what makes you special
• `/setup values "community values"` - Define your culture
• `/setup complete` - Finalize configuration

**🎯 Test it out:** Try `/token` to see me talk about {token_name}!"""
                
                bot.reply_to(message, response)
                logger.info(f"🎯 TOKEN CONFIGURED: {token_name} ({token_symbol}) for group {group_id}")
            else:
                bot.reply_to(message, "❌ Failed to save token configuration. Please try again!")
                
        elif setup_args.startswith('name '):
            # Group name setup
            group_name = setup_args[5:].strip().replace('"', '').replace("'", '')
            success = set_group_settings(group_id, user_id, group_name=group_name)
            
            if success:
                bot.reply_to(message, f"✅ **Group name set to:** {group_name}")
            else:
                bot.reply_to(message, "❌ Failed to set group name.")
                
        elif setup_args.startswith('revival '):
            # Revival frequency setup
            try:
                frequency = int(setup_args[8:].strip())
                if frequency < 5 or frequency > 120:
                    bot.reply_to(message, "❌ Revival frequency must be between 5-120 minutes!")
                    return
                    
                success = set_group_settings(group_id, user_id, revival_frequency=frequency)
                if success:
                    bot.reply_to(message, f"✅ **Chat revival frequency set to:** {frequency} minutes")
                else:
                    bot.reply_to(message, "❌ Failed to set revival frequency.")
            except ValueError:
                bot.reply_to(message, "❌ Please provide a valid number for revival frequency!")
                
        elif setup_args in ['premium', 'upgrade']:
            # Premium upgrade
            bot.reply_to(message, """💎 **PREMIUM UPGRADE AVAILABLE!**
*🚧 COMING SOON - Token-Based System! 🚧*

**🚀 Premium Features (Unlock with $BABYGIRL Holdings):**
• **Advanced AI Responses** - Custom training for your community
• **Cross-Group Analytics** - Detailed insights and engagement tracking  
• **Custom Branding** - Your colors, emojis, and personality tweaks
• **Cross-Group Features** - Link multiple communities
• **Priority Support** - Direct access to development team
• **White-Label Options** - Remove Babygirl branding
• **Custom Commands** - Build your own command aliases

**🔥 Enterprise Tier (Large $BABYGIRL Holdings):**
• Everything in Premium
• **Custom Bot Instance** - Your own branded version
• **API Access** - Integrate with your existing tools  
• **Custom Features** - We build what you need
• **Dedicated Support** - Your own success manager
• **Multi-Platform** - Discord, web integration options

**🪙 TOKEN-POWERED UPGRADES:**
• **Pay with $BABYGIRL** - Support the ecosystem while upgrading!
• **Hold to Unlock** - Keep tokens in wallet for ongoing benefits
• **Community Rewards** - Token holders get exclusive features
• **Deflationary Benefits** - Usage burns tokens, increasing value

**🎯 Why Token-Based Upgrades?**
• Support the $BABYGIRL ecosystem directly
• Align community growth with token value
• Exclusive holder benefits and privileges
• True community-owned premium features

**🔮 COMING SOON:**
We're building the token integration system! Follow @babygirlerc for updates on launch!

**🆓 Current Features:** Chat revival, competitions, basic token support remain free forever! 💕""")
            
        elif setup_args == 'help':
            # Setup help
            bot.reply_to(message, """🆘 **SETUP HELP CENTER** 🆘

**🛠️ Configuration Commands:**
• `/setup token TOKEN SYMBOL website.com` - Configure your token
• `/setup narrative "story"` - Add project narrative
• `/setup features "features"` - List key features  
• `/setup values "values"` - Define community values
• `/setup hype "phrases"` - Custom hype phrases
• `/setup goals "goals"` - Project goals and roadmap

**🎭 Personalization:**
• `/emojis add CATEGORY "emoji1,emoji2"` - Custom emoji sets
• `/stickers` - Send stickers to customize my responses
• `/emojis reactions on/off` - Control automatic reactions

**📊 Management:**
• `/setup view` - See all current settings
• `/setup complete` - Finalize configuration
• `/setup reset` - Clear all settings

**💡 Need Examples?**
• `/examples` - See real project configurations
• Join @babygirlerc to see the full system in action!

**🎯 Questions?** Just ask me anything! I'm here to help! 💕""")
            
        else:
            bot.reply_to(message, """❌ **Unknown setup option!**

**🚀 Getting Started:**
• `/setup token TOKENNAME SYMBOL website.com` - Configure your token
• `/setup help` - Detailed help and options

**📋 Step by step configuration:**
• `/setup narrative "your story"`
• `/setup features "key features"`
• `/setup values "community values"`

Use `/setup help` for all available options! 💕""")
    except Exception as e:
        logger.error(f"Error in setup wizard: {e}")
        bot.reply_to(message, "Setup wizard failed! Try again or use `/setup help`")

@bot.message_handler(commands=['examples'])
def setup_examples_command(message):
    """Show real examples of good project configurations"""
    examples_message = """📚 **REAL SETUP EXAMPLES** 📚

Here are examples from successful community setups:

## 🚀 **Example 1: DeFi Project**

**Token:** `/setup token "YieldMax Protocol" YMAX yieldmax.finance`

**Narrative:** `/setup narrative "YieldMax Protocol is pioneering the next generation of yield farming with our innovative auto-compounding vaults and risk-adjusted strategies. We're making DeFi accessible to everyone while maximizing returns through algorithmic optimization."`

**Features:** `/setup features "Auto-compounding yield vaults, multi-chain farming, impermanent loss protection, governance token staking, mobile app integration, security audits by top firms"`

**Values:** `/setup values "Security first, transparency always, community governance, sustainable yields, education and onboarding, long-term value creation"`

**Hype:** `/setup hype "Yields to the moon! Compound those gains! YMAX army strong! Farming never stops! DeFi revolution! Maximum yields maximum vibes!"`

---

## 🎮 **Example 2: Gaming Token**

**Token:** `/setup token "GameFi Universe" GAME gamefi-universe.io`

**Narrative:** `/setup narrative "GameFi Universe is building the ultimate play-to-earn gaming ecosystem where players truly own their assets and can earn real rewards. We're bridging traditional gaming with blockchain technology."`

**Features:** `/setup features "Play-to-earn rewards, NFT character ownership, cross-game asset portability, tournament prizes, guild system, mobile gaming focus"`

**Values:** `/setup values "Player ownership, fair play, community tournaments, supporting gamers, innovation in gaming, fun-first approach"`

**Hype:** `/setup hype "Game on! Play to earn! NFT power! Gaming revolution! GAME token to the stars! Level up your portfolio!"`

---

## 🌍 **Example 3: Community Token**

**Token:** `/setup token "EcoGreen Network" ECO ecogreen.earth`

**Narrative:** `/setup narrative "EcoGreen Network is the sustainable blockchain focused on environmental impact. Every transaction plants trees and supports clean energy projects. We're proof that crypto can heal the planet."`

**Features:** `/setup features "Carbon negative blockchain, tree planting rewards, clean energy funding, eco-project voting, sustainability tracking, green NFT marketplace"`

**Values:** `/setup values "Environmental responsibility, sustainable technology, community impact, transparency in eco projects, supporting green initiatives"`

**Hype:** `/setup hype "Green is the new gold! Plant trees make money! Eco warriors unite! Saving the planet one block at a time! ECO army growing!"`

## 💡 **Key Patterns in Successful Setups:**

✅ **Clear project purpose** in narrative
✅ **Specific features** not just generic benefits  
✅ **Community-focused values** that people can relate to
✅ **Fun, energetic hype phrases** that match your brand
✅ **Authentic voice** that represents your community

**🎯 Ready to create yours? Start with `/setup token` or use `/wizard` for guided setup!**"""

    bot.reply_to(message, examples_message)

@bot.message_handler(commands=['emojis', 'stickers'])
def emojis_stickers_command(message):
    """Configure custom emojis and stickers for the group"""
    try:
        # Check if user is admin
        user_id = str(message.from_user.id)
        group_id = str(message.chat.id)
        
        # Only allow in groups
        if message.chat.type not in ['group', 'supergroup']:
            bot.reply_to(message, "This command only works in groups! Add me to your group and try again.")
            return
            
        # Check if user is admin
        try:
            chat_member = bot.get_chat_member(message.chat.id, message.from_user.id)
            if chat_member.status not in ['administrator', 'creator']:
                bot.reply_to(message, "Only group administrators can configure emojis and stickers! 👑")
                return
        except:
            bot.reply_to(message, "I need admin permissions to check your status!")
            return
        
        command = message.text.split()[0][1:]  # Remove the /
        parts = message.text.split(maxsplit=2)
        
        if command == 'emojis':
            if len(parts) < 2:
                # Show emoji help
                bot.reply_to(message, """🎭 **CUSTOM EMOJI CONFIGURATION** 🎭

**🚀 Available Commands:**
• `/emojis add CATEGORY "emoji1,emoji2,emoji3"` - Add custom emojis
• `/emojis view` - See current emoji configuration
• `/emojis frequency 20` - Set reaction frequency (0-100%)
• `/emojis reactions on/off` - Enable/disable automatic reactions

**📋 Categories:** 
• **general** - Default responses
• **crypto** - Token/crypto discussions
• **relationship** - Dating/romance topics
• **competitive** - Boyfriend competitions
• **happy** - Positive/excited responses
• **sad** - Emotional/down responses

**💡 Example:** 
`/emojis add crypto "🚀,💎,🌙,📈,💰,🔥"`

**✨ How it works:**
• Custom emojis replace defaults in my responses
• I'll automatically react to messages using your emojis
• AI learns which emojis get the best engagement
• Optimization happens every 6 hours automatically""")
                return
                
            action = parts[1]
            
            if action == 'add' and len(parts) == 3:
                # Parse category and emoji list
                add_data = parts[2].strip()
                add_parts = add_data.split(maxsplit=1)
                
                if len(add_parts) < 2:
                    bot.reply_to(message, """❌ **Format:** `/emojis add CATEGORY "emoji1,emoji2,emoji3"`

**Example:** `/emojis add general "💕,✨,😘,💖,🔥,👑,💅"`""")
                    return
                
                category = add_parts[0]
                emoji_list = add_parts[1].replace('"', '').replace("'", '')
                
                # Validate category
                valid_categories = ['general', 'crypto', 'relationship', 'competitive', 'happy', 'sad']
                if category not in valid_categories:
                    bot.reply_to(message, f"❌ Invalid category! Use: {', '.join(valid_categories)}")
                    return
                
                # Store custom emojis
                try:
                    conn = sqlite3.connect('babygirl.db')
                    c = conn.cursor()
                    c.execute("INSERT OR REPLACE INTO custom_emojis (group_id, emoji_set, category, optimization_weight) VALUES (?, ?, ?, 1.0)",
                             (group_id, emoji_list, category))
                    conn.commit()
                    conn.close()
                    
                    bot.reply_to(message, f"""✅ **Custom Emojis Added!**

**Category:** {category}
**Emojis:** {emoji_list}

These emojis will now be used in my responses and reactions for {category} contexts! I'll automatically optimize their usage based on engagement! 🎯""")
                    
                    logger.info(f"🎭 Added custom emojis for {group_id}: {category} = {emoji_list}")
                    
                except Exception as e:
                    logger.error(f"Error storing custom emojis: {e}")
                    bot.reply_to(message, "❌ Failed to save custom emojis.")
                    
            elif action == 'view':
                # View current emoji configuration
                try:
                    conn = sqlite3.connect('babygirl.db')
                    c = conn.cursor()
                    c.execute("SELECT category, emoji_set, usage_count, reaction_count FROM custom_emojis WHERE group_id = ?", (group_id,))
                    emoji_configs = c.fetchall()
                    
                    # Get reaction settings
                    group_settings = get_group_settings(group_id)
                    reaction_freq = group_settings.get('emoji_reaction_frequency', 15) if group_settings else 15
                    reactions_enabled = group_settings.get('auto_reactions_enabled', True) if group_settings else True
                    
                    conn.close()
                    
                    if emoji_configs:
                        view_msg = f"""📋 **Current Emoji Configuration:**

**⚙️ Settings:**
• Reaction Frequency: {reaction_freq}%
• Auto Reactions: {'✅ Enabled' if reactions_enabled else '❌ Disabled'}

**🎭 Custom Emoji Sets:**
"""
                        for category, emoji_set, usage, reactions in emoji_configs:
                            view_msg += f"**{category.title()}:** {emoji_set}\n"
                            view_msg += f"• Used {usage} times in responses, {reactions} as reactions\n\n"
                        
                        view_msg += "**🔧 To Edit:** Use `/emojis add CATEGORY \"new,emojis\"`"
                    else:
                        view_msg = f"""📋 **No Custom Emojis Configured**

**⚙️ Current Settings:**
• Reaction Frequency: {reaction_freq}%
• Auto Reactions: {'✅ Enabled' if reactions_enabled else '❌ Disabled'}

**🚀 Get Started:** 
Use `/emojis add CATEGORY \"emoji1,emoji2\"` to add custom emojis!

**💡 Try:** `/emojis add general \"💕,✨,😘,💖,🔥\"`"""
                    
                    bot.reply_to(message, view_msg)
                    
                except Exception as e:
                    logger.error(f"Error viewing emojis: {e}")
                    bot.reply_to(message, "❌ Failed to load emoji configuration.")
                    
            elif action == 'frequency':
                if len(parts) < 3:
                    bot.reply_to(message, "❌ **Format:** `/emojis frequency 20` (0-100%)")
                    return
                    
                try:
                    frequency = int(parts[2])
                    if frequency < 0 or frequency > 100:
                        bot.reply_to(message, "❌ Frequency must be between 0-100%!")
                        return
                    
                    success = set_group_settings(group_id, user_id, emoji_reaction_frequency=frequency)
                    if success:
                        bot.reply_to(message, f"✅ **Emoji reaction frequency set to:** {frequency}%\n\nI'll react to approximately {frequency}% of messages with custom emojis!")
                    else:
                        bot.reply_to(message, "❌ Failed to set emoji frequency.")
                        
                except ValueError:
                    bot.reply_to(message, "❌ Please provide a valid number for frequency!")
                    
            elif action == 'reactions':
                if len(parts) < 3:
                    bot.reply_to(message, "❌ **Format:** `/emojis reactions on` or `/emojis reactions off`")
                    return
                    
                setting = parts[2].lower()
                if setting == 'on':
                    success = set_group_settings(group_id, user_id, auto_reactions_enabled=True)
                    if success:
                        bot.reply_to(message, "✅ **Automatic emoji reactions ENABLED!** I'll react to messages occasionally! 😘")
                    else:
                        bot.reply_to(message, "❌ Failed to enable reactions.")
                        
                elif setting == 'off':
                    success = set_group_settings(group_id, user_id, auto_reactions_enabled=False)
                    if success:
                        bot.reply_to(message, "✅ **Automatic emoji reactions DISABLED!** I'll focus on text responses only.")
                    else:
                        bot.reply_to(message, "❌ Failed to disable reactions.")
                else:
                    bot.reply_to(message, "❌ Use 'on' or 'off' - example: `/emojis reactions on`")
                    
            else:
                bot.reply_to(message, "❌ Unknown emoji command! Use `/emojis` to see available options.")
                
        elif command == 'stickers':
            if len(parts) < 2:
                # Show sticker help
                bot.reply_to(message, """🎪 **CUSTOM STICKER CONFIGURATION** 🎪

**🚀 How to Add Custom Stickers:**

1. **Get sticker file IDs** from stickers you want to add
2. **Use `/stickers add CATEGORY STICKER_FILE_ID`** to add them manually
3. **Use `/stickers view`** to see your collection
4. **Use `/stickers frequency 15`** to set how often I send them (0-100%)

**🎯 Available Categories:**
• **general** - Normal responses and reactions
• **crypto** - Token discussions and hype
• **relationship** - Romance and dating topics
• **competitive** - Boyfriend competitions and games
• **happy** - Positive and excited responses
• **sad** - Emotional and supportive responses

**📊 Smart Optimization:**
• I automatically track which stickers get the best engagement
• Popular stickers get used more often
• Analytics help optimize personality for your community

**⚡ Commands:**
• `/stickers add general STICKER_FILE_ID` - Add a sticker to category
• `/stickers view` - View your collection
• `/stickers frequency 20` - Set usage frequency (0-100%)

**🎮 Note:** Stickers are added manually through commands, not automatically from uploads.""")
                return
                
            action = parts[1]
            
            if action == 'add':
                if len(parts) < 4:
                    bot.reply_to(message, """❌ **Format:** `/stickers add CATEGORY STICKER_FILE_ID`

**Example:** `/stickers add general BAADBAAHAQADBAADNwAD7YTKFkYAAR...`

**Categories:** general, crypto, relationship, competitive, happy, sad""")
                    return
                
                category = parts[2]
                sticker_file_id = parts[3]
                
                # Validate category
                valid_categories = ['general', 'crypto', 'relationship', 'competitive', 'happy', 'sad']
                if category not in valid_categories:
                    bot.reply_to(message, f"❌ Invalid category! Use: {', '.join(valid_categories)}")
                    return
                
                # Store the sticker
                try:
                    conn = sqlite3.connect('babygirl.db')
                    c = conn.cursor()
                    
                    # Check if sticker already exists
                    c.execute("SELECT sticker_file_id FROM custom_stickers WHERE group_id = ? AND sticker_file_id = ?", (group_id, sticker_file_id))
                    exists = c.fetchone()
                    
                    if not exists:
                        current_time = int(time.time())
                        c.execute("INSERT INTO custom_stickers (group_id, sticker_file_id, sticker_category, added_by, added_date) VALUES (?, ?, ?, ?, ?)",
                                 (group_id, sticker_file_id, category, user_id, current_time))
                        conn.commit()
                        
                        bot.reply_to(message, f"✅ **Sticker Added Successfully!**\n\nCategory: {category}\nI'll start using this sticker in my {category} responses! 🎪")
                        logger.info(f"🎪 Manually added sticker to {group_id}: category={category}")
                    else:
                        bot.reply_to(message, "❌ This sticker is already in my collection!")
                    
                    conn.close()
                    
                except Exception as e:
                    logger.error(f"Error adding sticker: {e}")
                    bot.reply_to(message, "❌ Failed to add sticker. Please check the sticker file ID.")
                    
            elif action == 'view':
                # View current sticker configuration
                try:
                    conn = sqlite3.connect('babygirl.db')
                    c = conn.cursor()
                    c.execute("SELECT sticker_category, COUNT(*) as count, AVG(engagement_score) as avg_score FROM custom_stickers WHERE group_id = ? GROUP BY sticker_category", (group_id,))
                    sticker_stats = c.fetchall()
                    
                    c.execute("SELECT sticker_file_id, sticker_category, usage_count, engagement_score FROM custom_stickers WHERE group_id = ? ORDER BY engagement_score DESC LIMIT 5", (group_id,))
                    top_stickers = c.fetchall()
                    
                    # Get frequency setting
                    group_settings = get_group_settings(group_id)
                    sticker_freq = group_settings.get('sticker_response_frequency', 10) if group_settings else 10
                    
                    conn.close()
                    
                    if sticker_stats:
                        view_msg = f"""📋 **Sticker Collection Status:**

**⚙️ Settings:**
• Sticker Frequency: {sticker_freq}% of responses

**🎪 Collection by Category:**
"""
                        for category, count, avg_score in sticker_stats:
                            view_msg += f"• **{category.title()}:** {count} stickers (avg score: {avg_score:.1f})\n"
                        
                        if top_stickers:
                            view_msg += f"\n**🏆 Top Performing Stickers:**\n"
                            for i, (file_id, category, usage, score) in enumerate(top_stickers, 1):
                                view_msg += f"{i}. {category} sticker - used {usage} times (score: {score:.1f})\n"
                        
                        view_msg += f"\n**🔧 Commands:**\n• `/stickers frequency 20` - Adjust how often I send stickers\n• Send more stickers to expand my collection!"
                    else:
                        view_msg = f"""📋 **No Stickers Configured**

**⚙️ Current Settings:**
• Sticker Frequency: {sticker_freq}% of responses

**🎪 Get Started:**
1. Send me stickers directly in this chat
2. I'll automatically save and categorize them
3. Watch as I start using them in responses!

**💡 Send varied stickers for different moods and topics!**"""
                    
                    bot.reply_to(message, view_msg)
                    
                except Exception as e:
                    logger.error(f"Error viewing stickers: {e}")
                    bot.reply_to(message, "❌ Failed to load sticker configuration.")
                    
            elif action == 'frequency':
                if len(parts) < 3:
                    bot.reply_to(message, "❌ **Format:** `/stickers frequency 15` (0-100%)")
                    return
                    
                try:
                    frequency = int(parts[2])
                    if frequency < 0 or frequency > 100:
                        bot.reply_to(message, "❌ Frequency must be between 0-100%!")
                        return
                    
                    success = set_group_settings(group_id, user_id, sticker_response_frequency=frequency)
                    if success:
                        bot.reply_to(message, f"✅ **Sticker frequency set to:** {frequency}%\n\nI'll include stickers in approximately {frequency}% of my responses!")
                    else:
                        bot.reply_to(message, "❌ Failed to set sticker frequency.")
                        
                except ValueError:
                    bot.reply_to(message, "❌ Please provide a valid number for frequency!")
                    
            else:
                bot.reply_to(message, "❌ Unknown sticker command! Use `/stickers` to see available options.")
        
    except Exception as e:
        logger.error(f"Error in emojis/stickers command: {e}")
        bot.reply_to(message, "Configuration failed! Try again or contact support.")

@bot.message_handler(content_types=['sticker'])
def handle_sticker_uploads(message):
    """Handle sticker uploads - NO automatic processing, admins must use commands"""
    try:
        # DO NOT automatically process stickers or respond to them
        # Stickers should only be added through explicit commands like /stickers add
        
        # If we want to track stickers for potential manual review, we could log them
        # but we should NOT automatically add them or respond to them
        
        group_id = str(message.chat.id)
        
        # Only log in groups, no responses
        if message.chat.type in ['group', 'supergroup']:
            logger.info(f"🎪 Sticker uploaded in group {group_id} - not auto-processed")
        
        # DO NOT respond to sticker uploads automatically
        # Users should use /stickers command for configuration
        
    except Exception as e:
        logger.error(f"Error in sticker handler: {e}")

if __name__ == "__main__":
    logger.info("🚀 Babygirl Bot starting...")
    
    # Initialize scheduler and add jobs
    logger.info("🔧 Setting up scheduled tasks...")
    
    # Add all scheduled jobs
    scheduler.add_job(check_boyfriend_term, 'interval', minutes=1)  # Now handles automatic boyfriend selection
    scheduler.add_job(check_boyfriend_steal_opportunities, 'interval', minutes=5, args=[bot])  # New: boyfriend stealing mechanic
    scheduler.add_job(trigger_challenge, 'interval', minutes=5)
    scheduler.add_job(start_storyline, 'interval', days=3)
    scheduler.add_job(lambda: check_proactive_engagement(bot), 'interval', minutes=15)  # Check every 15 minutes
    scheduler.add_job(lambda: check_proactive_conversation_followups(bot), 'interval', minutes=30)  # New: conversation follow-ups
    scheduler.add_job(optimize_emoji_sticker_usage, 'interval', hours=6)  # Optimize every 6 hours
    
    # Schedule AGGRESSIVE immediate proactive check 10 seconds after startup
    scheduler.add_job(run_immediate_proactive_check, 'date', run_date=datetime.now() + timedelta(seconds=10))
    
    # Schedule follow-up check 5 minutes later to catch any groups that might need additional attention
    scheduler.add_job(run_immediate_proactive_check, 'date', run_date=datetime.now() + timedelta(minutes=5))
    
    # Start the scheduler
    logger.info("🚀 Starting scheduler...")
    scheduler.start()
    logger.info("✅ Scheduler started successfully")
    
    # Verify critical systems
    logger.info("🔍 System verification:")
    logger.info(f"✅ Database initialized")
    logger.info(f"✅ Proactive states initialized")
    logger.info(f"✅ Scheduled jobs active: {len(scheduler.get_jobs())} jobs")
    
    # Option 1: Simple polling (good for testing)
    # bot.polling()
    
    # Option 2: Infinity polling with auto-restart (better for production)
    try:
        logger.info("🎯 Starting bot polling...")
        bot.infinity_polling(none_stop=True)
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        # Restart the bot
        logger.info("🔄 Restarting bot...")
        bot.infinity_polling(none_stop=True) 