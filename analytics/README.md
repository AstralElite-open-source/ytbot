# 📊 YouTube Bot Analytics

Beautiful web-based analytics dashboard for your YouTube bot with real-time Kafka event streaming.

## 🚀 Quick Start

### Start Analytics Dashboard

```bash
cd analytics
docker-compose up -d analytics-dashboard
```

Then open: **http://localhost:8501**

### Generate Daily Report

```bash
docker-compose --profile report run --rm daily-report
```

For custom time period:
```bash
docker-compose --profile report run --rm daily-report python daily_report.py 168  # 7 days
```

---

## 📊 Features

### Web Dashboard
- 📈 Real-time metrics and statistics
- 🎨 Interactive graphs (Quality preferences, Top users, Activity by hour)
- 🎬 Recent videos list
- ❌ Error tracking
- 📡 Live event feed
- 🔄 Manual refresh button

### Daily Report Generator
- 📋 Comprehensive analytics report
- ⏰ Custom time periods
- 📊 Activity patterns
- 👥 User statistics
- 🎥 Quality preferences

---

## 🎯 What's Tracked

### Events from Kafka Topics:
- `youtube-bot-downloads` - Download events
- `youtube-bot-uploads` - Upload events
- `youtube-bot-errors` - Error events
- `youtube-bot-events` - General events (video detected, playlist detected, etc.)

### Metrics:
- 👥 Unique users
- 🎬 Videos & playlists downloaded
- 📊 Quality preferences (720p, 1080p, MP3)
- 💾 Total data uploaded
- ⏰ Activity patterns by hour
- ❌ Error tracking

---

## 📁 Files

```
analytics/
├── dashboard.py          ← Web dashboard (Streamlit)
├── daily_report.py       ← Report generator
├── Dockerfile           ← Container image
├── docker-compose.yml   ← Easy deployment
├── requirements.txt     ← Python dependencies
└── README.md           ← This file
```

---

## 🔧 Commands

```bash
# Start dashboard
docker-compose up -d analytics-dashboard

# View dashboard logs
docker logs -f ytbot-analytics-dashboard

# Stop dashboard
docker-compose down

# Restart dashboard
docker-compose restart analytics-dashboard

# Generate daily report
docker-compose --profile report run --rm daily-report

# Generate weekly report (168 hours)
docker-compose --profile report run --rm daily-report python daily_report.py 168

# Save report to file
docker-compose --profile report run --rm daily-report > reports/report-$(date +%Y-%m-%d).txt
```

---

## 🌐 Access Dashboard

### Same Computer
```
http://localhost:8501
```

### Different Computer (Same Network)
```
http://YOUR_IP:8501
```

Find your IP:
```bash
# Windows
ipconfig

# Linux/Mac
ifconfig
```

---

## 📊 Dashboard Preview

```
┌─────────────────────────────────────────┐
│  📊 YouTube Bot Analytics Dashboard     │
├─────────────────────────────────────────┤
│                                         │
│  👥 Users  🎬 Videos  ⬇️ Downloads     │
│     12        45         38             │
│                                         │
│  [Quality Preferences]  [Top Users]    │
│  🥧 Pie Chart           📊 Bar Chart   │
│                                         │
│  [Activity by Hour]                     │
│  📈 Line Graph                          │
│                                         │
│  🎬 Recent Videos    ❌ Recent Errors  │
│  ━━━━━━━━━━━━━━━━    ━━━━━━━━━━━━━━   │
│  1. Video Title 1    No errors! 🎉     │
│  2. Video Title 2                       │
│                                         │
└─────────────────────────────────────────┘
```

---

## 🐛 Troubleshooting

### Dashboard shows zeros
Make sure the main bot is running and Kafka has events:
```bash
cd ..
docker-compose ps
```

### Port 8501 already in use
Change port in `docker-compose.yml`:
```yaml
ports:
  - "8502:8501"  # Use 8502 instead
```

### Can't connect to network
Ensure main bot is running first:
```bash
cd ..
docker-compose up -d
```

---

## 📝 Notes

- Dashboard reads all historical events from Kafka
- Use "🔄 Refresh Data" button to update manually
- Reports are saved to `./reports` directory
- All times shown in UTC

---

**Made with ❤️ using Streamlit, Kafka, and Redis**
