"""Layer to fetch data from Twitter."""
import json
import logging
import os
import pickle
import time
from threading import Thread

import twitter

from twitterss import db
from twitterss.config import Config

CREDS_KEYS = {'consumer_key', 'consumer_secret', 'access_token_key', 'access_token_secret'}


def _get_conn() -> twitter.Api:
    """Get a connection to the Twitter API."""
    if not os.path.isfile(Config.CREDENTIALS):
        raise IOError('Could not find credentials at {}.'.format(Config.CREDENTIALS))

    with open(Config.CREDENTIALS) as cfd:
        creds = json.load(cfd)
        if set(creds.keys()) == CREDS_KEYS:
            return twitter.Api(**creds, tweet_mode='extended')
        else:
            raise IOError('%s is expected to have {}.'.format(CREDS_KEYS))


def _save_state(tweets: object):
    """Save the state into a pickle file for future investigations."""
    state = 'tweets_{}.dat'.format(int(time.time()))
    with open(state, 'wb') as pfd:
        pickle.dump(tweets, pfd)
    return state


def _load_state(state_path):
    """Load the state saved in a pickle file. Used only during investigations."""
    with open(state_path, 'rb') as pfd:
        return pickle.load(pfd)


class TimelineFetcher(object):
    """A daemon thread that periodically fetches tweets from home timeline and saves them to DB."""
    def __init__(self):
        self.api = _get_conn()
        thread = Thread(target=self.run, args=())
        thread.daemon = True
        thread.start()

    def run(self):
        tweets = None
        while True:
            try:
                since_id = db.get_most_recent_status_id()
                logging.info('Fetching tweets in timeline since %s.', since_id)
                tweets = self.api.GetHomeTimeline(count=200, since_id=since_id)
                if len(tweets) > 0:
                    db.save_tweets(tweets)
                    logging.info('Fetched and saved %s tweets.', len(tweets))
                else:
                    logging.info('No new tweets in timeline. Sleeping 60s.')
                    time.sleep(60)
            except twitter.error.TwitterError:
                logging.exception('Hit rate-limit while getting home timeline.')
                get_home_timeline_rate_limit = \
                    self.api.CheckRateLimit('https://api.twitter.com/1.1/statuses/home_timeline.json')
                duration = max(int(get_home_timeline_rate_limit.reset - time.time()) + 2, 0)
                logging.info('Hit rate-limits. Sleeping %s seconds.', duration)
                time.sleep(duration)
            except Exception as e:
                logging.exception('Error writing data to DB. Saving current data to %s for investigation.',
                                  _save_state(tweets))
                raise e
