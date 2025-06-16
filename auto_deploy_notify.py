#!/usr/bin/env python3
"""Automatic deployment notification for Heroku release phase"""

import os
import sys
import time
from deployment_notifier import send_deployment_update

def get_deployment_message():
    """Get the deployment message from environment variable or use default"""
    
    # Check if custom deployment message is set via environment variable
    custom_message = os.getenv('DEPLOYMENT_MESSAGE')
    if custom_message:
        return custom_message
    
    # Default message for regular deployments
    default_message = """🔄 **Fresh Deployment:** I just got redeployed with the latest updates! Everything is running smooth and I'm ready to flirt! 💅

💾 **Current Features:** Conversation memory, chat summaries, proactive engagement, and all my boyfriend competition games! 

🎯 **Ready to Chat:** Mention @babygirl_bf_bot to experience the full upgraded experience!"""
    
    return default_message

def main():
    """Send deployment notification during Heroku release phase"""
    try:
        print("🚀 Starting automatic deployment notification...")
        
        # Get the deployment message
        message = get_deployment_message()
        
        print(f"📢 Sending notification: {message[:100]}...")
        
        # Send the notification
        sent_count = send_deployment_update(message)
        
        if sent_count > 0:
            print(f"✅ Deployment notification sent to {sent_count} groups!")
        else:
            print("ℹ️ No active groups found - notification will be sent once bot is active")
        
        # Clear the custom message if it was set
        if os.getenv('DEPLOYMENT_MESSAGE'):
            print("🧹 Custom deployment message used and cleared")
        
        print("🎉 Automatic deployment notification complete!")
        return 0
        
    except Exception as e:
        print(f"⚠️ Deployment notification failed (deployment will continue): {e}")
        # Don't fail the deployment if notification fails
        return 0

if __name__ == "__main__":
    sys.exit(main()) 