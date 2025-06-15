# 🚀 Deploy Babygirl Bot to Heroku

This guide will help you deploy Babygirl to Heroku so she runs 24/7 without keeping your laptop on!

## ✅ Prerequisites

1. **Heroku Account**: Sign up at [heroku.com](https://heroku.com)
2. **Heroku CLI**: Download from [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)
3. **Git**: Make sure git is installed

## 🔧 Step 1: Prepare Your Code

Your files are already set up for Heroku deployment:
- ✅ `Procfile` - Tells Heroku how to run the bot
- ✅ `requirements.txt` - Lists Python dependencies  
- ✅ `runtime.txt` - Specifies Python version
- ✅ `.gitignore` - Excludes unnecessary files
- ✅ Bot code updated to use environment variables

## 🌐 Step 2: Deploy to Heroku

### Option A: Using Heroku CLI (Recommended)

1. **Login to Heroku**:
   ```bash
   heroku login
   ```

2. **Create a new Heroku app**:
   ```bash
   heroku create babygirl-bot-yourname
   ```
   (Replace `yourname` with something unique)

3. **Set the bot token as environment variable**:
   ```bash
   heroku config:set BOT_TOKEN=7618107152:AAEMPk7q7xNUhZpiDMMiVRSrTV0hkJSyV8I
   ```

4. **Deploy the bot**:
   ```bash
   git add .
   git commit -m "Deploy Babygirl Bot to Heroku"
   git push heroku main
   ```

5. **Scale the worker dyno**:
   ```bash
   heroku ps:scale worker=1
   ```

### Option B: Using Heroku Dashboard

1. Go to [dashboard.heroku.com](https://dashboard.heroku.com)
2. Click "New" → "Create new app"
3. Choose app name: `babygirl-bot-yourname`
4. Connect to your GitHub repository
5. In Settings → Config Vars, add:
   - KEY: `BOT_TOKEN`
   - VALUE: `7618107152:AAEMPk7q7xNUhZpiDMMiVRSrTV0hkJSyV8I`
6. Deploy from the Deploy tab
7. In Resources tab, turn on the `worker` dyno

## 🎯 Step 3: Verify Deployment

1. **Check logs**:
   ```bash
   heroku logs --tail
   ```
   You should see: `INFO:__main__:Babygirl Bot starting...`

2. **Test the bot** in your Telegram group:
   - Try `/start` command
   - Mention `@babygirl_bf_bot hello`
   - Use `/vibecheck` to test social features

## 💰 Heroku Pricing

- **Free Plan**: 550-1000 hours/month (enough for 24/7 if you verify with credit card)
- **Hobby Plan**: $7/month for unlimited hours
- The bot uses minimal resources, so either plan works great!

## 🔄 Managing Your Bot

### View logs:
```bash
heroku logs --tail
```

### Stop the bot:
```bash
heroku ps:scale worker=0
```

### Start the bot:
```bash
heroku ps:scale worker=1
```

### Update the bot:
```bash
git add .
git commit -m "Update bot"
git push heroku main
```

## 🎉 Success!

Once deployed, your Babygirl bot will run 24/7 on Heroku! She'll:
- ✅ Run boyfriend competitions automatically
- ✅ Respond to mentions and commands
- ✅ Track relationships and give opinions
- ✅ Keep groups engaged with social features
- ✅ Never go offline (unless you stop the dyno)

## 🚨 Important Notes

1. **Database**: The SQLite database will reset each time you deploy. For production, consider upgrading to PostgreSQL later.

2. **Bot Token Security**: The bot token is now stored as an environment variable, which is secure.

3. **Logs**: Use `heroku logs --tail` to monitor the bot and debug any issues.

4. **Updates**: Any changes you make locally can be deployed with `git push heroku main`.

## 🆘 Troubleshooting

**Bot not responding?**
- Check logs: `heroku logs --tail`
- Ensure worker dyno is running: `heroku ps`
- Verify bot token is set: `heroku config`

**Database issues?**
- Check logs for SQLite errors
- The database recreates automatically on startup

**Competition not working?**
- Ensure privacy mode is OFF in @BotFather
- Check that bot is admin in groups (optional but recommended)

---

🎊 **Congratulations! Babygirl is now live 24/7!** 🎊 