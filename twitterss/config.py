import os


class Config(object):
    """The single place to configure everything configurable in the app."""

    _root = os.getcwd()

    # Path to JSON containing Twitter API credentials
    CREDENTIALS = os.path.join(_root, '.twitter.json')

    # Path to DB to be used. Create if necessary.
    DB_PATH = os.path.join(_root, 'twitter.db')

    # Path to directory containing feeds.
    FEED_ROOT_PATH = os.path.join(_root, 'feeds')

    # Corresponding URL root.
    FEED_ROOT_URL = 'https://bsravan.in/feeds'

    # Path to HTML keeping a list of all RSS feeds.
    FEED_LIST_HTML = os.path.join(_root, 'feeds', 'twitterss.html')

    # Delete tweets older than these seconds if they have already been used in RSS feeds.
    TTL_SECONDS = 86400 * 7

    # Max number of items kept in the RSS feed. Blogs appear to use 10.
    RSS_MAX_ITEMS = 10

    # How quickly to retry after the timeline is all caught up.
    REFRESH_INTERVAL_SECONDS = 600

    # To save error data during crashes.
    CRASH_DIR = os.path.join(_root, 'crash')

    # Daily Digest.
    # HH:MM:SS represents the UTC time at which the next item in the RSS feed should be created.
    # Set to None to disable.
    DAILY_DIGEST = '08:00:00'
