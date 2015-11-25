import base64
import os
import time
from werkzeug import secure_filename
import redis
import boto3
import sys
sys.path.append("../")
import lib.common as common

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
USER_ALIAS = 'user_alias'
USER_TWEETS = 'user_tweets'
USER_PASS = 'user_pass'

HUSERALIAS = 'useralias_id_hash'
NEW_USERALIAS = 'new_useralias'

NEW_COMMENT_ID = 'new_comment_id'
COMMENT_USER = 'comment_user'
COMMENT_CONTENT = 'comment_content'
COMMENT_TIME = 'comment_time'
COMMENT_USERALIAS = 'comment_useralias'
COMMENT_USERNAME = 'comment_username'
COMMENTS = 'comments'


NEW_NOTI_ID = 'new_noti_id'
NOTI_ID = 'noti_id'
NOTI_CREATOR = 'noti_creator'
NOTI_TYPE = 'noti_type'
NOTI_TWEET = 'noti_tweet'
NOTI_TIME = 'noti_time'
NOTI_READ = 'noti_read'

FOLLOW_NOTI = 'follow_noti'
COMMENT_NOTI = 'comment_noti'

HASHTAGS = 'hashtags'


def get_tweet_hkey(tweet_id):
    return "tweet:" + str(tweet_id)


def get_user_hkey(user_email):
    return "user:" + user_email


def get_user_followers_hkey(userid):
    return "followers:" + userid


def get_user_followings_hkey(userid):
    return "followings:" + str(userid)


def get_tweet_comments_list(tweet_id):
    return "comments:" + str(tweet_id)


def get_comment_hkey(cmt_id):
    return "cmt:" + str(cmt_id)


def get_noti_hkey(noti_id):
    return "noti:" + str(noti_id)


def get_user_notis_list(user_id):
    return "notis:" + str(user_id)


def get_hashtag_list(hashtag):
    return "hashtag:" + str(hashtag)


