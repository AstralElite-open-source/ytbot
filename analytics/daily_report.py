#!/usr/bin/env python3
"""
Daily Report Generator - Generates comprehensive analytics report
Run this to get a complete summary of bot usage
"""

import json
from kafka import KafkaConsumer
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import os

# Kafka configuration
KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')

def generate_report(hours=24):
    """Generate report for last X hours"""
    
    print(f"📊 Generating {hours}-hour analytics report...")
    print("=" * 80)
    
    # Data collectors
    stats = {
        'events_by_type': Counter(),
        'events_by_hour': defaultdict(int),
        'users': set(),
        'user_activity': defaultdict(int),
        'quality_preferences': Counter(),
        'video_titles': [],
        'errors': [],
        'total_bytes': 0,
        'playlists': 0,
        'single_videos': 0,
        'downloads_completed': 0,
        'uploads_completed': 0,
        'average_file_size': [],
    }
    
    # Calculate cutoff time
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)
    
    try:
        # Create consumer
        consumer = KafkaConsumer(
            'youtube-bot-downloads',
            'youtube-bot-uploads',
            'youtube-bot-errors',
            'youtube-bot-events',
            bootstrap_servers=KAFKA_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            consumer_timeout_ms=10000,  # Stop after 10s of no messages
            group_id=f'report-generator-{datetime.now().timestamp()}'
        )
        
        print("✅ Reading events from Kafka...\n")
        
        events_processed = 0
        events_in_timeframe = 0
        
        for message in consumer:
            events_processed += 1
            event = message.value
            
            # Parse timestamp
            try:
                event_time = datetime.fromisoformat(event.get('timestamp', ''))
                if event_time < cutoff_time:
                    continue  # Skip old events
            except:
                continue
            
            events_in_timeframe += 1
            
            event_type = event.get('event_type')
            user_id = event.get('user_id')
            data = event.get('data', {})
            
            # Collect stats
            stats['events_by_type'][event_type] += 1
            stats['users'].add(user_id)
            stats['user_activity'][user_id] += 1
            
            # Hour distribution
            hour = event_time.hour
            stats['events_by_hour'][hour] += 1
            
            # Event-specific stats
            if event_type == 'video_detected':
                stats['single_videos'] += 1
                stats['video_titles'].append(data.get('title', 'Unknown')[:50])
                
            elif event_type == 'playlist_detected':
                stats['playlists'] += 1
                
            elif event_type == 'download_started':
                quality = data.get('quality', 'unknown')
                stats['quality_preferences'][quality] += 1
                
            elif event_type == 'upload_completed':
                stats['uploads_completed'] += 1
                file_size = data.get('file_size', 0)
                stats['total_bytes'] += file_size
                stats['average_file_size'].append(file_size)
                
            elif 'error' in event_type:
                error_msg = data.get('error', data.get('error_message', 'Unknown'))
                stats['errors'].append((event_time, error_msg))
        
        consumer.close()
        
        # Generate report
        print("=" * 80)
        print(f"📈 ANALYTICS REPORT - Last {hours} Hours")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        print(f"\n📊 OVERVIEW")
        print("-" * 80)
        print(f"Total Events Processed:    {events_in_timeframe:,}")
        print(f"Unique Users:              {len(stats['users']):,}")
        print(f"Videos Detected:           {stats['single_videos']:,}")
        print(f"Playlists Detected:        {stats['playlists']:,}")
        print(f"Uploads Completed:         {stats['uploads_completed']:,}")
        print(f"Total Data Uploaded:       {format_bytes(stats['total_bytes'])}")
        print(f"Errors:                    {len(stats['errors']):,}")
        
        if stats['average_file_size']:
            avg_size = sum(stats['average_file_size']) / len(stats['average_file_size'])
            print(f"Average File Size:         {format_bytes(avg_size)}")
        
        # Quality preferences
        if stats['quality_preferences']:
            print(f"\n🎥 QUALITY PREFERENCES")
            print("-" * 80)
            total_downloads = sum(stats['quality_preferences'].values())
            for quality, count in stats['quality_preferences'].most_common():
                percentage = (count / total_downloads * 100)
                bar = '█' * int(percentage / 2)
                print(f"{quality:10} [{bar:<50}] {count:4} ({percentage:5.1f}%)")
        
        # Most active users
        if stats['user_activity']:
            print(f"\n👥 TOP 10 MOST ACTIVE USERS")
            print("-" * 80)
            for user_id, activity_count in Counter(stats['user_activity']).most_common(10):
                print(f"User {user_id}: {activity_count} actions")
        
        # Hourly distribution
        if stats['events_by_hour']:
            print(f"\n⏰ ACTIVITY BY HOUR (UTC)")
            print("-" * 80)
            max_events = max(stats['events_by_hour'].values()) if stats['events_by_hour'] else 1
            for hour in range(24):
                count = stats['events_by_hour'][hour]
                if count > 0:
                    bar_length = int((count / max_events) * 40)
                    bar = '█' * bar_length
                    print(f"{hour:02d}:00 [{bar:<40}] {count:4} events")
        
        # Recent videos
        if stats['video_titles']:
            print(f"\n🎬 RECENT VIDEOS (Last 10)")
            print("-" * 80)
            for i, title in enumerate(stats['video_titles'][-10:], 1):
                print(f"{i:2}. {title}")
        
        # Errors
        if stats['errors']:
            print(f"\n❌ RECENT ERRORS")
            print("-" * 80)
            for event_time, error_msg in stats['errors'][-10:]:
                time_str = event_time.strftime('%H:%M:%S')
                print(f"[{time_str}] {error_msg[:70]}")
        
        # Event type breakdown
        print(f"\n📋 EVENT TYPE BREAKDOWN")
        print("-" * 80)
        for event_type, count in stats['events_by_type'].most_common():
            print(f"{event_type:30} {count:6,}")
        
        print("\n" + "=" * 80)
        print(f"✅ Report generated successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        print("Make sure Kafka is running: docker-compose up -d")

def format_bytes(bytes_num):
    """Format bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} PB"

if __name__ == '__main__':
    import sys
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    generate_report(hours)

