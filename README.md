# BabygirlBot 💕

A flirty Telegram bot with boyfriend competition game mechanics and mood-based responses.

## Features

### 🎮 Core Game Mechanics
- **Boyfriend Competition**: 12-hour boyfriend terms with automatic expiry
- **Cooldown Periods**: 15-minute application periods where users compete by mentioning the bot
- **Activity Tracking**: Counts mentions during cooldown periods
- **Automatic Scheduling**: Checks every minute for term expiry and cooldown end

### 💕 Personality & Responses
- **Flirty Personality**: Sassy, playful responses with mood variations
- **Mood System**: Happy, good, or lonely responses based on recent activity
- **Boyfriend Bonuses**: Special responses for current boyfriends
- **Multiple Response Sets**: 150+ different flirty responses

### 🏆 Gamification
- **Leaderboard**: Tracks top 5 boyfriend winners per group
- **Random Challenges**: 10% chance every 5 minutes for mention challenges
- **Storylines**: Random events every 3 days lasting 1 hour
- **Gift System**: Virtual flowers and chocolates with timestamps

### 🛠️ Commands

#### Basic Commands
- `/start` - Introduction message
- `/help` - Command list and instructions
- `/boyfriend` - Check current boyfriend and time remaining
- `/apply` - Apply during cooldown periods
- `/status` - Bot's current mood and relationship status

#### Exclusive Boyfriend Commands
- `/kiss` - Get a kiss (boyfriend only)
- `/hug` - Get a hug (boyfriend only)

#### Fun Commands
- `/gift flowers` - Send virtual flowers
- `/gift chocolates` - Send virtual chocolates
- `/leaderboard` - View top boyfriend winners
- `/play` - Get a random love song

#### Debug Commands
- `/debug` - Check bot status and database info
- `/privacy` - Check privacy mode settings
- `/test` - Test bot responsiveness
- `/mention` - Force trigger mention response

### 🔧 Technical Features
- **Multi-group Support**: Each group has independent game state
- **SQLite Database**: 5 tables for boyfriends, cooldowns, activity, leaderboard, and gifts
- **Comprehensive Mention Detection**: Handles both text and entity-based mentions
- **Error Handling**: Graceful error handling with logging
- **Auto-restart**: Production-ready with infinity polling

## Setup

### Prerequisites
- Python 3.10+
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)

### Installation
1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Update the `TOKEN` in `babygirl_bot.py` with your bot token
4. **Important**: Disable privacy mode via @BotFather for group functionality
5. Run the bot:
   ```bash
   python3 babygirl_bot.py
   ```

### Privacy Mode Setup
For the bot to work in groups, you MUST disable privacy mode:
1. Message [@BotFather](https://t.me/BotFather)
2. Send `/mybots`
3. Select your bot
4. Choose "Bot Settings" → "Group Privacy" → "Turn Off"

## Database Schema

### Tables
- `boyfriend_table`: Current boyfriends (user_id, end_time, group_id)
- `cooldown_table`: Active cooldown periods (is_active, end_time, group_id)
- `activity_table`: Mention counts during cooldowns (user_id, mention_count, group_id)
- `leaderboard_table`: Boyfriend win counts (user_id, boyfriend_count, group_id)
- `gifts_table`: Virtual gifts sent (user_id, gift_type, timestamp, group_id)

## Deployment

### Heroku Deployment
1. Create a Heroku app
2. Set up the following files:
   - `Procfile`: `worker: python babygirl_bot.py`
   - `requirements.txt`: Python dependencies
3. Deploy using Git or GitHub integration

### Local Development
```bash
python3 babygirl_bot.py
```

## Bot Mechanics

### Boyfriend Competition
1. Current boyfriend has a 12-hour term
2. When term expires, a 15-minute cooldown begins
3. Users compete by mentioning `@babygirl_bf_bot`
4. User with most mentions wins the next 12-hour term
5. Winner gets access to exclusive commands and bonus responses

### Mood System
- **Super Happy** (>10 recent mentions): Extra enthusiastic responses
- **Good** (5-10 mentions): Standard flirty responses  
- **Lonely** (<5 mentions): More vulnerable, attention-seeking responses

### Activity Tracking
- Only counts mentions containing `@babygirl_bf_bot`
- Tracks per-user mention counts during cooldown periods
- Resets after each competition

## Contributing

Feel free to submit issues and pull requests to improve the bot!

## License

This project is for educational and entertainment purposes. 