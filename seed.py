"""Create a seeded SQLite database for TicketInsight.

This script creates `data/tickets.db` with tables:
- categories
- agents
- tickets

Run as a script to (re)create the database.
"""
from __future__ import annotations

import os
import sqlite3
import random
from datetime import datetime, timedelta
from typing import List, Tuple


DB_PATH = os.path.join(os.path.dirname(__file__), "tickets.db")


def _ensure_data_dir() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def create_tables(conn: sqlite3.Connection) -> None:
    """Create tables for categories, agents and tickets."""
    cur = conn.cursor()
    cur.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS agents (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        team TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY,
        title TEXT NOT NULL,
        category_id INTEGER NOT NULL REFERENCES categories(id),
        priority TEXT NOT NULL,
        status TEXT NOT NULL,
        requester TEXT NOT NULL,
        assigned_to INTEGER REFERENCES agents(id),
        created_at TEXT NOT NULL,
        resolved_at TEXT
    );
    """)
    conn.commit()


def seed_categories(conn: sqlite3.Connection, names: List[str]) -> None:
    cur = conn.cursor()
    cur.executemany("INSERT OR IGNORE INTO categories(name) VALUES (?)", [(n,) for n in names])
    conn.commit()


def seed_agents(conn: sqlite3.Connection, agents: List[Tuple[str, str]]) -> None:
    cur = conn.cursor()
    cur.executemany("INSERT OR IGNORE INTO agents(name, team) VALUES (?, ?)", agents)
    conn.commit()


def seed_tickets(conn: sqlite3.Connection, count: int = 30) -> None:
    cur = conn.cursor()

    priorities = ["Low", "Medium", "High", "Critical"]
    statuses = ["Open", "In Progress", "Resolved", "Closed"]

    # Load category and agent ids
    cur.execute("SELECT id FROM categories ORDER BY id")
    category_ids = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT id FROM agents ORDER BY id")
    agent_ids = [row[0] for row in cur.fetchall()]

    requesters = [
        "Alice Johnson",
        "Bob Smith",
        "Carla Gomez",
        "Daniel Lee",
        "Eve Kline",
        "Frank Liu",
        "Grace Park",
        "Hassan Omar",
        "Ivy Chen",
        "Jack Turner",
    ]

    titles = [
        "Cannot connect to VPN",
        "Laptop battery drains quickly",
        "Email not syncing on mobile",
        "Forgot network password",
        "Printer printing blank pages",
        "Blue screen when starting",
        "Unable to access shared drive",
        "Two-factor authentication failure",
        "Application crashes on launch",
        "Slow internet performance",
        "Request for software installation",
        "Database query timeout",
        "Permission denied on folder",
        "Password reset request",
        "Phone headset not working",
    ]

    now = datetime.utcnow()
    random.seed(42)

    tickets = []
    for i in range(count):
        title = random.choice(titles)
        category_id = random.choice(category_ids)
        priority = random.choices(priorities, weights=[40, 35, 20, 5], k=1)[0]
        status = random.choices(statuses, weights=[30, 30, 30, 10], k=1)[0]
        requester = random.choice(requesters)
        assigned_to = random.choice(agent_ids + [None])

        created_at = now - timedelta(days=random.randint(0, 90), hours=random.randint(0, 23))

        # resolved_at: 50% chance resolved for non-open statuses
        resolved_at = None
        if status in ("Resolved", "Closed") or random.random() < 0.5:
            resolved_at_dt = created_at + timedelta(days=random.randint(1, 14))
            if resolved_at_dt > now:
                resolved_at_dt = now
            resolved_at = resolved_at_dt.isoformat()

        tickets.append((
            f"{title} (#{i+1})",
            category_id,
            priority,
            status,
            requester,
            assigned_to,
            created_at.isoformat(),
            resolved_at,
        ))

    cur.executemany(
        """
        INSERT INTO tickets (title, category_id, priority, status, requester, assigned_to, created_at, resolved_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tickets,
    )
    conn.commit()


def main() -> None:
    """Create the DB and seed it with sample data."""
    _ensure_data_dir()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = _connect()
    try:
        create_tables(conn)

        categories = [
            "Hardware",
            "Software",
            "Network",
            "Access",
            "Accounts",
            "Database",
            "Security",
            "Telephony",
            "Other",
        ]
        seed_categories(conn, categories)

        agents = [
            ("Olivia Bennett", "Infrastructure"),
            ("Liam Carter", "Infrastructure"),
            ("Noah Wilson", "Applications"),
            ("Emma Davis", "Applications"),
            ("Ava Martinez", "Service Desk"),
            ("Sophia Brown", "Service Desk"),
            ("Mason Garcia", "Security"),
            ("Lucas Rodriguez", "Database"),
        ]
        seed_agents(conn, agents)

        # create at least 30 tickets
        seed_tickets(conn, count=40)

        print(f"Created {DB_PATH} with seeded data.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
