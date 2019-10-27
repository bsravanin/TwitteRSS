"""Layer to fetch data from Twitter."""
import json
import logging
import os
import pickle
import time

import twitter
from twitter.error import TwitterError
from requests.exceptions import RequestException

from twitterss import db
from twitterss.config import Config

CREDENTIAL_KEYS = {'consumer_key', 'consumer_secret', 'access_token_key', 'access_token_secret'}


def _get_conn() -> twitter.Api:
    """Get a connection to the Twitter API."""
    if not os.path.isfile(Config.CREDENTIALS):
        raise IOError('Could not find credentials at {}.'.format(Config.CREDENTIALS))

    with open(Config.CREDENTIALS) as cfd:
        credentials = json.load(cfd)
        if set(credentials.keys()) == CREDENTIAL_KEYS:
            return twitter.Api(**credentials, tweet_mode='extended')
        else:
            raise IOError('%s is expected to have {}.'.format(CREDENTIAL_KEYS))


def _save_state(tweets: object):
    """Save the state into a pickle file for future investigations."""
    state = os.path.join(Config.CRASH_DIR, 'tweets_{}.dat'.format(int(time.time())))
    with open(state, 'wb') as pfd:
        pickle.dump(tweets, pfd)
    return state


def fetch_timeline():
    """Periodically fetch tweets from home timeline and save them to DB."""
    api = _get_conn()
    while True:
        tweets = None
        try:
            since_id = db.get_most_recent_status_id()
            logging.info('Fetching tweets in timeline since %s.', since_id)
            tweets = api.GetHomeTimeline(count=200, since_id=since_id)
            if len(tweets) > 0:
                db.save_tweets(tweets)
                logging.info('Fetched and saved %s tweets.', len(tweets))
            else:
                logging.info('No new tweets in timeline. Sleeping %ss.', Config.SLEEP_ON_CATCHING_UP_SECONDS)
                time.sleep(Config.SLEEP_ON_CATCHING_UP_SECONDS)
        except RequestException:
            logging.exception('Unknown exception while making request. Sleeping %ss and refreshing connection.',
                              Config.SLEEP_ON_CATCHING_UP_SECONDS)
            time.sleep(Config.SLEEP_ON_CATCHING_UP_SECONDS)
            api = _get_conn()
        except TwitterError:
            logging.exception('Hit rate-limit while getting home timeline.')
            get_home_timeline_rate_limit = \
                api.CheckRateLimit('https://api.twitter.com/1.1/statuses/home_timeline.json')
            duration = max(int(get_home_timeline_rate_limit.reset - time.time()) + 2, 0)
            logging.info('Hit rate-limits. Sleeping %s seconds.', duration)
            time.sleep(duration)
            api = _get_conn()
        except Exception as e:
            logging.exception('Error writing data to DB. Saving current data to %s for investigation.',
                              _save_state(tweets))
            raise e
