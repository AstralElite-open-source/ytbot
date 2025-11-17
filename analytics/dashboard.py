#!/usr/bin/env python3
"""
Streamlit Analytics Dashboard - Beautiful web-based analytics!
Access at: http://localhost:8501
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from kafka import KafkaConsumer
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import json
import os
import time

# Page config
st.set_page_config(
    page_title="YouTube Bot Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Kafka configuration
KAFKA_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092').split(',')

# Initialize session state
if 'stats' not in st.session_state:
    st.session_state.stats = {
        'total_videos': 0,
        'total_playlists': 0,
        'total_downloads': 0,
        'total_uploads': 0,
        'total_errors': 0,
        'total_bytes_uploaded': 0,
        'total_bytes_downloaded': 0,
        'unique_users': set(),
        'quality_prefs': Counter(),
        'hourly_activity': defaultdict(int),
        'events_timeline': [],
        'recent_videos': [],
        'recent_errors': [],
        'user_activity': Counter(),
    }


def format_bytes(bytes_num):
    """Format bytes to human readable"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} PB"

def load_kafka_events():
    """Load events from Kafka"""
    stats = st.session_state.stats
    
    try:
        # Create new consumer with unique group ID to read from beginning
        consumer = KafkaConsumer(
            'youtube-bot-downloads',
            'youtube-bot-uploads',
            'youtube-bot-errors',
            'youtube-bot-events',
            bootstrap_servers=KAFKA_SERVERS,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            group_id=f'streamlit-dashboard-{int(time.time() * 1000)}',  # Unique group = read all
            consumer_timeout_ms=5000
        )
        
        event_count = 0
        for message in consumer:
            event_count += 1
            event = message.value
            event_type = event.get('event_type')
            user_id = event.get('user_id')
            data = event.get('data', {})
            timestamp = event.get('timestamp', '')
            
            # Update stats
            stats['unique_users'].add(user_id)
            stats['user_activity'][user_id] += 1
            
            # Parse timestamp for hourly activity
            try:
                dt = datetime.fromisoformat(timestamp)
                stats['hourly_activity'][dt.hour] += 1
            except:
                pass
            
            # Event-specific processing
            if event_type == 'video_detected':
                stats['total_videos'] += 1
                title = data.get('title', 'Unknown')
                stats['recent_videos'].insert(0, {
                    'title': title[:60],
                    'time': timestamp,
                    'duration': data.get('duration', 0)
                })
                stats['recent_videos'] = stats['recent_videos'][:20]
                
            elif event_type == 'playlist_detected':
                stats['total_playlists'] += 1
                
            elif event_type == 'download_started':
                stats['total_downloads'] += 1
                quality = data.get('quality', 'unknown')
                stats['quality_prefs'][quality] += 1
                
            elif event_type == 'download_completed':
                file_size = data.get('file_size', 0)
                stats['total_bytes_downloaded'] += file_size
                
            elif event_type == 'upload_completed':
                stats['total_uploads'] += 1
                file_size = data.get('file_size', 0)
                stats['total_bytes_uploaded'] += file_size
                
            elif 'error' in event_type:
                stats['total_errors'] += 1
                error_msg = data.get('error', data.get('error_message', 'Unknown'))
                stats['recent_errors'].insert(0, {
                    'error': error_msg,
                    'time': timestamp,
                    'type': event_type
                })
                stats['recent_errors'] = stats['recent_errors'][:10]
            
            # Add to timeline
            stats['events_timeline'].append({
                'time': timestamp,
                'type': event_type,
                'user': user_id
            })
            if len(stats['events_timeline']) > 100:
                stats['events_timeline'] = stats['events_timeline'][-100:]
        
        consumer.close()
        return event_count
                
    except Exception as e:
        st.error(f"Kafka error: {e}")
        return 0

# Reset stats before loading
st.session_state.stats = {
    'total_videos': 0,
    'total_playlists': 0,
    'total_downloads': 0,
    'total_uploads': 0,
    'total_errors': 0,
    'total_bytes_uploaded': 0,
    'total_bytes_downloaded': 0,
    'unique_users': set(),
    'quality_prefs': Counter(),
    'hourly_activity': defaultdict(int),
    'events_timeline': [],
    'recent_videos': [],
    'recent_errors': [],
    'user_activity': Counter(),
}

