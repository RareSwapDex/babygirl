#!/usr/bin/env python3
"""Deployment notification system for Babygirl Bot"""

import sqlite3
import time
import telebot
import os

# Bot configuration
TOKEN = os.getenv('BOT_TOKEN', '7618107152:AAEMPk7q7xNUhZpiDMMiVRSrTV0hkJSyV8I')
bot = telebot.TeleBot(TOKEN)

def ensure_database_exists():
    """Ensure database exists and has required tables"""
    try:
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Create essential tables if they don't exist
        c.execute('''CREATE TABLE IF NOT EXISTS spam_tracking
                    (user_id TEXT, group_id TEXT, timestamp INTEGER)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS boyfriend_table
                    (group_id TEXT, user_id TEXT, username TEXT, end_time INTEGER)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS cooldown_table
                    (group_id TEXT, user_id TEXT, end_time INTEGER)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS leaderboard_table
                    (group_id TEXT, user_id TEXT, username TEXT, score INTEGER)''')
        
        conn.commit()
        conn.close()
        print("📊 Database structure ensured")
        return True
        
    except Exception as e:
        print(f"⚠️ Database setup failed: {e}")
        return False

def send_deployment_update(update_message):
    """Send deployment update to all active groups"""
    try:
        # Ensure database exists first
        if not ensure_database_exists():
            print("❌ Cannot access database - skipping notifications")
            return 0
            
        conn = sqlite3.connect('babygirl.db')
        c = conn.cursor()
        
        # Get all groups with recent activity (last 7 days)
        seven_days_ago = int(time.time() - 604800)
        c.execute("SELECT DISTINCT group_id FROM spam_tracking WHERE timestamp > ?", (seven_days_ago,))
        active_groups = c.fetchall()
        
        if not active_groups:
            # Fallback: get all groups that have any data
            c.execute("SELECT DISTINCT group_id FROM boyfriend_table UNION SELECT DISTINCT group_id FROM cooldown_table UNION SELECT DISTINCT group_id FROM leaderboard_table")
            active_groups = c.fetchall()
        
        if not active_groups:
            print("📭 No groups found in database - notifications will be sent once bot is used in groups")
            conn.close()
            return 0
        
        deployment_message = f"""✨ **BABYGIRL UPDATE DEPLOYED!** ✨

Hey my gorgeous cuties! Your girl just got some exciting new upgrades! 💅💖

🆕 **What's New:**
{update_message}

🎉 **Why You'll Love It:**
I'm now even more fabulous and ready to make our chats more amazing! Keep mentioning @babygirl_bf_bot to experience all the new goodness!

Use /help to see all my commands and /status to check what's happening! 😘

Love you all! Let's make some memories! 💕✨

*- Your upgraded babygirl* 💋"""

        success_count = 0
        for (group_id,) in active_groups:
            try:
                bot.send_message(group_id, deployment_message)
                success_count += 1
                print(f"✅ Deployment update sent to group {group_id}")
                time.sleep(0.5)  # Small delay to avoid rate limits
            except Exception as e:
                print(f"❌ Failed to send update to group {group_id}: {e}")
        
        print(f"🎉 Deployment update sent to {success_count} groups!")
        conn.close()
        return success_count
        
    except Exception as e:
        print(f"⚠️ Error sending deployment updates: {e}")
        return 0

def send_latest_update():
    """Send the latest deployment update about conversation memory and summary features"""
    latest_update = """💾 **Conversation Memory:** I now remember our past chats! I'll reference things you've told me before and build on our conversations! It's like having a real relationship! 🥰

📋 **Chat Summaries:** New /summary command gives you a 12-hour recap of everything you missed! See who's been active, current boyfriend status, hot topics, and more! Perfect for catching up! ✨

🧠 **Smarter Responses:** I use our conversation history to give more personal, meaningful replies! The more we chat, the better I know you! 💕

🎯 **Enhanced Engagement:** I can now initiate crypto discussions when chat is quiet and tag members to keep conversations flowing! Plus I remember ALL our previous updates! 🔥"""
    
    sent_count = send_deployment_update(latest_update)
    print(f"✅ Latest update sent to {sent_count} groups!")
    return sent_count

if __name__ == "__main__":
    print("🚀 Sending deployment notification...")
    send_latest_update()
    print("📨 Deployment notification complete!") 