#!/usr/bin/env python3
"""Send custom deployment update to all active groups"""

import sys
from deployment_notifier import send_deployment_update

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 send_update.py 'Your update message here'")
        print("\nExample:")
        print("python3 send_update.py 'I can now remember our conversations and tag you cuties when chat gets quiet! 💕'")
        return
    
    update_message = ' '.join(sys.argv[1:])
    print(f"📢 Sending update: {update_message}")
    
    sent_count = send_deployment_update(update_message)
    print(f"✅ Update sent to {sent_count} groups!")

if __name__ == "__main__":
    main() 