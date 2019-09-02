"""Layer to store Twitter data in a DB. So that RSS re-formatting doesn't require re-fetching old data."""
import json
import logging
import os
import sqlite3
import time
from collections import OrderedDict
from typing import List

from twitter.models import Status

from twitterss.config import Config

STATUS_TABLE = 'statuses'
RSS_COLUMN = 'rss_update'
STATUS_COLUMNS = OrderedDict({
    'id': int,
    'tweet_json': str,
    RSS_COLUMN: int
})
STATUS_INDICES = [RSS_COLUMN]


def _get_conn(read_only: bool = True) -> sqlite3.Connection:
    """Get a connection to the DB."""
    if not os.path.isfile(Config.DB_PATH):
        logging.warning('Could not find an existing DB at %s. Creating one...', Config.DB_PATH)

    if read_only:
        return sqlite3.connect('file:{}?mode=ro'.format(Config.DB_PATH), uri=True)
    else:
        return sqlite3.connect(Config.DB_PATH, isolation_level=None)


def _create_table(conn: sqlite3.Connection, table: str, schema: OrderedDict):
    """Create a table in the DB using the given schema."""
    schema_parts = []
    for key, value in schema.items():
        if key == 'id':
            schema_parts.append('{} INTEGER PRIMARY KEY'.format(key))
        elif value == int:
            schema_parts.append('{} INTEGER'.format(key))
        elif value == str:
            schema_parts.append('{} TEXT'.format(key))
        else:
            raise ValueError('Unknown type {} for column {} while creating table {}'.format(value, key, table))

    conn.execute('CREATE TABLE IF NOT EXISTS {} ({})'.format(table, ', '.join(schema_parts)))


def create_schema():
    """Create the full DB schema. Idempotent."""
    with _get_conn() as conn:
        _create_table(conn, STATUS_TABLE, STATUS_COLUMNS)

        for col_name in STATUS_INDICES:
            index_name = '{}_{}'.format(STATUS_TABLE, col_name)
            conn.execute(
                'CREATE INDEX IF NOT EXISTS {index} ON {table} ({column})'
                .format(index=index_name, table=STATUS_TABLE, column=col_name))


def get_most_recent_status_id() -> [int, None]:
    """Used to fetch newer tweets from Twitter."""
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT MAX(id) FROM {}'.format(STATUS_TABLE))
        for row in cursor.fetchall():
            return row[0]
        else:
            return None


def save_tweets(statuses: List[Status]):
    """Save tweets in the DB. All tweets are marked as not having been RSS fed."""
    if len(statuses) == 0:
        return
    rows = [(status.id, status.AsJsonString(), 0) for status in statuses]
    col_names = ', '.join(["'{}'".format(key) for key in STATUS_COLUMNS])
    col_values = ', '.join(['?'] * len(STATUS_COLUMNS))
    with _get_conn(read_only=False) as conn:
        conn.executemany('INSERT OR IGNORE INTO {} ({}) VALUES ({})'
                         .format(STATUS_TABLE, col_names, col_values), rows)


def get_tweets_to_rss_feed():
    """Get all tweets that are known to have not been included in RSS feeds yet. Read them in order, and reverse
    before passing. Reading them in reverse directly will lead to reading older tweets after newer ones."""
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT tweet_json FROM {} WHERE {} = 0 ORDER BY id LIMIT {}'
                       .format(STATUS_TABLE, RSS_COLUMN, Config.RSS_MAX_ITEMS))
        tweets = [Status.NewFromJsonDict(json.loads(row[0])) for row in cursor.fetchall()]
        tweets.reverse()
        return tweets


def mark_tweets_as_rss_fed(status_ids: List[int]):
    """To be able to periodically delete old data."""
    if len(status_ids) == 0:
        return
    with _get_conn(read_only=False) as conn:
        update_time = int(time.time())
        col_values = ', '.join(['?'] * len(status_ids))
        conn.execute('UPDATE {} SET {} = {} WHERE id IN ({})'
                     .format(STATUS_TABLE, RSS_COLUMN, update_time, col_values), status_ids)

        # Also delete old enough data while we are at it.
        max_rss_time = update_time - Config.DELETE_TWEETS_OLDER_THAN_SECONDS
        conn.execute('DELETE FROM {} WHERE {} > 0 AND {} < {}'
                     .format(STATUS_TABLE, RSS_COLUMN, RSS_COLUMN, max_rss_time))
