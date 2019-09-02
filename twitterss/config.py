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

    # Delete tweets older than these seconds if they have already been used in RSS feeds.
    DELETE_TWEETS_OLDER_THAN_SECONDS = 86400 * 7

    # Max number of items kept in the RSS feed. Can be larger than for blogs because tweets are tiny.
    RSS_MAX_ITEMS = 100

    # How quickly to retry after the timeline is all caught up.
    SLEEP_ON_CATCHING_UP_SECONDS = 60
