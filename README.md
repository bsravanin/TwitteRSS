TwitteRSS
=========
A server that fetches a Twitter user's home timeline and creates RSS feeds from it, a separate feed
per followed user.

This is an alternative to [TwitRSS.me](https://twitrss.me), which creates user feeds by scraping
the webpages. The main advantages of using the Twitter API over scraping are stability and ability
to include more relevant content in the RSS items.

The server runs two threads:
1. A thread that uses [python-twitter](https://github.com/bear/python-twitter) to periodically
   retrieve tweets from Twitter, and stores their raw JSONs in a SQLite DB.
2. A thread that periodically retrieves un-processed tweets from the DB and updates the
   corresponding RSS feeds.

The intermediate storage is not necessary, but useful to be able to update the RSS feed logic
without making additional Twitter API calls.

SECURITY
========
When creating credentials for your [Twitter App](https://apps.twitter.com) make sure to get
read-only access.

Save the credentials locally in a JSON like:
```
{
    "consumer_key": "YOUR_CONSUMER_KEY",
    "consumer_secret": "YOUR_CONSUMER_SECRET",
    "access_token_key": "YOUR_ACCESS_TOKEN_KEY",
    "access_token_secret": "YOUR_ACCESS_TOKEN_SECRET"
}
```

Remember to not commit/upload these credentials anywhere.

TODO
====
* Bug fixes and usability improvements based on using for a few days.
* Fix https://github.com/bear/python-twitter/issues/484, and stop using Status._json.
* Switch to lxml instead of hacky hand-rolled RSS feeds.
