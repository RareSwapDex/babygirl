#!/usr/bin/env python3
"""Helper script to set custom deployment messages for Heroku"""

import sys
import subprocess
import os

def set_deployment_message(app_name, message):
    """Set deployment message via Heroku CLI"""
    try:
        # Set the config var via Heroku CLI
        cmd = f'heroku config:set DEPLOYMENT_MESSAGE="{message}" -a {app_name}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Deployment message set for app '{app_name}':")
            print(f"📢 Message: {message}")
            print("\n🚀 Now deploy your app and Babygirl will send this custom message!")
        else:
            print(f"❌ Failed to set deployment message: {result.stderr}")
            print("💡 Make sure you have Heroku CLI installed and are logged in")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure you have Heroku CLI installed and are logged in")

def clear_deployment_message(app_name):
    """Clear the custom deployment message"""
    try:
        cmd = f'heroku config:unset DEPLOYMENT_MESSAGE -a {app_name}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ Custom deployment message cleared for app '{app_name}'")
            print("📢 Future deployments will use the default message")
        else:
            print(f"❌ Failed to clear deployment message: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    """Main function"""
    if len(sys.argv) < 3:
        print("🎯 Babygirl Deployment Message Helper")
        print("\n📝 Set a custom deployment message:")
        print("python3 set_deploy_message.py <app-name> 'Your custom message here! 💕'")
        print("\n🧹 Clear custom message (use default):")
        print("python3 set_deploy_message.py <app-name> --clear")
        print("\n💡 Examples:")
        print("python3 set_deploy_message.py babygirl-bot 'I can now remember our conversations! 🥰'")
        print("python3 set_deploy_message.py babygirl-bot 'New crypto features added! 🚀💕'")
        print("python3 set_deploy_message.py babygirl-bot --clear")
        return
    
    app_name = sys.argv[1]
    
    if len(sys.argv) > 2 and sys.argv[2] == '--clear':
        clear_deployment_message(app_name)
    else:
        message = ' '.join(sys.argv[2:])
        if not message:
            print("❌ Please provide a deployment message")
            return
        set_deployment_message(app_name, message)

if __name__ == "__main__":
    main() 