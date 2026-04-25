import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict
import json

class Database:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT NOT NULL,
                timestamp DATETIME NOT NULL,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id TEXT UNIQUE NOT NULL,
                user_profile TEXT,
                contact_profile TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_contact_id ON chat_records(contact_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON chat_records(timestamp)')

        conn.commit()
        conn.close()

    def insert_chat_records(self, contact_id: str, records: List[Dict]):
        conn = self._get_connection()
        cursor = conn.cursor()

        for record in records:
            cursor.execute('''
                INSERT INTO chat_records (contact_id, timestamp, sender, message)
                VALUES (?, ?, ?, ?)
            ''', (contact_id, record['timestamp'], record['sender'], record['message']))

        conn.commit()
        conn.close()

    def get_chat_records(self, contact_id: str, limit: Optional[int] = None) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()

        query = 'SELECT timestamp, sender, message FROM chat_records WHERE contact_id = ? ORDER BY timestamp'
        if limit:
            query += f' LIMIT {limit}'

        cursor.execute(query, (contact_id,))
        rows = cursor.fetchall()
        conn.close()

        return [{'timestamp': row[0], 'sender': row[1], 'message': row[2]} for row in rows]

    def upsert_profile(self, contact_id: str, user_profile: dict, contact_profile: dict):
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO profiles (contact_id, user_profile, contact_profile, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(contact_id) DO UPDATE SET
                user_profile = excluded.user_profile,
                contact_profile = excluded.contact_profile,
                updated_at = excluded.updated_at
        ''', (contact_id, json.dumps(user_profile, ensure_ascii=False),
              json.dumps(contact_profile, ensure_ascii=False), datetime.now()))

        conn.commit()
        conn.close()

    def get_profile(self, contact_id: str) -> Optional[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT user_profile, contact_profile, updated_at
            FROM profiles WHERE contact_id = ?
        ''', (contact_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'user_profile': json.loads(row[0]) if row[0] else None,
                'contact_profile': json.loads(row[1]) if row[1] else None,
                'updated_at': row[2]
            }
        return None
