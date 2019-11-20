"""Layer to create RSS feeds."""

import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from io import StringIO
from typing import List
from xml.sax.saxutils import escape

from twitter.models import Status

from twitterss import db
from twitterss.config import Config

TEMPLATES_ROOT = os.path.join(os.path.dirname(__file__), 'templates')
CHANNEL_XML_TEMPLATE = os.path.join(TEMPLATES_ROOT, 'channel.xml')
FEEDS_HTML_TEMPLATE = os.path.join(TEMPLATES_ROOT, 'feeds.html')
RSS_TIME_FORMAT = '%a, %d %b %Y %H:%M:%S UTC'  # Like 'Mon, 30 Sep 2002 01:56:02 GMT'


def _get_user_url(username: str) -> str:
    return 'https://twitter.com/{}'.format(username)


def _get_tweet_url(username: str, tid: int) -> str:
    return 'https://twitter.com/{}/status/{}'.format(username, tid)


def _get_feed_name(username: str) -> str:
    return '{}_rss.xml'.format(username.lower())


def _get_feed_url(username: str) -> str:
    return '{}/{}'.format(Config.FEED_ROOT_URL, _get_feed_name(username))


def _rss_time_format(epoch: int) -> str:
    return datetime.fromtimestamp(epoch).strftime(RSS_TIME_FORMAT)


def _rss_time_now() -> str:
    return datetime.utcnow().strftime(RSS_TIME_FORMAT)


def _initialize_feed(username: str, profile_image_url: str) -> str:
    """Initialize RSS feed for user as an XML string."""
    with open(CHANNEL_XML_TEMPLATE) as cfd:
        channel_xml = cfd.read()
    return channel_xml.format(
        username=username,
        feed_url=_get_feed_url(username),
        user_url=_get_user_url(username),
        last_build_date=_rss_time_now(),
        profile_image_url=profile_image_url,
    )


def _get_current_rss_items(feed_path: str) -> List[str]:
    """Return items in existing RSS feed of user as a list of XML strings."""
    if os.path.isfile(feed_path):
        with open(feed_path) as xfd:
            feed_str = xfd.read()
        items = ['<item>{}'.format(ip) for ip in feed_str.split('<item>')[1:]]
        if len(items) > 0:
            items[-1] = items[-1].replace('</channel>', '').replace('</rss>', '')
        return items
    return []


