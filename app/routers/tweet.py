import re
import json
import html
from os.path import dirname, abspath, join
from functools import reduce
from fastapi import APIRouter, Depends, HTTPException
from dependencies import (
    User,
    oauth2_scheme,
    get_current_active_user,
    get_scraper,
)

router = APIRouter(
    prefix='/tweet',
    tags=['tweet'],
    dependencies=[Depends(get_current_active_user)],
    responses={403: {'description': 'Forbidden'}},
)

reg_id_only = re.compile(r'^(\d+)$')
reg_url = re.compile(r'status/(\d+)')
reg_photo_ext = re.compile(r'\.([^.]+)$')
reg_video_ext = re.compile(r'\.([^.?]+)(\?|$)')
path_log = join(dirname(abspath(__file__)), '../../log/tweets.json')


def get_status_id(url: str) -> str:
    if not url:
        return None
    if reg_id_only.match(url):
        return url
    m = reg_url.search(url)
    if m:
        return m.group(1)
    return None


def get_first(list: list):
    return next(iter(list or []), None)


def get_user(tweet):
    if not tweet:
        return None
    user = tweet['core']['user_results']['result']['legacy']
    return user


def get_text(tweet):
    if not tweet:
        return None
    text = html.unescape(
        tweet['note_tweet']['note_tweet_results']['result']['text']
        if 'note_tweet' in tweet
        else tweet['legacy']['full_text']
    )
    return text


def get_urls(tweet):
    if not tweet:
        return None
    urls = []
    if (
        'note_tweet' in tweet
        and 'urls' in tweet['note_tweet']['note_tweet_results']['result']['entity_set']
    ):
        urls += tweet['note_tweet']['note_tweet_results']['result']['entity_set'][
            'urls'
        ]
    legacy = tweet['legacy']
    if 'extended_entities' in legacy and 'urls' in legacy['extended_entities']:
        urls += legacy['extended_entities']['urls']
    if 'entities' in legacy and 'urls' in legacy['entities']:
        urls += legacy['entities']['urls']
    return {url['url']: url['expanded_url'] for url in urls} if urls else None


def get_info_photo(media):
    url = media['media_url_https']
    return {
        'type': media['type'],
        'url': reg_photo_ext.sub('?format=\\1&name=orig', url),
        'ext': reg_photo_ext.search(url).group(1),
        'shorten': media['url'],
    }


def get_info_video(media):
    url = get_first(
        sorted(
            media['video_info']['variants'],
            key=lambda variant: variant.get('bitrate', 0),
            reverse=True,
        )
    ).get('url')
    ext = reg_video_ext.search(url).group(1)
    return {
        'type': media['type'],
        'url': url,
        'ext': ext,
        'shorten': media['url'],
    }


get_mediainfo = {
    'photo': get_info_photo,
    'video': get_info_video,
    'animated_gif': get_info_video,
}


def get_media(media):
    media_type = media['type']
    if not media_type in get_mediainfo:
        print(f"Unknown media type: {media_type}")
        return None
    return get_mediainfo[media_type](media)


def get_medias(tweet):
    if not tweet:
        return None
    legacy = tweet['legacy']
    # print(f"extended_entities: {legacy.get('extended_entities')}")
    medias = (
        legacy['extended_entities'].get('media')
        if 'extended_entities' in legacy
        else legacy['entities'].get('media') if 'entities' in legacy else None
    )
    # print(f"medias: {medias}")
    return [get_media(media) for media in medias] if medias else None


class Detail:

    def __init__(self, tweet):
        user = get_user(tweet)
        self.user = {
            'name': user['name'],
            'screen_name': user['screen_name'],
        }
        self.text = get_text(tweet)
        self.urls = get_urls(tweet)
        self.medias = get_medias(tweet)


def get_tweet(data):
    result = data['data']['tweetResult']['result']
    if result['__typename'] == 'Tweet':
        return result
    elif result['__typename'] == 'TweetWithVisibilityResults':
        return result['tweet']
    else:
        print(f"Type missmatch: {result['__typename']}")
        return None


@router.post('/details')
def get_details_by_ids(urls: list[str]):
    ids = [get_status_id(url) for url in urls]
    scraper = get_scraper()
    print(f"rate_limit: {scraper.rate_limit}")
    try:
        tweets = scraper.tweets_by_id(ids)
        if scraper.rate_limit:
            print(f"rate_limit: {scraper.rate_limit}")
            if len(tweets) == 0 and scraper.rate_limit.remaining == 0:
                raise HTTPException(
                    status_code=429,
                    detail='Too Many Requests',
                    headers={'Retry-After': scraper.rate_limit.wait},
                )
        with open(path_log, 'wt') as f:
            f.write(json.dumps(tweets, indent=2))
        details = {
            tweet['rest_id']: Detail(tweet)
            for tweet in [get_tweet(data) for data in tweets]
        }
        return details
    except Exception as e:
        print(e)
        return e