class RedisModel(object):

    def __init__(self, config):
        if not config['TESTING']:
            r = redis.StrictRedis(host=config['REDIS_HOST'], port=config['REDIS_PORT'], db=config['REDIS_DB'])
        else:
            r = redis.StrictRedis(host=config['REDIS_HOST'], port=config['REDIS_PORT'], db=config['REDIS_TEST_DB'])
        if config['LOCAL']:
            conn = None
        else:
            conn = boto3.resource('s3')
        self.r = r
        self.conn = conn
        self.config = config

    def flush_db(self):
        self.r.flushdb()

    ############# HASHTAG ##############

    def get_trending_tags(self):
        counts = [self.r.llen(get_hashtag_list(ht)) for ht in self.r.lrange(HASHTAGS, 0, -1)]
        indexes = sorted(range(len(counts)), key=lambda i: counts[i], reverse=True)[:5]
        return [self.r.lindex(HASHTAGS, i) for i in indexes]

    ############# NOTIFICATION ##############

    def set_new_noti_id(self):
        if self.r.get(NEW_NOTI_ID) is None:
            self.r.set(NEW_NOTI_ID, 0)
        return self.r.incr(NEW_NOTI_ID)

    def add_noti(self, uid, creator, ntype, read=False, tweet=None):
        # called by add_followers and add_comment
        noti_id = self.set_new_noti_id()
        ntime = time.time()
        if tweet:
            self.r.hmset(get_noti_hkey(noti_id), {NOTI_CREATOR: creator, NOTI_TYPE: ntype, NOTI_TIME: ntime, NOTI_READ: read, NOTI_TWEET: tweet})
        else:
            self.r.hmset(get_noti_hkey(noti_id), {NOTI_CREATOR: creator, NOTI_TYPE: ntype, NOTI_TIME: ntime, NOTI_READ: read})
        self.r.lpush(get_user_notis_list(uid), noti_id)
        return noti_id

    def get_unread_notis(self, uid):
        notis = self.r.lrange(get_user_notis_list(uid), 0, -1)
        return [self.get_noti(nid) for nid in notis if self.r.hget(get_noti_hkey(nid), NOTI_READ) != "True"]

    def get_all_notis(self, uid):
        notis = self.r.lrange(get_user_notis_list(uid), 0, -1)
        return [self.get_noti(nid) for nid in notis]

    def get_noti_data(self, nid):
        hkeys = self.r.hkeys(get_noti_hkey(nid))
        noti = {NOTI_ID: nid}
        for k in hkeys:
            val = self.r.hget(get_noti_hkey(nid), k)
            if k == NOTI_TIME:
                noti[k] = common.format_datetime(float(val))
            else:
                noti[k] = unicode(val, "utf8")
            if k == NOTI_CREATOR:
                noti['creator_name'] = self.get_username(val)
        return noti

    def get_noti(self, nid):
        nname = get_noti_hkey(nid)
        ntype = self.r.hget(nname, NOTI_TYPE)
        nread = self.r.hget(nname, NOTI_READ)
        ntime = common.format_datetime(float(self.r.hget(nname, NOTI_TIME)))
        if ntype == FOLLOW_NOTI:
            msg = self.get_username(self.r.hget(nname, NOTI_CREATOR)) + " is following you."
            url = self.r.hget(get_noti_hkey(nid), NOTI_CREATOR)
        else:
            msg = self.get_username(self.r.hget(get_noti_hkey(nid), NOTI_CREATOR)) + " commented on you tweet."
            url = self.r.hget(get_noti_hkey(nid), NOTI_TWEET)
        return {NOTI_ID: nid, NOTI_TYPE: ntype, 'noti_msg': msg, 'noti_target': url, NOTI_TIME: ntime, NOTI_READ: nread}

    def set_read_noti(self, nid):
        if self.r.hget(get_noti_hkey(nid), NOTI_READ) != "True":
            self.r.hset(get_noti_hkey(nid), NOTI_READ, True)

    def set_read_notis(self, uid):
        for nid in self.r.lrange(get_user_notis_list(uid), 0, -1):
            self.set_read_noti(nid)
        return 0

    ############# S3 CONNECTION ##############

    def get_s3_filename(self, filename):
        if filename == self.config['DEFAULT_AVA']:
            return filename
        if self.config['TESTING']:
            filename = 'db' + str(self.config['REDIS_TEST_DB']) + '_' + filename
        else:
            filename = 'db' + str(self.config['REDIS_DB']) + '_' + filename
        return filename

    def s3_put(self, bucket, filename, content):
        self.conn.Object(bucket, self.get_s3_filename(filename)).put(Body=content)

    def s3_get(self, bucket, filename):
        img_data = self.conn.Object(bucket, self.get_s3_filename(filename)).get()
        return base64.encodestring(img_data['Body'].read())

    def s3_delete(self, bucket, filename):
        self.conn.Object(bucket, self.get_s3_filename(filename)).delete()

    ############# TWEETS MODEL ##############

    def set_new_tweet_id(self):
        if self.r.get(NEW_TWEET_ID) is None:
            self.r.set(NEW_TWEET_ID, 0)
        return self.r.incr(NEW_TWEET_ID)

    def get_new_tweet_id(self):
        if self.r.get(NEW_TWEET_ID) is None:
            return 1
        return self.r.get(NEW_TWEET_ID)

    def set_new_useralias(self):
        if self.r.get(NEW_USERALIAS) is None:
            self.r.set(NEW_USERALIAS, 1000)
        return "user" + str(self.r.incr(NEW_USERALIAS))

    def add_tweet(self, content, user, img=None):
        tweet_id = self.set_new_tweet_id()
        ttime = time.time()
        if img is not None:
            new_imgname = None
            org_imgname = secure_filename(img.filename)
            new_imgname = "tweet" + str(tweet_id) + '.' + org_imgname.rsplit('.', 1)[1]
            if self.config['LOCAL']:
                img.save(os.path.join(self.config['UPLOAD_FOLDER'], new_imgname))
            else:
                self.s3_put(self.config['BUCKET'], new_imgname, img)
            self.r.hmset(get_tweet_hkey(tweet_id), {TWEET_IMG: new_imgname})
        self.r.hmset(get_tweet_hkey(tweet_id), {TWEET_CONTENT: content, TWEET_TIME: ttime, TWEET_USER: user})
        self.r.lpush(TWEETS, tweet_id)
        tags = {tag.strip("#") for tag in content.split() if len(tag) > 0 and tag.startswith("#")}
        for tag in tags:
            if self.r.llen(get_hashtag_list(tag)) == 0:
                self.r.lpush(HASHTAGS, tag)
            self.r.lpush(get_hashtag_list(tag), tweet_id)
        return tweet_id

    def add_retweet(self, uid, tweet_id):
        pass

    def get_comment_ids(self, tweet_id):
        return self.r.lrange(get_tweet_comments_list(tweet_id), 0, -1)

    def get_comments(self, tweet_id):
        comments = []
        for cmt_id in self.get_comment_ids(tweet_id):
            cmt = {}
            hkeys = self.r.hkeys(get_comment_hkey(cmt_id))
            for k in hkeys:
                val = self.r.hget(get_comment_hkey(cmt_id), k)
                if k == COMMENT_TIME:
                    cmt[k] = common.format_datetime(float(val))
                else:
                    cmt[k] = unicode(val, "utf8")
                if k == COMMENT_USER:
                    cmt[COMMENT_USERNAME] = self.get_username(val)
                    cmt[COMMENT_USERALIAS] = self.get_useralias(val)
            comments.append(cmt)
        return comments

    def remove_tweet(self, tweet_id):
        content = self.r.hget(get_tweet_hkey(tweet_id), TWEET_CONTENT)
        #remove comment => remove the img => remove tweet => pop out the tweet list
        for cmt_id in self.get_comment_ids(tweet_id):
            self.remove_comment(tweet_id, cmt_id)
        tweet_img = self.r.hget(get_tweet_hkey(tweet_id), TWEET_IMG)
        if tweet_img:
            if self.config['LOCAL']:
                pass
            else:
                self.s3_delete(self.config['BUCKET'], tweet_img)
        self.r.delete(get_tweet_hkey(tweet_id))
        #Try to return the next tweet
        tweet_ids = self.r.lrange(TWEETS, 0, -1)
        next_tweet = 0
        if tweet_id in tweet_ids and tweet_ids.index(tweet_id) > 0:
            next_tweet = tweet_ids[tweet_ids.index(tweet_id) - 1]
        self.r.lrem(TWEETS, 0, tweet_id)

        tags = {tag.strip("#") for tag in content.split() if len(tag) > 0 and tag.startswith("#")}
        for tag in tags:
            self.r.lrem(get_hashtag_list(tag), 0, tweet_id)
            if self.r.llen(get_hashtag_list(tag)) == 0:
                self.r.lrem(HASHTAGS, 0, tag)

        return next_tweet

    def get_tweet(self, tweet_id):
        tname = get_tweet_hkey(tweet_id)
        hkeys = self.r.hkeys(tname)
        tweet = {'tweet_id': tweet_id}
        for k in hkeys:
            val = self.r.hget(tname, k)
            if k == TWEET_IMG and val:
                if self.config['LOCAL']:
                    tweet[k] = os.path.join('tmp', val)
                else:
                    tweet[k] = self.s3_get(self.config['BUCKET'], val)
            elif k == TWEET_TIME:
                tweet[k] = common.format_datetime(float(val))
            else:
                tweet[k] = unicode(val, "utf8")
            if k == TWEET_USER:
                tweet[USER_NAME] = self.get_username(val)
                tweet[USER_ALIAS] = self.get_useralias(val)
                tweet[USER_IMG] = self.get_userimg(val)
        tweet[COMMENTS] = self.get_comments(tweet_id)
        return tweet

    def get_tweets(self, lusers=None, offset=None, anchor=None, tag=None):
        twits = []
        if tag is None:
            tweet_ids = self.r.lrange(TWEETS, 0, -1)
        else:
            tweet_ids = self.r.lrange(get_hashtag_list(tag), 0, -1)
        if lusers is not None:
            tweet_ids = [tid for tid in tweet_ids if self.r.hget(get_tweet_hkey(tid), TWEET_USER) in lusers]
        more_tweet = False
        if anchor is not None:
            if anchor in tweet_ids:
                index = tweet_ids.index(anchor) + 1
                nopages = int(index / self.config['TWEETS_PER_PAGE']) + (index % self.config['TWEETS_PER_PAGE'] > 0)
                tweet_ids = tweet_ids[:(nopages * self.config['TWEETS_PER_PAGE'])]
            else:
                tweet_ids = tweet_ids[:self.config['TWEETS_PER_PAGE']]
        else:
            if offset is not None:
                offset_end = offset + self.config['TWEETS_PER_PAGE']
                more_tweet = offset_end < len(tweet_ids)
                tweet_ids = tweet_ids[offset:offset_end]
        for tid in tweet_ids:
            tweet = self.get_tweet(tid)
            twits.append(tweet)
        return (twits, more_tweet)

    def get_tweets_from_tag(self, tag):
        pass

    ############# USER MODEL ##############

    def get_user_from_tweet(self, tweet_id):
        return self.r.hget(get_tweet_hkey(tweet_id), TWEET_USER)

    def is_registered(self, email):
        return email in self.r.lrange(USERS, 0, -1)

    def add_user(self, email, name, password=None, img=None):
        joined = time.time()
        useralias = self.set_new_useralias()
        self.r.hmset(get_user_hkey(email), {USER_NAME: name, USER_PASS: password, USER_JOINED: joined, USER_ALIAS: useralias, USER_IMG: self.config['DEFAULT_AVA']})
        self.r.lpush(USERS, email)
        self.r.hset(HUSERALIAS, useralias, email)
        return email

    def add_user_avatar(self, uid, avatar):
        new_imgname = None
        org_imgname = secure_filename(avatar.filename)
        new_imgname = "avatar" + uid.replace('@', '__').replace('.', '_') + '.' + org_imgname.rsplit('.', 1)[1]
        if self.config['LOCAL']:
            avatar.save(os.path.join(self.config['UPLOAD_FOLDER'], new_imgname))
        else:
            old_img = self.r.hget(get_user_hkey(uid), USER_IMG)
            if old_img != self.config['DEFAULT_AVA']:
                self.s3_delete(self.config['BUCKET'], old_img)
            self.s3_put(self.config['BUCKET'], new_imgname, avatar)
        self.r.hmset(get_user_hkey(uid), {USER_IMG: new_imgname})

    def is_valid_user(self, email, password):
        stored_pass = self.r.hget(get_user_hkey(email), USER_PASS)
        return stored_pass == password

    def get_username(self, uid):
        return self.r.hget(get_user_hkey(uid), USER_NAME)

    def get_userid(self, useralias):
        return self.r.hget(HUSERALIAS, useralias)

    def get_useralias(self, uid):
        return self.r.hget(get_user_hkey(uid), USER_ALIAS)

    def check_alias(self, alias):
        return alias in self.r.hkeys(HUSERALIAS)

    def get_userimg(self, uid):
        user_img = self.r.hget(get_user_hkey(uid), USER_IMG)
        if user_img:
            if self.config['LOCAL']:
                return os.path.join('tmp', self.r.hget(get_user_hkey(uid), USER_IMG))
            else:
                return self.s3_get(self.config['BUCKET'], self.r.hget(get_user_hkey(uid), USER_IMG))
        else:
            return None

    def get_user_info(self, uid):
        user = {'user_id': uid}
        hkeys = self.r.hkeys(get_user_hkey(uid))
        for k in hkeys:
            val = self.r.hget(get_user_hkey(uid), k)
            if k == USER_JOINED:
                user[k] = common.format_datetime(float(val))
            elif k == USER_IMG:
                user[k] = self.get_userimg(uid)
            else:
                user[k] = unicode(val, "utf8")
        user['followers'] = self.get_followers(uid)
        user['followings'] = self.get_followings(uid)
        return user

    def get_user_basicinfo(self, uid):
        user = {}
        user[USER_NAME] = self.r.hget(get_user_hkey(uid), USER_NAME)
        user[USER_ALIAS] = self.r.hget(get_user_hkey(uid), USER_ALIAS)
        if self.get_userimg(uid):
            user[USER_IMG] = self.get_userimg(uid)
        return user

    def update_userinfo(self, uid, new_name=None, new_alias=None):
        if new_name:
            self.r.hmset(get_user_hkey(uid), {USER_NAME: new_name})
        if new_alias:
            alias = self.get_useralias(uid)
            self.r.hdel(HUSERALIAS, alias)
            self.r.hset(HUSERALIAS, new_alias, uid)
            self.r.hmset(get_user_hkey(uid), {USER_ALIAS: new_alias})

    ############# FOLLOWING ##############

    def add_follower(self, follower, followee):
        if follower == followee:
            return 0
        self.r.sadd(get_user_followers_hkey(followee), follower)
        self.r.sadd(get_user_followings_hkey(follower), followee)
        nid = self.add_noti(followee, follower, FOLLOW_NOTI)
        return nid

    def remove_follower(self, follower, followee):
        if follower == followee:
            return 0
        else:
            self.r.srem(get_user_followers_hkey(followee), follower)
            self.r.srem(get_user_followings_hkey(follower), followee)
            return 1

    def get_follower_ids(self, uid):
        return list(self.r.smembers(get_user_followers_hkey(uid)))

    def get_following_ids(self, uid):
        return list(self.r.smembers(get_user_followings_hkey(uid)))

    def get_followers(self, uid):
        return [self.get_user_basicinfo(f) for f in self.get_follower_ids(uid)]

    def get_followings(self, uid):
                return [self.get_user_basicinfo(f) for f in self.get_following_ids(uid)]

    def check_followed(self, follower, followee):
        return followee in self.get_following_ids(follower)

    ############# COMMENTS ##############

    def set_new_comment_id(self):
        if self.r.get(NEW_COMMENT_ID) is None:
            self.r.set(NEW_COMMENT_ID, 0)
        return self.r.incr(NEW_COMMENT_ID)

    def add_comment(self, tweet_id, userid, comment_content):
        cmt_id = self.set_new_comment_id()
        self.r.rpush(get_tweet_comments_list(tweet_id), cmt_id)
        self.r.hmset(get_comment_hkey(cmt_id), {COMMENT_USER: userid, COMMENT_CONTENT: comment_content, COMMENT_TIME: time.time()})
        nid = self.add_noti(self.get_user_from_tweet(tweet_id), userid, COMMENT_NOTI, tweet=tweet_id)
        return nid

    def remove_comment(self, tweet_id, cmt_id):
        self.r.delete(get_comment_hkey(cmt_id))
        self.r.lrem(get_tweet_comments_list(tweet_id), 0, cmt_id)
