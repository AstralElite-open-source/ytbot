# YouTube Downloader Telegram Bot

Just paste a YouTube link to download high quality videos and audio!

## Features

- 🎥 Download videos up to 1080p
- 🎵 Download audio in 320kbps MP3
- 📑 Download entire playlists and channels
- 📦 Support for files up to 2GB
- 🎨 Animated sticker during downloads
- 🧹 Clean chat experience (auto-deletes temporary messages)
- 👥 Multi-user support
- 🔴 Redis for persistent session storage
- 📊 Kafka event streaming for monitoring and analytics

## Quick Setup

```bash
git clone https://github.com/AstralElite-open-source/ytbot.git
```

### 1. Get Telegram Credentials

Visit https://my.telegram.org/auth and login:
- Note your `API ID`
- Note your `API Hash`

### 2. Create Your Bot

Message [@BotFather](https://t.me/BotFather) on Telegram:
- Send `/newbot`
- Choose a name and username
- Copy your `Bot Token`

### 3. Configure Environment

Create a `.env` file:
```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_API_ID=your_api_id_here
TELEGRAM_API_HASH=your_api_hash_here
```

### 4. Start the Bot

```bash
docker-compose up -d
```

That's it! ✅

## Usage

1. Send a YouTube link to your bot
2. Choose quality (1080p/720p/480p/360p/Audio)
3. Wait for download and upload
4. Enjoy your video/audio!

## Commands

View logs:
```bash
docker logs youtube-downloader-bot
```

Stop the bot:
```bash
docker-compose down
```

Restart the bot:
```bash
docker-compose restart
```

## Kafka Topics

The bot publishes events to the following Kafka topics:

- `youtube-bot-downloads` - Download events (started, completed)
- `youtube-bot-uploads` - Upload events (started, completed)
- `youtube-bot-errors` - Error events
- `youtube-bot-events` - General events (bot started, video detected, etc.)

### Consuming Kafka Events

To consume events from Kafka:

```bash
# Connect to Kafka container
docker exec -it youtube-bot-kafka bash

# Consume from all topics
kafka-console-consumer --bootstrap-server localhost:9092 --topic youtube-bot-downloads --from-beginning
kafka-console-consumer --bootstrap-server localhost:9092 --topic youtube-bot-uploads --from-beginning
kafka-console-consumer --bootstrap-server localhost:9092 --topic youtube-bot-errors --from-beginning
kafka-console-consumer --bootstrap-server localhost:9092 --topic youtube-bot-events --from-beginning
```

## Customization

### Change Download Sticker

1. Send any sticker to your bot
2. Bot will reply with the sticker file ID
3. Update the sticker ID in `bot.py`

## License

MIT License - Feel free to use and modify!

## Disclaimer

This bot is intended for **personal use only** to download content you have rights to or for offline viewing of your own content. 

**Please respect copyright laws and YouTube's Terms of Service:**
- Don't download copyrighted content without permission
- Don't redistribute downloaded content
- Don't use for commercial purposes
- Use responsibly and legally

The developers are not responsible for any misuse of this tool.


## Note

This bot is for educational purposes. Please respect YouTube's Terms of Service and copyright laws.
