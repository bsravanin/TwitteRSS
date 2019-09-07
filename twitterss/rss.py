"""Layer to create RSS feeds."""

import logging
import os
import re
import time
import xml.etree.ElementTree as ElementTree
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
HEADER = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
    xmlns:atom="http://www.w3.org/2005/Atom"
    xmlns:sy="http://purl.org/rss/1.0/modules/syndication/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:content="http://purl.org/rss/1.0/modules/content/">
'''
NS_SPECIAL_HANDLING = {
    'atom:link': [r'xmlns_atom_link', r'ns\d:link'],
    'sy:updatePeriod': [r'xmlns_sy_update_period', r'ns\d:updatePeriod'],
    'sy:updateFrequency': [r'xmlns_sy_update_frequency', r'ns\d:updateFrequency'],
    'dc:creator': [r'xmlns_dc_creator', r'ns\d:creator'],
    'content:encoded': [r'xmlns_content_encoded', r'ns\d:encoded'],
}
RSS_TIME_FORMAT = '%a, %d %b %Y %H:%M:%S UTC'   # Like 'Mon, 30 Sep 2002 01:56:02 GMT'


def _get_user_url(username: str) -> str:
    return 'https://twitter.com/{}'.format(username)


def _get_tweet_url(username: str, tid: int) -> str:
    return 'https://twitter.com/{}/status/{}'.format(username, tid)


def _get_feed_name(username: str) -> str:
    return '{}_rss.xml'.format(username.lower())


def _get_feed_url(username: str) -> str:
    return '{}/{}'.format(Config.FEED_ROOT_URL, _get_feed_name(username))


def get_feed(feed_path: str, username: str, profile_image_url: str) -> ElementTree:
    """Return RSS feed of user as an XML. Initialize if necessary."""
    if os.path.isfile(feed_path):
        return ElementTree.parse(feed_path)
    with open(CHANNEL_XML_TEMPLATE) as cfd:
        channel_xml = cfd.read()
    root_str = channel_xml.format(
        username=username, feed_url=_get_feed_url(username), user_url=_get_user_url(username),
        profile_image_url=profile_image_url)
    return ElementTree.ElementTree(ElementTree.fromstring(root_str))


def _rss_time_format(epoch: int) -> str:
    return datetime.fromtimestamp(epoch).strftime(RSS_TIME_FORMAT)


def _rss_time_now() -> str:
    return datetime.utcnow().strftime(RSS_TIME_FORMAT)


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

    def get_rss_item(self) -> ElementTree.Element:
        """The main method of EnhancedTweet. Because namespaces are not available at the element level, this uses
        custom property names."""
        base_item = '''
<item>
    <title>{display_name} tweeted {id}</title>
    <link>{url}</link>
    <pubDate>{pub_date}</pubDate>
    <xmlns_dc_creator>{display_name}</xmlns_dc_creator>
    <category>Tweets</category>
    <guid isPermaLink="false">{url}</guid>
    <description />
    <xmlns_content_encoded>RSS_ITEM_PLACE_HOLDER</xmlns_content_encoded>
</item>'''.format(display_name=self.display_name, id=self.id, url=self.url,
                  pub_date=_rss_time_format(self.inner.created_at_in_seconds))
        item = base_item.replace('RSS_ITEM_PLACE_HOLDER', self.get_content())
        try:
            return ElementTree.fromstring(item)
        except:
            logging.exception('Failed to create RSS item for %s. Item: %s', self.url, item)
            item = base_item.replace('RSS_ITEM_PLACE_HOLDER', 'RSS Error. Please read {} directly.'.format(self.url))
            return ElementTree.fromstring(item)

    def _add_sanitized_text(self, content: StringIO):
        tweet = self.inner
        text = escape(tweet.full_text or tweet.text or '').replace('\n', '<br/>')
        # for user in self.raw_json.get('user_mentions', []):
        #     username = user.get('screen_name')
        #     if username is not None:
        #         href = '<a href="{}">@{}</a>'.format(_get_user_url(username), username)
        #         text = re.sub(r'@%s\b' % username, href, text, flags=re.IGNORECASE)
        if text != '':
            content.write('<p>{text}</p>\n'.format(text=text))

    def _add_photo(self, content: StringIO, media_url: str = None, alt_text: str = None):
        if media_url is not None:
            content.write(
                '<p><a href="{img_url}"><img src="{img_url}" alt="{ext_alt_text}" width="640" height="480" '
                'class="aligncenter size-large" sizes="(max-width: 640px) 100vw, 640px" /></a></p>\n'
                .format(img_url=media_url, ext_alt_text=alt_text or ''))

    def _add_media(self, content: StringIO):
        for media in self.raw_json.get('media', []):
            media_type = media.get('type')
            if media_type == 'photo':
                self._add_photo(content, media.get('media_url_https'), media.get('ext_alt_text'))
            elif media_type in ['animated_gif', 'video']:
                video = media.get('video_info', {}).get('variants', [None])[-1]
                if video is not None:
                    content.write('''