# Load events on each refresh
with st.spinner("Loading data from Kafka..."):
    events_loaded = load_kafka_events()

# Dashboard UI
st.title("📊 YouTube Bot Analytics Dashboard")
st.markdown("---")

# Get stats
stats = st.session_state.stats

# Show events loaded
if events_loaded > 0:
    st.success(f"✅ Loaded {events_loaded} events from Kafka")
else:
    st.warning("⏳ Waiting for events... Use your bot to download videos!")

# Sidebar controls
st.sidebar.title("⚙️ Controls")

if st.sidebar.button("🔄 Refresh Data"):
    st.cache_resource.clear()
    st.rerun()

st.sidebar.markdown("---")

# Report generator in sidebar
st.sidebar.subheader("📋 Generate Report")
report_hours = st.sidebar.selectbox(
    "Time Period",
    [1, 6, 12, 24, 48, 168, 720],
    index=3,
    format_func=lambda x: {
        1: "Last Hour",
        6: "Last 6 Hours", 
        12: "Last 12 Hours",
        24: "Last 24 Hours",
        48: "Last 2 Days",
        168: "Last Week",
        720: "Last Month"
    }[x]
)

if st.sidebar.button("📥 Generate Report"):
    # Generate text report
    report_text = f"""
📈 YOUTUBE BOT ANALYTICS REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Time Period: Last {report_hours} hours
{'=' * 60}

📊 OVERVIEW
{'-' * 60}
Unique Users:              {len(stats['unique_users']):,}
Videos Detected:           {stats['total_videos']:,}
Playlists Detected:        {stats['total_playlists']:,}
Downloads Started:         {stats['total_downloads']:,}
Uploads Completed:         {stats['total_uploads']:,}

💾 BANDWIDTH USAGE
{'-' * 60}
Total Bandwidth:           {format_bytes(stats['total_bytes_uploaded'] + stats['total_bytes_downloaded'])}
  ↓ Downloaded:            {format_bytes(stats['total_bytes_downloaded'])}
  ↑ Uploaded:              {format_bytes(stats['total_bytes_uploaded'])}

Errors:                    {stats['total_errors']:,}

"""
    
    if stats['quality_prefs']:
        report_text += f"\n🎥 QUALITY PREFERENCES\n{'-' * 60}\n"
        total_downloads = sum(stats['quality_prefs'].values())
        for quality, count in stats['quality_prefs'].most_common():
            percentage = (count / total_downloads * 100) if total_downloads > 0 else 0
            report_text += f"{quality:10} {count:4} ({percentage:5.1f}%)\n"
    
    if stats['user_activity']:
        report_text += f"\n👥 TOP 10 ACTIVE USERS\n{'-' * 60}\n"
        for user_id, activity_count in stats['user_activity'].most_common(10):
            report_text += f"User {user_id}: {activity_count} actions\n"
    
    if stats['recent_videos']:
        report_text += f"\n🎬 RECENT VIDEOS\n{'-' * 60}\n"
        for i, video in enumerate(stats['recent_videos'][:10], 1):
            report_text += f"{i:2}. {video['title']}\n"
    
    if stats['recent_errors']:
        report_text += f"\n❌ RECENT ERRORS\n{'-' * 60}\n"
        for error in stats['recent_errors']:
            report_text += f"- {error['error'][:70]}\n"
    
    report_text += f"\n{'=' * 60}\n✅ End of Report\n"
    
    # Provide download button
    st.sidebar.download_button(
        label="💾 Download as TXT",
        data=report_text,
        file_name=f"youtube_bot_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain"
    )

# Top metrics
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("👥 Unique Users", len(stats['unique_users']))
    
with col2:
    st.metric("🎬 Videos", stats['total_videos'])
    
with col3:
    st.metric("⬇️ Downloads", stats['total_downloads'])
    
with col4:
    st.metric("📤 Uploads", stats['total_uploads'])
    
with col5:
    st.metric("❌ Errors", stats['total_errors'], 
              delta=None if stats['total_errors'] == 0 else "Check logs",
              delta_color="inverse")

st.markdown("---")

# Second row of metrics
col1, col2, col3, col4 = st.columns(4)

