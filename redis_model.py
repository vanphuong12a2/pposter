import base64
import os
import common
import time

NEW_TWEET_ID = 'new_tweet_id'
TWEETS = 'tweet_ids'
TWEET_CONTENT = 'tweet_content'
TWEET_IMG = 'tweet_img'
TWEET_TIME = 'tweet_time'
TWEET_USER = 'tweet_user'

USERS = 'user_emails'
USER_NAME = 'user_name'
USER_IMG = 'user_img'
USER_JOINED = 'user_joined'
USER_LINK = 'user_link'
USER_TWEETS = 'user_tweets'
USER_FOLLOWINGS = 'user_followings'
USER_FOLLOWEDS = 'user_followed'
USER_PASS = 'user_pass'

HUSERLINK = 'userlink_id_hash'
NEW_USERLINK = 'new_userlink'


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
        if self.r.get(NEW_TWEET_ID) is None:
            self.r.set(NEW_TWEET_ID, 0)
        return self.r.incr(NEW_TWEET_ID)

    def get_new_tweet_id(self):
        if self.r.get(NEW_TWEET_ID) is None:
            return 1
        return self.r.get(NEW_TWEET_ID)

    def set_new_userlink(self):
        if self.r.get(NEW_USERLINK) is None:
            self.r.set(NEW_USERLINK, 1000)
        return "user" + str(self.r.incr(NEW_USERLINK))

    def add_tweet(self, content, user, img=None):
        tweet_id = self.set_new_tweet_id()
        ttime = time.time()
        print content, user
        if img is not None:
            self.r.hmset(get_tweet_hkey(tweet_id), {TWEET_CONTENT: content, TWEET_TIME: ttime, TWEET_USER: user, TWEET_IMG: img})
        else:
            self.r.hmset(get_tweet_hkey(tweet_id), {TWEET_CONTENT: content, TWEET_TIME: ttime, TWEET_USER: user})
        self.r.lpush(TWEETS, tweet_id)
        return tweet_id

    def get_tweet(self, tweet_id):
        tname = get_tweet_hkey(tweet_id)
        hkeys = self.r.hkeys(tname)
        tweet = {}
        for k in hkeys:
            val = self.r.hmget(tname, k)[0]
            if k == TWEET_IMG and val:
                if self.config['TEST']:
                    tweet[k] = os.path.join('tmp', val)
                else:
                    tweet[k] = self.s3_get(self.config['BUCKET'], val)
            elif k == TWEET_TIME:
                tweet[k] = common.format_datetime(float(val))
            else:
                tweet[k] = unicode(val, "utf8")
            if k == TWEET_USER:
                tweet['username'] = self.get_username(val)
                tweet['userlink'] = self.get_userlink(val)
        return tweet

    def get_tweets(self, lusers=None, offset=None):
        twits = []
        tweet_ids = self.r.lrange(TWEETS, 0, -1)
        if lusers is not None:
            tweet_ids = [tid for tid in tweet_ids if self.r.hmget(get_tweet_hkey(tid), TWEET_USER)[0] in lusers]
        if offset is not None:
            offset_end = offset + self.config['TWEETS_PER_PAGE']
            tweet_ids = tweet_ids[offset:offset_end]
        for tid in tweet_ids:
            tweet = self.get_tweet(tid)
            twits.append(tweet)
        return twits

    def is_registered(self, email):
        return email in self.r.lrange(USERS, 0, -1)

    def add_user(self, email, name, password, img=None):
        joined = time.time()
        userlink = self.set_new_userlink()
        self.r.hmset(get_user_hkey(email), {USER_NAME: name, USER_PASS: password, USER_JOINED: joined, USER_LINK: userlink})
        self.r.lpush(USERS, email)
        self.r.hset(HUSERLINK, userlink, email)
        return email

    def is_valid_user(self, email, password):
        stored_pass = self.r.hmget(get_user_hkey(email), USER_PASS)[0]
        return stored_pass == password

    def get_username(self, uid):
        return self.r.hmget(get_user_hkey(uid), USER_NAME)[0]

    def get_userid(self, userlink):
        return self.r.hget(HUSERLINK, userlink)

    def get_userlink(self, uid):
        return self.r.hmget(get_user_hkey(uid), USER_LINK)[0]
