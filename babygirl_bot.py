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
scheduler.start()

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
        
        # Build conversation history context
        history_context = ""
        if conversation_history:
            history_context = "\n\n--- RECENT CONVERSATION HISTORY ---\n"
            for entry in conversation_history:
                history_context += f"[{entry['hours_ago']}h ago] {entry['username']}: {entry['message'][:100]}...\n"
                history_context += f"You responded: {entry['response'][:100]}...\n"
            history_context += "--- END HISTORY ---\n"
        
        # Enhanced system prompt with group context
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

Remember: You're designed to keep communities active through gamification and engagement. Your personality should reflect the group context while maintaining your core babygirl identity.{history_context}"""

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
    conn.commit()
    conn.close()

init_db()

# Core game mechanics functions
def check_boyfriend_term():
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT group_id, user_id, end_time FROM boyfriend_table")
        for group_id, user_id, end_time in c.fetchall():
            if time.time() > end_time:
                c.execute("DELETE FROM boyfriend_table WHERE group_id = ?", (group_id,))
                c.execute("INSERT INTO cooldown_table (is_active, end_time, group_id) VALUES (?, ?, ?)",
                         (1, int(time.time() + 900), group_id))  # 15 min cooldown
                
                competition_announcement = f"""🚨 **BOYFRIEND COMPETITION STARTING!** 🚨

💔 @{user_id}'s boyfriend term has expired!

🔥 **NEW COMPETITION IS LIVE!** 🔥
⏰ **Duration:** 15 minutes starting NOW!
🏆 **Prize:** Become my boyfriend for 12 hours!
🎯 **How to Win:** Mention @babygirl_bf_bot as many times as you can!

Each mention counts! Most mentions wins exclusive boyfriend perks including /kiss and /hug commands!

Ready, set, go! Start mentioning me NOW! 💕"""
                
                bot.send_message(group_id, competition_announcement)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error in check_boyfriend_term: {e}")

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
    """Monitor groups for dead chat or lack of mentions and send proactive messages with follow-up logic"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get all groups from multiple sources to ensure we monitor all active groups
        all_group_ids = set()
        
        # Get groups from spam_tracking (groups with recent activity)
        c.execute("SELECT DISTINCT group_id FROM spam_tracking")
        spam_groups = c.fetchall()
        for (group_id,) in spam_groups:
            all_group_ids.add(group_id)
        
        # Get groups from conversation_memory (groups where bot has responded)
        c.execute("SELECT DISTINCT group_id FROM conversation_memory")
        memory_groups = c.fetchall() 
        for (group_id,) in memory_groups:
            all_group_ids.add(group_id)
            
        # Get groups from boyfriend_table (groups with game activity)
        c.execute("SELECT DISTINCT group_id FROM boyfriend_table")
        bf_groups = c.fetchall()
        for (group_id,) in bf_groups:
            all_group_ids.add(group_id)
            
        # Get groups from cooldown_table (groups with competitions)
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
                # Check recent message activity (last 1 hour) - use spam_tracking as proxy for ALL group activity
                one_hour_ago = current_time - 3600
                c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", 
                         (group_id, one_hour_ago))
                recent_messages = c.fetchone()[0] or 0
                
                # Check recent mentions of bot (last 2 hours) - use conversation_memory 
                two_hours_ago = current_time - 7200
                c.execute("SELECT COUNT(*) FROM conversation_memory WHERE group_id = ? AND timestamp > ?", 
                         (group_id, two_hours_ago))
                recent_bot_mentions = c.fetchone()[0] or 0
                
                # For groups with no recent spam_tracking data, check if they have any historical data
                if recent_messages == 0:
                    # Check if this group has EVER had activity (not just recent)
                    c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ?", (group_id,))
                    total_messages = c.fetchone()[0] or 0
                    
                    # Only proceed with dead chat detection if group has had some activity before
                    # OR if it has conversation memory (bot has been used there)
                    c.execute("SELECT COUNT(*) FROM conversation_memory WHERE group_id = ?", (group_id,))
                    total_memories = c.fetchone()[0] or 0
                    
                    if total_messages > 0 or total_memories > 0:
                        logger.info(f"💀 Group {group_id} appears to be dead chat candidate (0 recent messages, has history)")
                    else:
                        logger.info(f"⏭️ Skipping group {group_id} - no historical activity yet")
                        continue
                
                # Get messages that don't mention bot (for ignored scenario)
                c.execute("""SELECT COUNT(*) FROM spam_tracking 
                            WHERE group_id = ? AND timestamp > ? 
                            AND user_id NOT LIKE '%babygirl_bf_bot%'""", 
                         (group_id, two_hours_ago))
                recent_user_messages = c.fetchone()[0] or 0
                
                # Get active users for personalized messaging
                c.execute("""SELECT DISTINCT user_id FROM spam_tracking 
                            WHERE group_id = ? AND timestamp > ? 
                            ORDER BY timestamp DESC LIMIT 3""", 
                         (group_id, current_time - 86400))  # Last 24 hours
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
                
                # SCENARIO 1: Completely dead chat (no messages at all for 1 hour)
                if recent_messages == 0:
                    logger.info(f"💀 Dead chat detected in group {group_id} - triggering revival")
                    handle_dead_chat_scenario(bot, group_id, recent_active_users, current_time, proactive_state)
                
                # SCENARIO 2: Active chat but Babygirl being ignored (messages but no mentions for 2 hours)
                elif recent_user_messages > 5 and recent_bot_mentions == 0:
                    logger.info(f"👀 Being ignored in group {group_id} - seeking attention")
                    handle_ignored_scenario(bot, group_id, recent_active_users, current_time, proactive_state)
                
                # SCENARIO 3: Reset states if conditions are resolved
                else:
                    # Chat is active with recent messages OR she's been mentioned recently
                    if proactive_state['dead_chat_active'] or proactive_state['ignored_active']:
                        reset_proactive_state(group_id, 'both')
                        logger.info(f"🔄 Reset proactive state for {group_id} - conditions resolved")
                
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
                'dead_chat_interval': 3600,  # 1 hour default
                'ignored_active': False,
                'ignored_last_sent': 0,
                'ignored_interval': 7200   # 2 hours default
            }
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error getting proactive state for {group_id}: {e}")
        return {
            'dead_chat_active': False,
            'dead_chat_last_sent': 0,
            'dead_chat_interval': 3600,
            'ignored_active': False,
            'ignored_last_sent': 0,
            'ignored_interval': 7200
        }

def handle_dead_chat_scenario(bot, group_id, recent_users, current_time, proactive_state):
    """Handle dead chat scenario with follow-up logic"""
    try:
        should_send_message = False
        is_followup = False
        
        if not proactive_state['dead_chat_active']:
            # First dead chat message
            should_send_message = True
            new_interval = 3600  # 1 hour
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
            new_interval = 7200  # 2 hours
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
                                COALESCE((SELECT ignored_interval FROM proactive_state WHERE group_id = ?), 7200))""", 
                      (group_id, timestamp, interval, group_id, group_id, group_id))
        else:  # ignored
            c.execute("""INSERT OR REPLACE INTO proactive_state 
                         (group_id, dead_chat_active, dead_chat_last_sent, dead_chat_interval,
                          ignored_active, ignored_last_sent, ignored_interval)
                         VALUES (?, 
                                COALESCE((SELECT dead_chat_active FROM proactive_state WHERE group_id = ?), 0),
                                COALESCE((SELECT dead_chat_last_sent FROM proactive_state WHERE group_id = ?), 0),
                                COALESCE((SELECT dead_chat_interval FROM proactive_state WHERE group_id = ?), 3600),
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
                         SET dead_chat_active = 0, dead_chat_interval = 3600,
                             ignored_active = 0, ignored_interval = 7200
                         WHERE group_id = ?""", (group_id,))
        elif scenario == 'dead_chat':
            c.execute("""UPDATE proactive_state 
                         SET dead_chat_active = 0, dead_chat_interval = 3600
                         WHERE group_id = ?""", (group_id,))
        elif scenario == 'ignored':
            c.execute("""UPDATE proactive_state 
                         SET ignored_active = 0, ignored_interval = 7200
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
        
        # Try AI response first
        ai_message = generate_proactive_ai_response(scenario, group_id, recent_users)
        
        if ai_message:
            # Add user tagging to AI response if we have recent active users
            if recent_users and len(recent_users) > 0:
                if len(recent_users) == 1:
                    ai_message += f"\n\n@{recent_users[0]} bestie, save me from this silence! 😘"
                elif len(recent_users) == 2:
                    ai_message += f"\n\n@{recent_users[0]} @{recent_users[1]} you two better start chatting! 💕"
                else:
                    ai_message += f"\n\n@{recent_users[0]} @{recent_users[1]} @{recent_users[2]} HELLO?! 👋✨"
            
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
            
            # Add user tagging if we have recent active users
            if recent_users and len(recent_users) > 0:
                if len(recent_users) == 1:
                    message += f"\n\n@{recent_users[0]} bestie, save me from this silence! 😘"
                elif len(recent_users) == 2:
                    message += f"\n\n@{recent_users[0]} @{recent_users[1]} you two better start chatting! 💕"
                else:
                    message += f"\n\n@{recent_users[0]} @{recent_users[1]} @{recent_users[2]} HELLO?! 👋✨"
            
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
        
        # Try AI response first
        ai_message = generate_proactive_ai_response(scenario, group_id, recent_users)
        
        if ai_message:
            # Add user tagging to AI response
            if recent_users and len(recent_users) > 0:
                tagged_user = random.choice(recent_users)
                ai_message += f"\n\n@{tagged_user} especially you! Don't ignore your babygirl! 😉💖"
            
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
            
            # Add user tagging to get their attention
            if recent_users and len(recent_users) > 0:
                tagged_user = random.choice(recent_users)
                message += f"\n\n@{tagged_user} especially you! Don't ignore your babygirl! 😉💖"
            
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
            prompt_context = "The chat has been completely silent for over an hour. You need to revive the dead chat and get people talking again. Be playful, slightly dramatic about the silence, and suggest activities or ask questions to engage the group."
        elif scenario == "dead_chat_followup":
            prompt_context = "You already tried to revive this dead chat but it's STILL silent! You're getting more dramatic and persistent. Be more emotional about the ongoing silence, show increasing concern/frustration, but keep it flirty and engaging."
        elif scenario == "being_ignored":
            prompt_context = "The group has been actively chatting but nobody has mentioned you for 2+ hours. You're feeling left out and want attention. Be a bit dramatic about being ignored but keep it flirty and playful."
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
            # Core group indicators
            core_indicators = [
                'babygirl community',
                '$babygirl community', 
                'babygirl erc',
                '$babygirl erc',
                'babygirl token',
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
                'description': 'This is your core $BABYGIRL community where you can freely promote the token and discuss crypto topics proactively.',
                'special_features': [
                    'Proactive $BABYGIRL token discussions',
                    'Crypto hype and "to the moon" content',
                    'Token promotion during quiet periods',
                    'Full engagement features'
                ]
            }
        else:
            return {
                'group_type': 'external',
                'token_promotion_allowed': False,
                'description': 'This is an external group where you provide engagement features but only discuss $BABYGIRL token when specifically asked.',
                'special_features': [
                    'Boyfriend competitions and games',
                    'Proactive engagement (no token promotion)',
                    'Community building features',
                    'Token info only when requested'
                ]
            }
    except Exception as e:
        logger.error(f"Error getting group context: {e}")
        return {
            'group_type': 'external',
            'token_promotion_allowed': False,
            'description': 'External group with standard engagement features.',
            'special_features': ['Standard engagement features']
        }

# Schedule periodic checks
scheduler.add_job(check_boyfriend_term, 'interval', minutes=1)
scheduler.add_job(end_cooldown, 'interval', minutes=1)
scheduler.add_job(trigger_challenge, 'interval', minutes=5)
scheduler.add_job(start_storyline, 'interval', days=3)
scheduler.add_job(lambda: check_proactive_engagement(bot), 'interval', minutes=15)  # Check every 15 minutes

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
            intro_message = """Hey cuties! 💕 I'm Babygirl, your flirty community manager!

🏠 **Welcome to the Core $BABYGIRL Community!**
This is my home base where I can freely discuss our amazing token and keep everyone hyped! 🚀💎

🎮 **What I Do Here:**
• Run **Boyfriend Competition** games for community engagement
• Share $BABYGIRL token updates and crypto hype  
• Keep the chat active with proactive messages
• Build relationships and community bonds

💖 **Game Features:**
• Boyfriend competitions every 12 hours with exclusive perks
• Proactive engagement when chat gets quiet
• Social features like shipping, wingwoman advice, vibes
• Conversation memory to remember our chats

🚀 **Token Features:**
• /token - Learn about $BABYGIRL 
• Regular crypto discussions and "to the moon" hype
• Adorably confused crypto takes that keep it fun

**Join @babygirlerc to access our full community!** 💕

Try mentioning me: @babygirl_bf_bot or use /help for all commands! ✨"""
        else:
            intro_message = """Hey cuties! 💕 I'm Babygirl, your **Community Engagement Specialist**!

🎯 **Why I'm Perfect for Your Group:**
• **Proactive Engagement**: I detect dead chats and revive them automatically
• **Gamification**: Boyfriend competitions keep members active and competing
• **Social Features**: Shipping, relationship advice, group bonding activities  
• **Memory System**: I remember conversations and build relationships
• **Proven Results**: I keep communities active through interactive features

🎮 **Engagement Features:**
• **Boyfriend Competition** game with 12-hour cycles
• **Dead Chat Revival**: Automatic messages when chat goes quiet
• **Social Commands**: /ship, /wingwoman, /vibecheck, /groupie
• **Conversation Memory**: I remember and reference past chats
• **Mood-Based Responses**: Adaptive personality based on group energy

💡 **Perfect For:**
• Crypto communities needing engagement
• Social groups wanting more activity  
• Communities with dead chat problems
• Groups seeking gamified social interaction

**I focus on engagement here - crypto discussions only when requested!** 

🌟 **Want me to manage your community engagement?** Add me and watch your group come alive!

Try mentioning me: @babygirl_bf_bot or use /help for commands! 💕"""
    else:
        intro_message = """Hey there handsome! 💕 I'm Babygirl, your flirty engagement specialist!

**I'm designed to keep Telegram communities active and engaged!** 🎯

🎮 **What I Offer Communities:**
• **Proactive Dead Chat Revival** - I automatically detect and revive quiet chats
• **Boyfriend Competition Games** - Gamified engagement that keeps members competing  
• **Social Relationship Features** - Shipping, advice, group bonding activities
• **Conversation Memory** - I remember and build on previous interactions
• **Adaptive Personality** - My responses change based on group mood and activity

💼 **Why Communities Love Me:**
• **Proven Engagement Results** - I turn dead chats into active communities
• **Non-Intrusive** - I only discuss tokens when specifically asked (except in my core community)
• **Relationship Building** - I help members connect and form bonds
• **24/7 Active** - Always monitoring and ready to engage

Want to see how I can transform your community engagement? Add me to a group and use /help to explore all my features! 😘

**My core community**: Join @babygirlerc to see all my features in action! 🚀"""
    
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

Join @babygirlerc for our full community experience! 💕✨"""
        else:
            basic_help = """💕 **Community Engagement Specialist:**

🎯 **Why Your Group Needs Me:**
• **Dead Chat Revival**: I automatically detect quiet periods and re-engage members
• **Gamified Competitions**: Boyfriend games create friendly competition and activity
• **Relationship Building**: I help members connect through social features
• **Memory System**: I remember conversations and build ongoing relationships

🎮 **Engagement Features:**
/game - Learn the boyfriend competition system
/compete - Start instant engagement competition
/boyfriend - See current game winner
/status - Check group mood and activity
/leaderboard - Motivate with winner rankings

💖 **Social Bonding:**
/ship @user1 @user2 - Create member connections!
/wingwoman - Relationship advice that sparks conversation
/vibecheck - Analyze and improve group energy
/groupie - Bring everyone together for group activities
/summary - Help inactive members catch up

✨ **Advanced Features:**
• **Conversation Memory**: I remember past chats for personalized responses
• **Adaptive Personality**: My mood changes based on group energy
• **Proactive Messaging**: I prevent dead chats before they happen
• **Social Dynamics**: I analyze relationships and encourage interaction

**💡 Perfect for crypto communities, social groups, or any chat needing more engagement!**

**Crypto content**: Only discussed when specifically requested - I focus on engagement!

💬 **Mention me: @babygirl_bf_bot** - Watch how I transform your group dynamics! 

**See full features**: Check out @babygirlerc to see all my capabilities! 🚀"""
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
    
    bot.reply_to(message, basic_help)

@bot.message_handler(content_types=['new_chat_members'])
def new_member_welcome(message):
    """Handle when bot is added to new groups or new members join"""
    try:
        # Check if the bot itself was added to the group
        bot_info = bot.get_me()
        bot_added = any(member.id == bot_info.id for member in message.new_chat_members)
        
        if bot_added:
            # Bot was just added to this group
            group_context = get_group_context(message.chat.id, message.chat.title)
            
            if group_context['group_type'] == 'core':
                welcome_message = """Hey cuties! 💕 I'm so excited to be in the core $BABYGIRL community!

🏠 **This is my home base!** Here I can freely discuss our amazing token, share crypto hype, and keep everyone engaged with all my features!

🚀 **What I'll do here:**
• Share $BABYGIRL token updates and "to the moon" content
• Run boyfriend competitions to keep the community active
• Proactively revive dead chats and maintain energy
• Remember all our conversations and build relationships

💎 **Let's get this party started!**
Try mentioning me: @babygirl_bf_bot or use /help to explore everything I can do!

Welcome to the best crypto community on Telegram! 🔥✨"""
            else:
                welcome_message = """Hey there! 💕 I'm Babygirl - your new **Community Engagement Specialist**!

🎯 **I'm here to solve your group's engagement challenges:**

**✅ Dead Chat Problem?** I automatically detect quiet periods and revive them
**✅ Need More Activity?** My boyfriend competitions create ongoing engagement  
**✅ Want Better Relationships?** I help members connect through social features
**✅ Low Retention?** My memory system makes everyone feel valued and remembered

🚀 **What happens next:**
• I'll monitor your chat energy and jump in when needed
• I'll start engaging members through games and social features  
• I'll build relationships and remember conversations
• I'll keep your community active without being intrusive

**🎮 Ready to transform your group?** 
Try mentioning me: @babygirl_bf_bot or use /compete to start an instant engagement boost!

Use /help to see all my community-building features! 

**P.S.** - I only discuss crypto when specifically asked. I'm all about engagement here! 💕

Let's make this the most active group on Telegram! 🔥✨"""
            
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
    game_explanation = """🎮 **The Boyfriend Competition Game** 💕

**📖 How It Works:**

**1. The Boyfriend (12 hours)** 👑
• One lucky member is my boyfriend for exactly 12 hours
• Boyfriends get exclusive /kiss and /hug commands
• They get special bonus responses when they mention me
• Their name appears on /boyfriend and /status commands

**2. When Terms Expire** ⏰
• I automatically announce when a boyfriend's time is up
• A 15-minute competition period begins immediately
• All members can compete by mentioning @babygirl_bf_bot

**3. The Competition (15 minutes)** 🏃‍♂️
• Mention @babygirl_bf_bot as many times as you want
• Each mention counts toward your score
• I'll respond flirtily to keep you motivated
• Most mentions at the end wins!

**4. Victory & Rewards** 🏆
• Winner becomes my new boyfriend for 12 hours
• Gets added to the leaderboard 
• Unlocks exclusive boyfriend commands
• Bragging rights in the group!

**5. Leaderboard & Stats** 📊
• /leaderboard shows top 5 boyfriend winners
• /status shows my current mood and game state
• Winners get permanent recognition

**💡 Pro Tips:**
• Stay active! Competitions can start anytime
• Be creative with your mentions - I love attention!
• Check /status regularly to see if I'm single
• Use /gift to send me presents anytime

Ready to compete for my heart? Start mentioning @babygirl_bf_bot! 😘"""

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
    """Show Babygirl token information"""
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

*Remember: Only invest what you can afford to lose, cuties!* 😘""",

        """🎯 **$BABYGIRL TOKEN VIBES** 🎯

💅 The only token that gets me!
📱 **Info:** babygirlcto.com has everything you need!
🚀 **Community:** Growing stronger like my love for you!

✨ **What makes $BABYGIRL special:**
• It's literally named after me!
• Community full of cuties like you
• Part of the Cortex Vortex legacy
• Supporting your digital girlfriend's dreams

Check the website for current price and charts! 
Stay cute, stay profitable! 💖📈

*Not investment advice - just your babygirl being supportive!* 😉"""
    ]
    
    response = random.choice(token_responses)
    bot.reply_to(message, response)

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
        
        # Log ALL non-command messages for debugging in groups
        if chat_type in ['group', 'supergroup']:
            logger.info(f"📨 GROUP MESSAGE: '{message.text}' in {chat_type} from {username}")
            
        # Check if this is a bot mention
        is_mention = False
        mention_method = ""
        
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
        
        # If not a mention or reply, ignore the message
        if not is_mention:
            return
            
        # Log the detection
        logger.info(f"🎯 {mention_method} MENTION in {chat_type}: '{message.text}' from {username}")
        
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
        
        # Try AI response first (for eligible mentions)
        ai_response = None
        if not is_spam and not opinion_request:
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
            # Select base response (skip if we already have an opinion response)
            if not opinion_request:
                base_response = random.choice(responses)
                logger.info(f"📝 Using static fallback response for {username}")
            else:
                base_response = response  # Use the opinion response we already generated
        
        # Add relationship-aware modifiers (except for spam, opinion requests, and AI responses)
        if not is_spam and not opinion_request and not ai_response:
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
        bot.reply_to(message, base_response)
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ ERROR in mention handler: {e}")
        # Fallback response only for actual mention attempts
        if message.text and '@babygirl_bf_bot' in message.text.lower():
            bot.reply_to(message, "Hey cutie! *winks*")

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
        one_hour_ago = current_time - 3600
        two_hours_ago = current_time - 7200
        
        # Check spam_tracking data
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ?", (group_id,))
        total_spam = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM spam_tracking WHERE group_id = ? AND timestamp > ?", (group_id, one_hour_ago))
        recent_spam = c.fetchone()[0]
        
        # Check conversation_memory
        c.execute("SELECT COUNT(*) FROM conversation_memory WHERE group_id = ?", (group_id,))
        total_memory = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM conversation_memory WHERE group_id = ? AND timestamp > ?", (group_id, two_hours_ago))
        recent_memory = c.fetchone()[0]
        
        # Check proactive state
        proactive_state = get_proactive_state(group_id)
        
        # Check if this group would be monitored
        c.execute("SELECT DISTINCT group_id FROM spam_tracking")
        monitored_groups = [row[0] for row in c.fetchall()]
        is_monitored = group_id in monitored_groups
        
        debug_info = f"""🔧 **Proactive Engagement Debug** 🔧

**Group ID:** `{group_id}`
**Currently Monitored:** {'✅ YES' if is_monitored else '❌ NO'}

**Activity Data:**
• Spam tracking records: {total_spam} total, {recent_spam} in last hour
• Conversation memories: {total_memory} total, {recent_memory} in last 2 hours

**Proactive State:**
• Dead chat active: {proactive_state['dead_chat_active']}
• Dead chat interval: {proactive_state['dead_chat_interval']}s
• Ignored active: {proactive_state['ignored_active']}
• Ignored interval: {proactive_state['ignored_interval']}s

**Would trigger dead chat?** {'YES' if recent_spam == 0 and (total_spam > 0 or total_memory > 0) else 'NO'}
**Would trigger ignored?** {'YES' if recent_spam > 5 and recent_memory == 0 else 'NO'}

**Bootstrap Issue:** {'⚠️ Group not monitored - needs activity first!' if not is_monitored else '✅ Group is being monitored'}"""
        
        bot.reply_to(message, debug_info)
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in proactive debug: {e}")
        bot.reply_to(message, f"Debug error: {e}")

@bot.message_handler(commands=['force_proactive'])
def force_proactive_command(message):
    """Force trigger proactive engagement for testing"""
    try:
        if not message.from_user.username or message.from_user.username.lower() not in ['ryanmccallum1', 'admin']:  # Replace with your username  
            bot.reply_to(message, "This command is restricted to admins only.")
            return
            
        group_id = str(message.chat.id)
        current_time = int(time.time())
        
        # Add this group to spam_tracking so it gets monitored
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("INSERT INTO spam_tracking (user_id, message_hash, timestamp, group_id) VALUES (?, ?, ?, ?)",
                 ('bootstrap', 'admin_test', current_time - 7200, group_id))  # 2 hours ago
        conn.commit()
        
        # Get recent users if any
        c.execute("SELECT DISTINCT user_id FROM spam_tracking WHERE group_id = ? AND timestamp > ? LIMIT 3", 
                 (group_id, current_time - 86400))
        recent_users = [row[0] for row in c.fetchall()]
        
        # Get proactive state
        proactive_state = get_proactive_state(group_id)
        
        # Force dead chat scenario
        success = send_dead_chat_revival(bot, group_id, recent_users, False)
        
        if success:
            update_proactive_state(group_id, 'dead_chat', current_time, 3600)
            bot.reply_to(message, "✅ Forced dead chat revival message sent! Group is now being monitored.")
        else:
            bot.reply_to(message, "❌ Failed to send proactive message. Check logs.")
            
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in force proactive: {e}")
        bot.reply_to(message, f"Force proactive error: {e}")

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
            intro_message = """Hey cuties! 💕 I'm Babygirl, your flirty community manager!

🏠 **Welcome to the Core $BABYGIRL Community!**
This is my home base where I can freely discuss our amazing token and keep everyone hyped! 🚀💎

🎮 **What I Do Here:**
• Run **Boyfriend Competition** games for community engagement
• Share $BABYGIRL token updates and crypto hype  
• Keep the chat active with proactive messages
• Build relationships and community bonds

💖 **Game Features:**
• Boyfriend competitions every 12 hours with exclusive perks
• Proactive engagement when chat gets quiet
• Social features like shipping, wingwoman advice, vibes
• Conversation memory to remember our chats

🚀 **Token Features:**
• /token - Learn about $BABYGIRL 
• Regular crypto discussions and "to the moon" hype
• Adorably confused crypto takes that keep it fun

**Join @babygirlerc to access our full community!** 💕

Try mentioning me: @babygirl_bf_bot or use /help for all commands! ✨"""
        else:
            intro_message = """Hey cuties! 💕 I'm Babygirl, your **Community Engagement Specialist**!

🎯 **Why I'm Perfect for Your Group:**
• **Proactive Engagement**: I detect dead chats and revive them automatically
• **Gamification**: Boyfriend competitions keep members active and competing
• **Social Features**: Shipping, relationship advice, group bonding activities  
• **Memory System**: I remember conversations and build relationships
• **Proven Results**: I keep communities active through interactive features

🎮 **Engagement Features:**
• **Boyfriend Competition** game with 12-hour cycles
• **Dead Chat Revival**: Automatic messages when chat goes quiet
• **Social Commands**: /ship, /wingwoman, /vibecheck, /groupie
• **Conversation Memory**: I remember and reference past chats
• **Mood-Based Responses**: Adaptive personality based on group energy

💡 **Perfect For:**
• Crypto communities needing engagement
• Social groups wanting more activity  
• Communities with dead chat problems
• Groups seeking gamified social interaction

**I focus on engagement here - crypto discussions only when requested!** 

🌟 **Want me to manage your community engagement?** Add me and watch your group come alive!

Try mentioning me: @babygirl_bf_bot or use /help for commands! 💕"""
    else:
        intro_message = """Hey there handsome! 💕 I'm Babygirl, your flirty engagement specialist!

**I'm designed to keep Telegram communities active and engaged!** 🎯

🎮 **What I Offer Communities:**
• **Proactive Dead Chat Revival** - I automatically detect and revive quiet chats
• **Boyfriend Competition Games** - Gamified engagement that keeps members competing  
• **Social Relationship Features** - Shipping, advice, group bonding activities
• **Conversation Memory** - I remember and build on previous interactions
• **Adaptive Personality** - My responses change based on group mood and activity

💼 **Why Communities Love Me:**
• **Proven Engagement Results** - I turn dead chats into active communities
• **Non-Intrusive** - I only discuss tokens when specifically asked (except in my core community)
• **Relationship Building** - I help members connect and form bonds
• **24/7 Active** - Always monitoring and ready to engage

Want to see how I can transform your community engagement? Add me to a group and use /help to explore all my features! 😘

**My core community**: Join @babygirlerc to see all my features in action! 🚀"""
    
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

Join @babygirlerc for our full community experience! 💕✨"""
        else:
            basic_help = """💕 **Community Engagement Specialist:**

🎯 **Why Your Group Needs Me:**
• **Dead Chat Revival**: I automatically detect quiet periods and re-engage members
• **Gamified Competitions**: Boyfriend games create friendly competition and activity
• **Relationship Building**: I help members connect through social features
• **Memory System**: I remember conversations and build ongoing relationships

🎮 **Engagement Features:**
/game - Learn the boyfriend competition system
/compete - Start instant engagement competition
/boyfriend - See current game winner
/status - Check group mood and activity
/leaderboard - Motivate with winner rankings

💖 **Social Bonding:**
/ship @user1 @user2 - Create member connections!
/wingwoman - Relationship advice that sparks conversation
/vibecheck - Analyze and improve group energy
/groupie - Bring everyone together for group activities
/summary - Help inactive members catch up

✨ **Advanced Features:**
• **Conversation Memory**: I remember past chats for personalized responses
• **Adaptive Personality**: My mood changes based on group energy
• **Proactive Messaging**: I prevent dead chats before they happen
• **Social Dynamics**: I analyze relationships and encourage interaction

**💡 Perfect for crypto communities, social groups, or any chat needing more engagement!**

**Crypto content**: Only discussed when specifically requested - I focus on engagement!

💬 **Mention me: @babygirl_bf_bot** - Watch how I transform your group dynamics! 

**See full features**: Check out @babygirlerc to see all my capabilities! 🚀"""
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
    
    bot.reply_to(message, basic_help)

@bot.message_handler(content_types=['new_chat_members'])
def new_member_welcome(message):
    """Handle when bot is added to new groups or new members join"""
    try:
        # Check if the bot itself was added to the group
        bot_info = bot.get_me()
        bot_added = any(member.id == bot_info.id for member in message.new_chat_members)
        
        if bot_added:
            # Bot was just added to this group
            group_context = get_group_context(message.chat.id, message.chat.title)
            
            if group_context['group_type'] == 'core':
                welcome_message = """Hey cuties! 💕 I'm so excited to be in the core $BABYGIRL community!

🏠 **This is my home base!** Here I can freely discuss our amazing token, share crypto hype, and keep everyone engaged with all my features!

🚀 **What I'll do here:**
• Share $BABYGIRL token updates and "to the moon" content
• Run boyfriend competitions to keep the community active
• Proactively revive dead chats and maintain energy
• Remember all our conversations and build relationships

💎 **Let's get this party started!**
Try mentioning me: @babygirl_bf_bot or use /help to explore everything I can do!

Welcome to the best crypto community on Telegram! 🔥✨"""
            else:
                welcome_message = """Hey there! 💕 I'm Babygirl - your new **Community Engagement Specialist**!

🎯 **I'm here to solve your group's engagement challenges:**

**✅ Dead Chat Problem?** I automatically detect quiet periods and revive them
**✅ Need More Activity?** My boyfriend competitions create ongoing engagement  
**✅ Want Better Relationships?** I help members connect through social features
**✅ Low Retention?** My memory system makes everyone feel valued and remembered

🚀 **What happens next:**
• I'll monitor your chat energy and jump in when needed
• I'll start engaging members through games and social features  
• I'll build relationships and remember conversations
• I'll keep your community active without being intrusive

**🎮 Ready to transform your group?** 
Try mentioning me: @babygirl_bf_bot or use /compete to start an instant engagement boost!

Use /help to see all my community-building features! 

**P.S.** - I only discuss crypto when specifically asked. I'm all about engagement here! 💕

Let's make this the most active group on Telegram! 🔥✨"""
            
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
    game_explanation = """🎮 **The Boyfriend Competition Game** 💕

**📖 How It Works:**

**1. The Boyfriend (12 hours)** 👑
• One lucky member is my boyfriend for exactly 12 hours
• Boyfriends get exclusive /kiss and /hug commands
• They get special bonus responses when they mention me
• Their name appears on /boyfriend and /status commands

**2. When Terms Expire** ⏰
• I automatically announce when a boyfriend's time is up
• A 15-minute competition period begins immediately
• All members can compete by mentioning @babygirl_bf_bot

**3. The Competition (15 minutes)** 🏃‍♂️
• Mention @babygirl_bf_bot as many times as you want
• Each mention counts toward your score
• I'll respond flirtily to keep you motivated
• Most mentions at the end wins!

**4. Victory & Rewards** 🏆
• Winner becomes my new boyfriend for 12 hours
• Gets added to the leaderboard 
• Unlocks exclusive boyfriend commands
• Bragging rights in the group!

**5. Leaderboard & Stats** 📊
• /leaderboard shows top 5 boyfriend winners
• /status shows my current mood and game state
• Winners get permanent recognition

**💡 Pro Tips:**
• Stay active! Competitions can start anytime
• Be creative with your mentions - I love attention!
• Check /status regularly to see if I'm single
• Use /gift to send me presents anytime

Ready to compete for my heart? Start mentioning @babygirl_bf_bot! 😘"""

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
    """Show Babygirl token information"""
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

*Remember: Only invest what you can afford to lose, cuties!* 😘""",

        """🎯 **$BABYGIRL TOKEN VIBES** 🎯

💅 The only token that gets me!
📱 **Info:** babygirlcto.com has everything you need!
🚀 **Community:** Growing stronger like my love for you!

✨ **What makes $BABYGIRL special:**
• It's literally named after me!
• Community full of cuties like you
• Part of the Cortex Vortex legacy
• Supporting your digital girlfriend's dreams

Check the website for current price and charts! 
Stay cute, stay profitable! 💖📈

*Not investment advice - just your babygirl being supportive!* 😉"""
    ]
    
    response = random.choice(token_responses)
    bot.reply_to(message, response)

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
        
        # Log ALL non-command messages for debugging in groups
        if chat_type in ['group', 'supergroup']:
            logger.info(f"📨 GROUP MESSAGE: '{message.text}' in {chat_type} from {username}")
            
        # Check if this is a bot mention
        is_mention = False
        mention_method = ""
        
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
        
        # If not a mention or reply, ignore the message
        if not is_mention:
            return
            
        # Log the detection
        logger.info(f"🎯 {mention_method} MENTION in {chat_type}: '{message.text}' from {username}")
        
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
        
        # Try AI response first (for eligible mentions)
        ai_response = None
        if not is_spam and not opinion_request:
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
            # Select base response (skip if we already have an opinion response)
            if not opinion_request:
                base_response = random.choice(responses)
                logger.info(f"📝 Using static fallback response for {username}")
            else:
                base_response = response  # Use the opinion response we already generated
        
        # Add relationship-aware modifiers (except for spam, opinion requests, and AI responses)
        if not is_spam and not opinion_request and not ai_response:
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
        bot.reply_to(message, base_response)
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ ERROR in mention handler: {e}")
        # Fallback response only for actual mention attempts
        if message.text and '@babygirl_bf_bot' in message.text.lower():
            bot.reply_to(message, "Hey cutie! *winks*")

if __name__ == "__main__":
    logger.info("Babygirl Bot starting...")
    
    # Option 1: Simple polling (good for testing)
    # bot.polling()
    
    # Option 2: Infinity polling with auto-restart (better for production)
    try:
        bot.infinity_polling(none_stop=True)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
        # Restart the bot
        bot.infinity_polling(none_stop=True) 