class EnhancedTweet(object):
    """A wrapper around Status, with helper attributes and methods to assist creating a corresponding RSS item."""

    def __init__(self, tweet: Status):
        self.inner = tweet
        self.id = tweet.id
        self.display_name = escape(tweet.user.name)
        self.username = tweet.user.screen_name
        self.url = _get_tweet_url(tweet.user.screen_name, tweet.id)
        self.is_retweet = tweet.retweeted_status is not None
        self.is_reply = tweet.in_reply_to_status_id is not None and tweet.in_reply_to_screen_name is not None
        self.has_quoted = tweet.quoted_status is not None
        self.raw_json = tweet._json

    def get_rss_item(self) -> str:
        """The main method of EnhancedTweet. Because namespaces are not available at the element level, this uses
        custom property names."""
        base_item = '''
<item>
    <title>{display_name} tweeted {id}</title>
    <link>{url}</link>
    <pubDate>{pub_date}</pubDate>
    <dc:creator>{display_name}</dc:creator>
    <category>Tweets</category>
    <guid isPermaLink="false">{url}</guid>
    <description />
    <content:encoded><![CDATA[
        RSS_ITEM_PLACE_HOLDER
    ]]></content:encoded>
</item>'''.format(
            display_name=self.display_name,
            id=self.id,
            url=self.url,
            pub_date=_rss_time_format(self.inner.created_at_in_seconds),
        )
        try:
            return base_item.replace('RSS_ITEM_PLACE_HOLDER', self.get_content())
        except:
            logging.exception('Failed to create RSS item for %s.', self.url)
            return base_item.replace('RSS_ITEM_PLACE_HOLDER', 'RSS Error. Please read {} directly.'.format(self.url),)

    def _add_sanitized_text(self, content: StringIO):
        tweet = self.inner
        text = (tweet.full_text or tweet.text or '').replace('\n', '<br/>')
        if self.has_quoted:
            quoted_status = self.inner.quoted_status
            quoted_url = _get_tweet_url(quoted_status.user.screen_name, quoted_status.id).lower()
        else:
            quoted_url = None
        urls = {url['url']: url['expanded_url'] for url in self.raw_json.get('urls', [])}
        for url in self.raw_json.get('media', []):
            urls[url['url']] = 'REMOVE_MEDIA_URL'
        for url, expanded_url in urls.items():
            if expanded_url == 'REMOVE_MEDIA_URL' or (quoted_url is not None and quoted_url == expanded_url.lower()):
                text = text.replace(url, '')
            else:
                text = text.replace(url, '<a href="{}">{}</a>'.format(expanded_url, expanded_url))
        for um in self.raw_json.get('user_mentions', []):
            username = um['screen_name']
            user_url = _get_user_url(username)
            regex = re.compile(r"@%s\b" % username, re.IGNORECASE)  # double, not single quotes.
            text = re.sub(regex, '<a href="{}">@{}</a>'.format(user_url, username), text)
        if text != '':
            content.write('<p>{text}</p>\n'.format(text=text.strip()))

    def _add_photo(self, content: StringIO, media_url: str = None, alt_text: str = None):
        if media_url is not None:
            content.write(
                '<p><a href="{img_url}"><img src="{img_url}" alt="{ext_alt_text}" width="640" height="480" '
                'class="aligncenter size-large" sizes="(max-width: 640px) 100vw, 640px" /></a></p>\n'.format(
                    img_url=media_url, ext_alt_text=alt_text or ''
                )
            )

    def _add_media(self, content: StringIO):
        for media in self.raw_json.get('media', []):
            media_type = media.get('type')
            if media_type == 'photo':
                self._add_photo(content, media.get('media_url_https'), media.get('ext_alt_text'))
            elif media_type in ['animated_gif', 'video']:
                video = media.get('video_info', {}).get('variants', [None])[-1]
                if video is not None:
                    content.write(
                        '''
<p><a href="{video_url}"><video width="640" height="480" controls>
    <source src="{video_url}" type="{content_type}">
    This browser or application does not appear to support the video tag.
</video></a></p>
'''.format(
                            video_url=video['url'], content_type=video['content_type']
                        )
                    )
                else:
                    media_url = media.get('expanded_url') or media.get('url') or media.get('media_url_https')
                    self._add_photo(content, media_url)
            else:
                content.write('<p>This tweet has media elements that cannot be rendered in this RSS feed.</p>\n')

    def get_content(self) -> str:
        """The crux of RSS content creation. Whereas get_rss_item puts together the XML, this method creates the
        HTML content that becomes the content of the RSS item."""
        content = StringIO()
        tweet = self.inner
        if self.is_retweet:
            content.write('<p>{name} Retweeted</p>\n'.format(name=self.display_name))
            content.write(EnhancedTweet(tweet.retweeted_status).get_content())
            return content.getvalue()

        if self.is_reply:
            reply_url = _get_tweet_url(tweet.in_reply_to_screen_name, tweet.in_reply_to_status_id)
            content.write(
                '<p>Replying to <a href="{reply_url}">@{username}</a></p>\n'.format(
                    reply_url=reply_url, username=tweet.in_reply_to_screen_name
                )
            )

        content.write('<blockquote>\n')
        self._add_sanitized_text(content)
        self._add_media(content)

        content.write('</blockquote>\n')
        content.write(
            '<p><img src="{img_url}" width="32" height="32" class="alignleft" /> '
            '-- {name} (@{username}) <a href="{url}">{created_at}</a></p>\n'.format(
                img_url=tweet.user.profile_image_url_https,
                name=self.display_name,
                username=self.username,
                url=self.url,
                created_at=tweet.created_at,
            )
        )

        if self.has_quoted:
            content.write('<p>{name} tweeted this while quoting the below tweet.</p>\n'.format(name=self.display_name))
            content.write(EnhancedTweet(tweet.quoted_status).get_content())

        return content.getvalue()


