import base64
import os
import common

new_tweet_id = 'new_tweet_id'
tweets = 'tweet_ids'
tweet_content = 'tweet_content'
tweet_img = 'tweet_img'
tweet_time = 'tweet_time'
tweet_user = 'tweet_user'

users = 'user_emails'
user_firstname = 'user_firstname'
user_lastname = 'user_lastname'
user_img = 'user_img'
user_joined = 'user_joined'
user_tweets = 'user_tweets'
user_followings = 'user_followings'
user_followeds = 'user_followed'
user_pass = 'user_pass'


def get_tweet_hkey(tweet_id):
    return "tweet:" + str(tweet_id)


def get_user_hkey(user_email):
    return "user:" + user_email


class RedisModel(object):

    def __init__(self, r, conn, config):
        self.r = r
        self.conn = conn
        self.config = config

    def s3_put(self, bucket, filename, content):
        self.conn.Object(bucket, filename).put(Body=content)

    def s3_get(self, bucket, filename):
        img_data = self.conn.Object(bucket, filename).get()
        return base64.encodestring(img_data['Body'].read())

    def s3_delete(self, bucket, filename):
        self.conn.Object(bucket, filename).delete()

    def set_new_tweet_id(self):
        if self.r.get(new_tweet_id) is None:
            self.r.set(new_tweet_id, 0)
        return self.r.incr(new_tweet_id)

    def get_new_tweet_id(self):
        if self.r.get(new_tweet_id) is None:
            return 1
        return self.r.get(new_tweet_id)

    def add_tweet(self, content, time, user, img=None):
        tweet_id = self.set_new_tweet_id()
        if img is not None:
            self.r.hmset(get_tweet_hkey(tweet_id), {tweet_content: content, tweet_time: time, tweet_user: user, tweet_img: img})
        else:
            self.r.hmset(get_tweet_hkey(tweet_id), {tweet_content: content, tweet_time: time, tweet_user: user})
        self.r.lpush(tweets, tweet_id)
        return tweet_id

    def get_tweets(self, offset):
        twits = []
        if offset < self.r.llen(tweets):
            tweet_ids = self.r.lrange(tweets, offset, min(offset + self.config['TWEETS_PER_PAGE'] - 1, self.r.llen(tweets)))
            for tid in tweet_ids:
                tname = get_tweet_hkey(tid)
                hkeys = self.r.hkeys(tname)
                tweet = {}
                for k in hkeys:
                    val = self.r.hmget(tname, k)[0]
                    if k == tweet_img and val:
                        if self.config['TEST']:
                            tweet[k] = os.path.join('tmp', val)
                        else:
                            tweet[k] = self.s3_get(self.config['BUCKET'], val)
                    elif k == tweet_time:
                        tweet[k] = common.format_datetime(float(val))
                    else:
                        tweet[k] = unicode(val, "utf8")
                twits.append(tweet)
        return twits
