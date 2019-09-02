class Config(object):
    """The single place to configure everything configurable in the app."""

    # Path to JSON containing Twitter API credentials
    CREDENTIALS = '.twitter.json'

    # Path to DB to be used. Create if necessary.
    DB_PATH = 'twitter.db'

    # Path to directory containing feeds.
    FEED_ROOT_PATH = 'feeds'

    # Delete tweets older than these seconds if they have already been used in RSS feeds.
    DELETE_TWEETS_OLDER_THAN_SECONDS = 86400 * 7

    # Max number of items kept in the RSS feed. Can be larger than for blogs because tweets are tiny.
    RSS_MAX_ITEMS = 100
