"""Optional device state is separate from farm records and portable backups."""
PUSH_SCHEMA = '''
CREATE TABLE IF NOT EXISTS push_subscriptions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,endpoint TEXT NOT NULL UNIQUE,p256dh TEXT NOT NULL,auth TEXT NOT NULL,new_records INTEGER NOT NULL,daily_reminder INTEGER NOT NULL,language TEXT NOT NULL,since_seq INTEGER NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS push_deliveries(subscription_id TEXT NOT NULL,event_key TEXT NOT NULL,category TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',attempts INTEGER NOT NULL DEFAULT 0,next_attempt REAL NOT NULL DEFAULT 0,lease_until REAL NOT NULL DEFAULT 0,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(subscription_id,event_key));
CREATE INDEX IF NOT EXISTS push_deliveries_pending ON push_deliveries(status,next_attempt);
'''
