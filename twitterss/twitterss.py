#! /usr/bin/env python3
"""App for Twitter RSS Feed Generation."""

import logging
import os
import sys
from threading import Thread

sys.path.insert(0, os.getcwd())
from twitterss import db
from twitterss import rss
from twitterss import twitter_api

LOGGING_FORMAT = '%(asctime)s %(levelname)s %(message)s'
LOGGING_LEVEL = logging.INFO


def main():
    """Main function that will be run if this is used as a script instead of imported."""
    logging.basicConfig(format=LOGGING_FORMAT, level=LOGGING_LEVEL)

    logging.info('Creating schema.')
    db.create_schema()

    timeline_fetcher = Thread(target=twitter_api.fetch_timeline)
    feed_generator = Thread(target=rss.generate_feeds)

    logging.info('Starting thread to fetch Twitter home timeline.')
    timeline_fetcher.start()

    logging.info('Starting thread to generate RSS feeds.')
    feed_generator.start()

    timeline_fetcher.join()
    feed_generator.join()


if __name__ == '__main__':
    main()
