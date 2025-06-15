# 🤖 Groq AI Integration Setup for BabygirlBot

## ✨ Overview
Your BabygirlBot now supports **FREE** AI-powered responses using Groq! This integration provides:
- Dynamic, context-aware responses
- Maintains Babygirl's flirty Instagram influencer personality  
- Completely free (6,000 requests/minute limit)
- Automatic fallback to static responses if AI fails

## 🚀 Quick Setup

### Step 1: Get Your FREE Groq API Key
1. Go to https://console.groq.com/keys
2. Sign up with your email (completely free!)
3. Click "Create API Key"
4. Copy the key (starts with `gsk_...`)

### Step 2: Install Groq in WSL Ubuntu
```bash
# Switch to Ubuntu in WSL
wsl

# Navigate to your project
cd /home/ryan/projects/BabyGirlTgBot

# Install Groq
pip install groq==0.4.1

# Test the setup
python3 ai_setup.py
```

### Step 3: Set Environment Variables
Create a `.env` file in your project directory:
```bash
echo "GROQ_API_KEY=your_api_key_here" >> .env
echo "USE_AI_RESPONSES=true" >> .env
```

### Step 4: Update Heroku (for deployment)
```bash
heroku config:set GROQ_API_KEY=your_api_key_here
heroku config:set USE_AI_RESPONSES=true
heroku restart
```

## 🎮 How It Works

### AI Response Generation
The bot will now:
1. **Try AI first** - Generate contextual responses using Groq
2. **Fallback gracefully** - Use original static responses if AI fails
3. **Maintain personality** - All responses stay true to Babygirl's character

### When AI is Used
- ✅ Normal mentions (@babygirl_bf_bot)
- ✅ Replies to bot messages
- ✅ Casual conversations
- ✅ Context-aware based on relationships/competitions

### When Static Responses are Used
- 🚫 Spam detection (prevents AI abuse)
- 🚫 Opinion requests about other users (uses existing logic)
- 🚫 Game-specific mechanics (boyfriend competitions, etc.)

## 🎯 AI Features

### Context Awareness
The AI knows about:
- **Current boyfriend status** - Treats boyfriends specially
- **Active competitions** - Adjusts responses during competitions  
- **Relationship status** - Different responses for single/taken users
- **User activity** - Considers mention counts and engagement

### Personality Consistency
- Flirty Instagram influencer style
- Uses lots of emojis (💕😘✨💅👑🔥💖😍)
- Modern slang and current expressions
- References to Cortex Vortex background
- Maintains "main character energy"

## 🔧 Testing Your Setup

### Test Commands (add to your bot)
```python
@bot.message_handler(commands=['ai'])
def ai_command(message):
    # Shows AI status and allows testing
    # Usage: /ai, /ai test, /ai on, /ai off
```

### Manual Testing
1. Mention the bot: `@babygirl_bf_bot hey how are you?`
2. Check logs for `🤖 Using AI response` vs `📝 Using static response`
3. AI responses should be more varied and contextual

## 📊 Rate Limits & Costs

### Groq Free Tier
- **6,000 requests per minute**
- **Completely FREE** (no credit card required)
- **Fast inference** (faster than OpenAI)
- **High-quality responses** using Llama 3 8B model

### Fallback Protection
If you hit rate limits or API fails:
- Bot automatically uses static responses
- No downtime or errors for users
- Seamless experience maintained

## 🔒 Security & Environment Variables

### Required Environment Variables
```bash
# Bot token (already set)
BOT_TOKEN=7618107152:AAEMPk7q7xNUhZpiDMMiVRSrTV0hkJSyV8I

# New AI variables
GROQ_API_KEY=gsk_your_key_here
USE_AI_RESPONSES=true
```

### Heroku Config
```bash
heroku config:set GROQ_API_KEY=gsk_your_key_here
heroku config:set USE_AI_RESPONSES=true
```

## 🚀 Deployment Steps

### Local Testing
1. Set up `.env` file with your API key
2. Run `python3 babygirl_bot.py` 
3. Test mentions and check logs

### Heroku Deployment  
1. Update requirements.txt (already done)
2. Set Heroku config vars
3. Deploy: `git push heroku main`
4. Check logs: `heroku logs --tail`

## 📈 Expected Improvements

### Before AI
- Repetitive responses from static pools
- Limited contextual awareness
- Same responses regardless of situation

### After AI
- **Dynamic responses** based on conversation context
- **Relationship-aware** interactions
- **Competition-sensitive** during boyfriend games
- **More engaging** and less predictable
- **Personality consistency** maintained

## 🛠️ Troubleshooting

### Common Issues
1. **"No API key set"** - Check environment variables
2. **"API test failed"** - Verify API key is correct
3. **Rate limit errors** - Bot will fallback to static responses
4. **Import errors** - Ensure `groq` package is installed

### Debug Commands
- `/debug` - Check bot status
- `/ai` - Check AI status (once added)
- Check Heroku logs for AI usage patterns

## 💡 Next Steps

1. **Get your API key** from Groq
2. **Test locally** using WSL Ubuntu environment
3. **Deploy to Heroku** with new environment variables
4. **Monitor performance** and user engagement
5. **Enjoy more dynamic** Babygirl responses!

Your bot will now be significantly more engaging while maintaining all existing functionality! 🎉 