<p><object width="640" height="480">
<param name="movie" value="{video}"></param>
<param name="wmode" value="transparent"></param>
<embed src="{video}" type="{content_type}" wmode="transparent" width="640" height="480"></embed>
</object>
<noembed><a href="{video}">Click here to view video</a></noembed>
</p>'
'''.format(video=video['url'], content_type=video['content_type']))
                else:
                    media_url = media.get('expanded_url') or media.get('url') or media.get('media_url_https')
                    self._add_photo(content, media_url)
            else:
                content.write('<p>This tweet has media elements that cannot be rendered in this RSS feed.</p>')

    def _add_urls(self, content: StringIO):
        if self.has_quoted:
            quoted_status = self.inner.quoted_status
            quoted_url = _get_tweet_url(quoted_status.user.screen_name, quoted_status.id)
        else:
            quoted_url = None
        urls = self.raw_json.get('urls', [])
        if quoted_url in urls:
            urls.remove(quoted_url)
        if len(urls) > 0:
            content.write('<p>URLs mentioned in this tweet:</p>')
            for url in urls:
                final_url = url.get('expanded_url') or url.get('url')
                if final_url is not None:
                    sanitized_url = escape(final_url)
                    content.write('<p><a href="{}">{}</a></p>'.format(sanitized_url, sanitized_url))

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
            content.write('<p>Replying to <a href="{reply_url}">@{username}</a></p>\n'.format(
                reply_url=reply_url, username=tweet.in_reply_to_screen_name))

        content.write('<blockquote>\n')
        self._add_sanitized_text(content)
        self._add_media(content)
        self._add_urls(content)

        content.write('</blockquote>\n')
        content.write(
            '<p>-- {name} (@{username}) <a href="{url}">{created_at}</a></p>\n'.format(
                name=self.display_name, username=self.username, url=self.url, created_at=tweet.created_at))

        if self.has_quoted:
            content.write('<p>{name} tweeted this while quoting the below tweet.</p>'.format(name=self.display_name))
            content.write(EnhancedTweet(tweet.quoted_status).get_content())

        return content.getvalue()


def _get_namespace_handled_xml(rss: ElementTree.Element) -> str:
    """Because xml.etree doesn't seem to handle namespaces well and because EnhancedTweet deals only with XML elements
    without access to the entire tree, customer property names are (hackily) converted into namespaces and a namespsace
    section is added to the root."""
    feed_str = ElementTree.tostring(rss, encoding='unicode', method='xml')
    for tag, regexes in NS_SPECIAL_HANDLING.items():
        for regex in regexes:
            feed_str = re.sub(regex, tag, feed_str)
    feed_str = re.sub(r'\n+', '\n', feed_str)\
        .replace('</item></channel>', '</item>\n</channel>')\
        .replace('<content:encoded>', '<content:encoded><![CDATA[')\
        .replace('</content:encoded>', ']]></content:encoded>')
    return re.sub(r'^.* version="2.0">?', HEADER, feed_str)


def _update_feed(username: str, tweets: List[Status]):
    """Assumption: All tweets in the list are owned by the username, and are to be written to that user's RSS feed."""
    feed_path = os.path.join(Config.FEED_ROOT_PATH, _get_feed_name(username))
    profile_image_url = tweets[0].user.profile_image_url_https or 'https://abs.twimg.com/favicons/win8-tile-144.png'
    feed = get_feed(feed_path, username, profile_image_url)
    rss = feed.getroot()
    channel = rss[0]
    min_remove_idx = Config.RSS_MAX_ITEMS - len(tweets)
    for index, item in enumerate(channel.iter('item')):
        if index > min_remove_idx:
            channel.remove(item)
    for index, tweet in enumerate(tweets):
        # TODO: Hard-coded assumption that items start at the 10th place as channel children.
        channel.insert(index + 10, EnhancedTweet(tweet).get_rss_item())
    for lastBuildDate in channel.iter('lastBuildDate'):
        lastBuildDate.text = _rss_time_now()
    feed_str = _get_namespace_handled_xml(rss)
    with open(feed_path, 'w') as xfd:
        xfd.write(feed_str)


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
        timestamp_td = '<td>{}</td>'.format(_rss_time_format(timestamp))
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
            logging.info('No new tweets in DB. Sleeping %ss.', Config.SLEEP_ON_CATCHING_UP_SECONDS)
            time.sleep(Config.SLEEP_ON_CATCHING_UP_SECONDS)
