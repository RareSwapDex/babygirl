import sqlite3
import time

# Connect to database
conn = sqlite3.connect('babygirl.db')
c = conn.cursor()

print('=== DEBUGGING PROACTIVE ENGAGEMENT ===')
print()

# Check if spam_tracking table has data
print('1. SPAM_TRACKING TABLE:')
c.execute('SELECT COUNT(*) FROM spam_tracking')
total_spam_records = c.fetchone()[0]
print(f'Total records: {total_spam_records}')

if total_spam_records > 0:
    c.execute('SELECT DISTINCT group_id FROM spam_tracking')
    groups = c.fetchall()
    print(f'Groups with activity: {len(groups)}')
    for group in groups[:5]:  # Show first 5
        print(f'  Group ID: {group[0]}')
        
        # Check last message time for this group
        c.execute('SELECT MAX(timestamp) FROM spam_tracking WHERE group_id = ?', (group[0],))
        last_timestamp = c.fetchone()[0]
        if last_timestamp:
            last_time = time.time() - last_timestamp
            print(f'    Last activity: {int(last_time/60)} minutes ago')
else:
    print('No groups found in spam_tracking!')

print()

# Check proactive_state table
print('2. PROACTIVE_STATE TABLE:')
try:
    c.execute('SELECT COUNT(*) FROM proactive_state')
    proactive_records = c.fetchone()[0]
    print(f'Proactive state records: {proactive_records}')

    if proactive_records > 0:
        c.execute('SELECT * FROM proactive_state')
        states = c.fetchall()
        for state in states:
            print(f'  Group: {state[0]}, Dead Chat Active: {state[1]}, Last Sent: {state[2]}')
except Exception as e:
    print(f'Error accessing proactive_state table: {e}')

print()

# Check recent activity for any group
print('3. RECENT ACTIVITY CHECK:')
current_time = int(time.time())
one_hour_ago = current_time - 3600

c.execute('SELECT group_id, COUNT(*), MAX(timestamp) FROM spam_tracking WHERE timestamp > ? GROUP BY group_id', (one_hour_ago,))
recent_activity = c.fetchall()

if recent_activity:
    print('Groups with activity in last hour:')
    for group_id, count, last_ts in recent_activity:
        print(f'  Group {group_id}: {count} messages, last: {int((current_time-last_ts)/60)}min ago')
else:
    print('No activity in any group in the last hour')
    
    # Check groups that had activity before but not in last hour
    print('Groups that had activity before but silent for 1+ hours:')
    c.execute('SELECT group_id, COUNT(*), MAX(timestamp) FROM spam_tracking WHERE timestamp <= ? GROUP BY group_id ORDER BY MAX(timestamp) DESC LIMIT 5', (one_hour_ago,))
    silent_groups = c.fetchall()
    
    for group_id, count, last_ts in silent_groups:
        hours_silent = int((current_time - last_ts) / 3600)
        print(f'  Group {group_id}: Silent for {hours_silent} hours')

print()

# Check conversation_memory table
print('4. CONVERSATION_MEMORY TABLE:')
c.execute('SELECT COUNT(*) FROM conversation_memory')
memory_records = c.fetchone()[0]
print(f'Conversation memory records: {memory_records}')

if memory_records > 0:
    c.execute('SELECT group_id, COUNT(*), MAX(timestamp) FROM conversation_memory GROUP BY group_id')
    memory_groups = c.fetchall()
    print('Groups with conversation memory:')
    for group_id, count, last_ts in memory_groups:
        hours_ago = int((current_time - last_ts) / 3600)
        print(f'  Group {group_id}: {count} memories, last: {hours_ago}h ago')

print()

# Check if tables exist
print('5. TABLE STRUCTURE:')
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = c.fetchall()
print('Existing tables:')
for table in tables:
    print(f'  {table[0]}')

conn.close()
print()
print('=== DEBUG COMPLETE ===') 