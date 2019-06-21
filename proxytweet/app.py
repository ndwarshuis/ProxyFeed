import html
import re
import logging
from twitterscraper.query import query_tweets_from_user
import rfeed as rf
from flask import Flask, Response
from functools import reduce
from bs4 import BeautifulSoup


class TwitterFeed(rf.Extension):
    def get_namespace(self):
        return {
            "xmlns:atom": "http://www.w3.org/2005/Atom",
            "xmlns:georss": "http://www.georss.org/georss",
            "xmlns:twitter": "http://api.twitter.com",
            "xmlns:dc": "http://purl.org/dc/elements/1.1/",
        }

    def publish(self, handler):
        rf.Serializable.publish(self, handler)
        self._write_element(
            "atom:link",
            None,
            attributes={
                "href": "http://192.168.11.130:5000",
                "rel": "self",
                "type": "application/rss+xml",
            },
        )


class TwitterItem(rf.Serializable):
    def __init__(self):
        rf.Serializable.__init__(self)

    def publish(self, handler):
        rf.Serializable.publish(self, handler)
        self._write_short_element("twitter:source")
        self._write_short_element("twitter:place")

    def _write_short_element(self, name):
        self.handler.startElement(name, {})
        self.handler.endElement(name)


logging.getLogger("twitterscraper").setLevel("ERROR")


def get_user_tweets(user):
    return query_tweets_from_user(user, limit=100)


def format_cdata(content):
    return "<![CDATA[{0}]]>".format(content)


def format_description(html):
    content = reduce(
        lambda s, r: re.sub(*r, s),
        [
            ("</?s>", ""),  # remove strikethroughs
            ("(#|@)<b>", "<b>\\1"),  # make tags entirely bold
            ("</?span[^>]*>", ""),  # remove spans
            ('data-[\\w\\-]+="[^"]+"', ""),  # remove data-* attributes
            ('target="_blank"', ""),  # remove link targets
        ],
        html,
    )
    return format_cdata(content)


def format_title(html):
    # just remove the links and return contents of the text
    return format_cdata(BeautifulSoup(html).p.contents[0])


def format_tweet(tweet, user):
    ln = "https://twitter.com/{0}/status/{1}".format(user, tweet.id)
    return rf.Item(
        title=format_title(tweet.text),
        description=format_description(tweet.html),
        creator="@{0}".format(user),
        link=ln,
        guid=rf.Guid(ln),
        pubDate=tweet.timestamp,
        extensions=[TwitterItem()],
    )


def tweets_to_rss(user):
    return rf.Feed(
        title="Tweets from @{0}".format(user),
        description="Tweets from @{0}, generated by ProxyTweet".format(user),
        link="https://twitter.com/{0}".format(user),
        language="en-us",
        ttl=15,
        items=[format_tweet(t, user) for t in get_user_tweets(user)],
        extensions=[TwitterFeed()],
    )


app = Flask(__name__)


@app.route("/user/<handle>")
def feed(handle):
    rss = html.unescape(tweets_to_rss(handle).rss())
    return Response(rss, mimetype="application/rss+xml")


def main():
    app.run()
