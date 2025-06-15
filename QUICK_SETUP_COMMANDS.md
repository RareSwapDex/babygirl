# 🚀 Quick Setup Commands for Groq AI Integration

## 1️⃣ Get Your FREE API Key
Visit: https://console.groq.com/keys
- Sign up (free)
- Create API key
- Copy key (starts with `gsk_...`)

## 2️⃣ Set up in WSL Ubuntu
```bash
# Switch to WSL Ubuntu
wsl

# Navigate to your project
cd /home/ryan/projects/BabyGirlTgBot

# Install Groq
pip install groq==0.4.1

# Create environment file
echo "GROQ_API_KEY=your_key_here" > .env
echo "USE_AI_RESPONSES=true" >> .env

# Test the AI setup
python3 ai_setup.py
```

## 3️⃣ Update Your Bot Code
1. **Add import** (top of babygirl_bot.py):
```python
from groq import Groq
```

2. **Add AI config** (after scheduler.start()):
```python
# Copy the AI_CONFIG_CODE from ai_integration_patch.py
```

3. **Add AI function** (after AI config):
```python
# Copy the AI_FUNCTION_CODE from ai_integration_patch.py
```

4. **Add /ai command** (after your existing commands):
```python
# Copy the AI_COMMAND_CODE from ai_integration_patch.py
```

5. **Modify mention handler** (follow MENTION_HANDLER_MODIFICATION instructions)

## 4️⃣ Deploy to Heroku
```bash
# Set environment variables
heroku config:set GROQ_API_KEY=your_key_here
heroku config:set USE_AI_RESPONSES=true

# Deploy changes
git add .
git commit -m "Add Groq AI integration"
git push heroku main

# Check status
heroku logs --tail
```

## 5️⃣ Test Your Bot
```bash
# In Telegram, try these commands:
/ai                    # Check AI status
/ai test              # Test AI response
@babygirl_bf_bot hi   # Test actual AI responses
```

## 📋 Files Created
- ✅ `requirements.txt` - Updated with groq==0.4.1
- ✅ `GROQ_AI_SETUP.md` - Complete setup guide
- ✅ `ai_setup.py` - Setup and testing script
- ✅ `ai_integration_patch.py` - Code to add to your bot
- ✅ `QUICK_SETUP_COMMANDS.md` - This file

## 🎯 Expected Results
- **Dynamic AI responses** for normal conversations
- **Context-aware** responses based on relationships/competitions
- **Fallback protection** to static responses if AI fails
- **Free usage** with 6,000 requests/minute
- **Better engagement** with more varied responses

## 🔧 Quick Troubleshooting
- **No AI key**: Check environment variables
- **Import error**: Run `pip install groq==0.4.1`
- **API failed**: Verify key is correct (starts with gsk_)
- **Not responding**: Check `/ai` command output

Your bot will now be significantly more engaging! 🎉 