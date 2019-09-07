TwitteRSS
=========
A server that fetches a Twitter user's home timeline and creates RSS feeds from it, a separate feed
per followed user.

[Example Feeds](https://bsravan.in/feeds/twitterss.html)

Design
======
The server runs two threads:
1. A thread that uses [python-twitter](https://github.com/bear/python-twitter) to periodically
   retrieve tweets from Twitter, and stores their raw JSONs in a SQLite DB.
2. A thread that periodically retrieves un-processed tweets from the DB and updates the
   corresponding RSS feeds.

The intermediate storage is not necessary, but useful to be able to update the RSS feed logic
without making additional Twitter API calls.

vs TwitRSS.me
=============
[TwitRSS.me](https://twitrss.me) is a nice and popular alternative to this application. It creates
Twitter user/search feeds by scraping their web pages. Its main advantage is that it is a service
readily usable by anyone.

It has a few disadvantages:
* Case-sensitive usernames, e.g. @MattYglesias and not @mattyglesias.
* So-so support for media and metadata.
* Brittle to major UI changes.

By using the Twitter API, TwitteRSS overcomes all 3 disadvantages, but has other disadvantages:
* It cannot unwind URLs and show the corresponding image, headline, and snippet. See
  [this python-twitter issue](https://github.com/bear/python-twitter/issues/515) to know more.
* It cannot display polls, because Twitter provides these only in its enterprise APIs.
* It is not available as a service.
* It uses the application's home timeline instead of user timelines. So getting the RSS feed of a
  new user involves following a new user.

The latter two disadvantages can be resolved without much effort, but this project was meant as a
POC for my personal usage, so I am not in a hurry to make those changes. Opening up access also
involves a lot of maintenance effort which I am not excited about. In the meantime, open a GitHub
issue or contact me directly to request the feed URL of your choice.

Security
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
* Switch to GET statuses/user_timeline.
* Add a "register timeline" page and open up access.
* Fix https://github.com/bear/python-twitter/issues/484, and stop using Status._json.
* Switch to lxml instead of hacky hand-rolled RSS feeds.
