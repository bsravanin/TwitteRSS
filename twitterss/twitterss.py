#! /usr/bin/env python3
"""App for Twitter RSS Feed Generation."""

import logging

from twitterss import db
from twitterss.rss import FeedGenerator
from twitterss.twitter_api import TimelineFetcher

LOGGING_FORMAT = '%(asctime)s %(levelname)s %(message)s'
LOGGING_LEVEL = logging.INFO


def main():
    """Main function that will be run if this is used as a script instead of imported."""
    logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL)

    db.create_schema()

    # Start the daemon that fetches Twitter home timeline.
    TimelineFetcher()

    # Start the daemon that updates RSS feeds.
    FeedGenerator()


if __name__ == '__main__':
    main()
