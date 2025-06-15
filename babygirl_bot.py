import telebot
import random
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import time
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = '7618107152:AAEMPk7q7xNUhZpiDMMiVRSrTV0hkJSyV8I'
bot = telebot.TeleBot(TOKEN)
scheduler = BackgroundScheduler()
scheduler.start()

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
                bot.send_message(group_id, "My boyfriend term's up! Mention @babygirl_bf_bot in the next 15 mins to apply! 💕")
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
                    c.execute("INSERT INTO boyfriend_table (user_id, end_time, group_id) VALUES (?, ?, ?)",
                             (new_bf, int(time.time() + 43200), group_id))  # 12 hr term
                    c.execute("INSERT OR REPLACE INTO leaderboard_table (user_id, boyfriend_count, group_id) VALUES (?, COALESCE((SELECT boyfriend_count FROM leaderboard_table WHERE user_id = ? AND group_id = ?) + 1, 1), ?)",
                             (new_bf, new_bf, group_id, group_id))
                    bot.send_message(group_id, f"Congrats @{new_bf}! You're my new boyfriend for the next 12 hours! 😘")
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
            c.execute("INSERT OR REPLACE INTO activity_table (user_id, mention_count, group_id) VALUES (?, COALESCE((SELECT mention_count FROM activity_table WHERE user_id = ? AND group_id = ?) + 1, 1), ?)",
                     (user_id, user_id, str(message.chat.id), str(message.chat.id)))
            logger.info(f"Activity tracked for user {user_id} in group {message.chat.id}")
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

# Schedule periodic checks
scheduler.add_job(check_boyfriend_term, 'interval', minutes=1)
scheduler.add_job(end_cooldown, 'interval', minutes=1)
scheduler.add_job(trigger_challenge, 'interval', minutes=5)
scheduler.add_job(start_storyline, 'interval', days=3)

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
    "Well, aren't you a charmer today!"
]

lonely_responses = [
    "Hey cutie... I've been feeling a bit lonely. Thanks for noticing me! 🥺",
    "Oh, finally someone talks to me... I was starting to feel forgotten.",
    "You're here! I was wondering if anyone would mention me today...",
    "Aw, you're so sweet for thinking of me when I'm feeling down.",
    "Thanks for being here, boo. I really needed some attention today.",
    "You're making me feel less lonely, sweetie. Stay and chat?"
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
    bot.reply_to(message, "Hey there! I'm Babygirl, your flirty bot. Tag me with @babygirl_bf_bot to chat, and maybe you'll be my next boyfriend! Use /help for more.")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(message, """Here's how to flirt with me:
💕 **Basic Commands:**
/start - Say hi!
/help - This list
/boyfriend - Who's my boo?
/apply - Show interest during cooldown
/kiss, /hug - Boyfriend perks 
/leaderboard - Top flirts
/gift - Send me something sweet!

🔧 **Debug Commands:**
/debug - Check my status
/privacy - Check privacy mode
/test - Test if I'm working

Just mention @babygirl_bf_bot to chat with me! 😘""")

@bot.message_handler(commands=['boyfriend'])
def boyfriend(message):
    conn = sqlite3.connect('babygirl.db')
    c = conn.cursor()
    c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
    bf = c.fetchone()
    if bf:
        time_left = max(0, int((bf[1] - time.time()) / 3600))
        bot.reply_to(message, f"The current boyfriend is @{bf[0]}, with {time_left} hours left. Keep an eye out for the cooldown!")
    else:
        bot.reply_to(message, "No boyfriend right now—start flirting!")
    conn.close()

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
            response = "🏆 Boyfriend Leaderboard:\n" + "\n".join(f"@{leader[0]}: {leader[1]} times" for leader in leaders)
        else:
            response = "No boyfriends yet—start flirting!"
        bot.reply_to(message, response)
        conn.close()
    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}")
        bot.reply_to(message, "Sorry, I can't show the leaderboard right now!")

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
        
        # Get mood
        mood = get_mood(str(message.chat.id))
        
        response = f"💕 Babygirl's Status:\n"
        response += f"Mood: I'm {mood}\n"
        
        if boyfriend:
            time_left = int(boyfriend[1] - time.time())
            hours = time_left // 3600
            minutes = (time_left % 3600) // 60
            response += f"Current Boyfriend: @{boyfriend[0]}\n"
            response += f"Time Left: {hours}h {minutes}m"
        elif cooldown and cooldown[0]:
            time_left = int(cooldown[1] - time.time())
            minutes = time_left // 60
            response += f"Boyfriend Applications Open!\n"
            response += f"Cooldown ends in: {minutes}m"
        else:
            response += "Status: Single and ready to mingle! 💕"
            
        bot.reply_to(message, response)
        conn.close()
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        bot.reply_to(message, "Sorry, I can't check my status right now!")

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
        
        # If not a mention, ignore the message
        if not is_mention:
            return
            
        # Log the detection
        logger.info(f"🎯 {mention_method} MENTION in {chat_type}: '{message.text}' from {username}")
        
        # Track activity for boyfriend game
        track_activity(message)
        
        # Get current boyfriend and mood
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        c.execute("SELECT user_id, end_time FROM boyfriend_table WHERE group_id = ?", (str(message.chat.id),))
        boyfriend = c.fetchone()
        
        mood = get_mood(str(message.chat.id))
        if "super happy" in mood:
            responses = happy_responses
        elif "a bit lonely" in mood:
            responses = lonely_responses
        else:
            responses = good_responses
        
        # Add boyfriend bonus
        if boyfriend and boyfriend[0] == str(message.from_user.id):
            response = random.choice(responses) + " My boyfriend gets extra love! 😘"
        else:
            response = random.choice(responses)
            
        logger.info(f"💬 RESPONDING in {chat_type}: {response}")
        bot.reply_to(message, response)
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