# If no download data, estimate from uploads (downloads ≈ uploads)
actual_downloaded = stats['total_bytes_downloaded']
estimated_downloaded = stats['total_bytes_uploaded'] if actual_downloaded == 0 else actual_downloaded
total_bandwidth = stats['total_bytes_uploaded'] + estimated_downloaded

with col1:
    st.metric("🌐 Total Bandwidth", format_bytes(total_bandwidth))
    
with col2:
    st.metric("📤 Uploaded", format_bytes(stats['total_bytes_uploaded']))
    
with col3:
    download_label = "📥 Downloaded"
    if actual_downloaded == 0 and stats['total_bytes_uploaded'] > 0:
        download_label = "📥 Downloaded (est.)"
    st.metric(download_label, format_bytes(estimated_downloaded))
    
with col4:
    st.metric("📑 Playlists", stats['total_playlists'])

st.markdown("---")

# Graphs section
col1, col2 = st.columns(2)

with col1:
    st.subheader("🎥 Quality Preferences")
    if stats['quality_prefs']:
        quality_df = pd.DataFrame([
            {'Quality': quality, 'Count': count} 
            for quality, count in stats['quality_prefs'].items()
        ])
        fig = px.pie(quality_df, values='Count', names='Quality', 
                     color_discrete_sequence=px.colors.qualitative.Set3)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No downloads yet")

with col2:
    st.subheader("👥 Top Users")
    if stats['user_activity']:
        top_users = stats['user_activity'].most_common(10)
        user_df = pd.DataFrame(top_users, columns=['User ID', 'Actions'])
        fig = px.bar(user_df, x='User ID', y='Actions',
                     color='Actions',
                     color_continuous_scale='blues')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No user activity yet")

st.markdown("---")

# Hourly activity
st.subheader("⏰ Activity by Hour (UTC)")
if stats['hourly_activity']:
    hourly_df = pd.DataFrame([
        {'Hour': f"{hour:02d}:00", 'Events': count}
        for hour, count in sorted(stats['hourly_activity'].items())
    ])
    fig = px.line(hourly_df, x='Hour', y='Events', 
                  markers=True,
                  line_shape='spline')
    fig.update_traces(line_color='#1f77b4', line_width=3)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No activity data yet")

st.markdown("---")

# Two columns for recent data
col1, col2 = st.columns(2)

with col1:
    st.subheader("🎬 Recent Videos")
    if stats['recent_videos']:
        for i, video in enumerate(stats['recent_videos'][:10], 1):
            duration = video['duration']
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "?"
            try:
                dt = datetime.fromisoformat(video['time'])
                time_str = dt.strftime('%H:%M:%S')
            except:
                time_str = "?"
            st.text(f"{i}. [{time_str}] {video['title']} ({duration_str})")
    else:
        st.info("No videos detected yet")

with col2:
    st.subheader("❌ Recent Errors")
    if stats['recent_errors']:
        for i, error in enumerate(stats['recent_errors'], 1):
            try:
                dt = datetime.fromisoformat(error['time'])
                time_str = dt.strftime('%H:%M:%S')
            except:
                time_str = "?"
            st.error(f"[{time_str}] {error['error'][:60]}")
    else:
        st.success("No errors! 🎉")

st.markdown("---")

# Live event feed
st.subheader("📡 Live Event Feed")
if stats['events_timeline']:
    event_expander = st.expander("View Recent Events", expanded=False)
    with event_expander:
        for event in reversed(stats['events_timeline'][-20:]):
            try:
                dt = datetime.fromisoformat(event['time'])
                time_str = dt.strftime('%H:%M:%S')
            except:
                time_str = event['time']
            
            event_type = event['type']
            user_id = event['user']
            
            # Color code by event type
            if 'error' in event_type:
                st.markdown(f"🔴 `{time_str}` **{event_type}** (User: {user_id})")
            elif 'completed' in event_type:
                st.markdown(f"🟢 `{time_str}` **{event_type}** (User: {user_id})")
            else:
                st.markdown(f"🔵 `{time_str}` **{event_type}** (User: {user_id})")
else:
    st.info("Waiting for events...")

# Footer
st.markdown("---")
st.caption("🚀 YouTube Bot Analytics • Data updates every 5 seconds • Made with ❤️ using Streamlit")