def _update_feed(username: str, tweets: List[Status]):
    """Assumption: All tweets in the list are owned by the username, and are to be written to that user's RSS feed."""
    feed_path = os.path.join(Config.FEED_ROOT_PATH, _get_feed_name(username))
    profile_image_url = tweets[0].user.profile_image_url_https or 'https://abs.twimg.com/favicons/win8-tile-144.png'
    feed = _initialize_feed(username, profile_image_url)
    rss_items = []
    for tweet in tweets:
        if (
            tweet.in_reply_to_status_id is not None
            and tweet.retweeted_status is None
            and tweet.in_reply_to_user_id != tweet.user.id
        ):
            # Home timeline shows replies between users that "I" follow. They wouldn't show up on a regular
            # User timeline. So skipping them. Based on tests, only about 1% of tweets fall under this category.
            logging.info(
                '%s is a reply to someone else, and not a retweet. Skipping...',
                _get_tweet_url(tweet.user.screen_name, tweet.id),
            )
            continue
        else:
            rss_items.append(EnhancedTweet(tweet).get_rss_item())
    if len(rss_items) == 0:
        return
    max_old_items = Config.RSS_MAX_ITEMS - len(tweets)
    if max_old_items > 0:
        rss_items.extend(_get_current_rss_items(feed_path)[:max_old_items])
    full_feed = '{feed_header}{items}\n</channel>\n</rss>'.format(
        feed_header=feed.replace('</channel>', '').replace('</rss>', ''), items='\n'.join(rss_items),
    )
    with open(feed_path, 'w') as xfd:
        xfd.write(re.sub(r'\n+', '\n', full_feed))


def _update_feeds_html():
    """Write Config.FEED_LIST_HTML, a useful page that lists all the RSS feeds available from this app at any given
    moment."""
    with open(FEEDS_HTML_TEMPLATE) as hfd:
        full_html = hfd.read()
    full_trs = []
    for username, display_name, timestamp in db.get_all_users():
        name_td = '<td>{}</td>'.format(display_name)
        twitter_td = '<td><a href="{}">@{}</a></td>'.format(_get_user_url(username), username)
        feed_td = '<td><a href="{}">{}</a></td>'.format(_get_feed_url(username), _get_feed_name(username))
        data_tstamp = _rss_time_format(timestamp)
        timestamp_td = '<td class="rss_update" data-tstamp="{}">{}</td>'.format(data_tstamp, data_tstamp)
        full_trs.append('<tr>{}{}{}{}</tr>'.format(name_td, twitter_td, feed_td, timestamp_td))

    full_html = full_html.replace('PLACEHOLDER', '\n'.join(full_trs))
    with open(Config.FEED_LIST_HTML, 'w') as hfd:
        hfd.write(full_html)


def _generate_feeds_once(mark_tweets_as_rss_fed: bool = True) -> int:
    """Fetch new tweets from the DB and update their corresponding RSS feeds."""
    all_new_tweets = db.get_tweets_to_rss_feed()
    if len(all_new_tweets) > 0:
        username_to_tweets = defaultdict(list)
        for tweet in all_new_tweets:
            username_to_tweets[tweet.user.screen_name].append(tweet)
        for username, tweets in username_to_tweets.items():
            logging.info('Updating RSS feed of %s with %s tweets.', username, len(tweets))
            _update_feed(username, tweets)
            if mark_tweets_as_rss_fed:
                db.mark_tweets_as_rss_fed(username, tweets[0].user.name, [tweet.id for tweet in tweets])
        _update_feeds_html()
    return len(all_new_tweets)


def generate_feeds():
    """Periodically update RSS feeds with new tweets."""
    os.makedirs(Config.FEED_ROOT_PATH, exist_ok=True)
    while True:
        items_created = _generate_feeds_once()
        if items_created == 0:
            logging.info(
                'No new tweets in DB. Sleeping %ss.', Config.SLEEP_ON_CATCHING_UP_SECONDS,
            )
            time.sleep(Config.SLEEP_ON_CATCHING_UP_SECONDS)
