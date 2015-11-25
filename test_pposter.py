#!/usr/bin/env python


"""
Unittest module for pposter.py
Owner: Phuong Nguyen
"""

import unittest
from mock import patch
from StringIO import StringIO
from model.redis_model import RedisModel
import pposter


class PposterTestCase(unittest.TestCase):
    def setUp(self):
        self.app = pposter.app.test_client()
        self.config = pposter.app.config
        self.config['TESTING'] = True
        pposter.model = RedisModel(self.config)
        self.model = pposter.model

    def tearDown(self):
        #clear teh current database
        pposter.model.flush_db()

    def login(self, email, password):
        return self.app.post('/login', data=dict(
            email=email,
            password=password), follow_redirects=True)

    def success_login(self, name):
        self.register(name + '@gmail.com', name, 'aA1233@222', 'aA1233@222')
        rv = self.login(name + '@gmail.com', 'aA1233@222')
        return rv

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def register(self, email, name, password, password2):
        return self.app.post('/register', data=dict(
            email=email,
            name=name,
            password=password,
            password2=password2), follow_redirects=True)

    def add_tweet(self, tweet_content, tweet_img=None, useralias=None):
        if tweet_img is None:
            data = dict(tweet=tweet_content)
        else:
            data = dict(tweet=tweet_content, img=tweet_img)
        if useralias:
            return self.app.post('/' + useralias + '/add_tweet', data=data, follow_redirects=True)
        else:
            return self.app.post('/add_tweet', data=data, follow_redirects=True)

    def remove_tweet(self, tweet_id, useralias=None):
        if useralias:
            return self.app.get('/' + useralias + '/remove_tweet?tweet_id=' + str(tweet_id), follow_redirects=True)
        else:
            return self.app.get('/remove_tweet?tweet_id=' + str(tweet_id), follow_redirects=True)

    def update_avatar(self, useralias, avatar):
        return self.app.post('/' + useralias + '/update_avatar', data=dict(avatar=avatar), follow_redirects=True)

    def update_info(self, useralias, new_name, new_alias):
        return self.app.post('/' + useralias + '/update_info', data=dict(name=new_name, alias=new_alias), follow_redirects=True)

    def add_comment(self, tweet_id, content, useralias=None):
        if useralias:
            return self.app.post('/' + useralias + '/add_comment?tweet_id=' + str(tweet_id), data=dict(content=content), follow_redirects=True)
        else:
            return self.app.post('/add_comment?tweet_id=' + str(tweet_id), data=dict(content=content), follow_redirects=True)

    def assert_flashes(self, expected_message, expected_category='message'):
        with self.app.session_transaction() as session:
            try:
                category, message = session['_flashes'][-1]
            except KeyError:
                raise AssertionError('nothing flashed')
            assert expected_message in message
            assert expected_category == category

    def test_boto3(self):
        if self.config['LOCAL']:
            pass
        else:
            img = open('./static/tmp/default_ava.png', 'rb')
            self.model.s3_put(self.config['BUCKET'], 'demo.png', img)
            ret_img = self.model.s3_get(self.config['BUCKET'], 'demo.png')
            assert img == ret_img
            self.model.delete(self.config['BUCKET'], 'demo.png')
            ret_img2 = self.model.s3_get(self.config['BUCKET'], 'demo.png')
            assert ret_img2 is None
            img.close()

    def test_register(self):
        rv = self.register('not.a.valid.email', '', '', '')
        assert 'You have to enter an valid email' in rv.data
        # Success register
        rv = self.register('test@gmail.com', 'test', 'aA1233@222', 'aA1233@222')
        assert 'Login' in rv.data
        rv = self.register('test@gmail.com', 'test2', 'dggGG2232@ds', 'dggGG2232@ds')
        assert 'This email was registered' in rv.data
        rv = self.register('test2@gmail.com', '', '', '')
        assert 'You have to enter your name' in rv.data
        rv = self.register('test2@gmail.com', 'test', '', '')
        assert 'You have to enter a password' in rv.data
        rv = self.register('test2@gmail.com', 'test', '123', '124')
        assert 'The two passwords do not match' in rv.data
        rv = self.register('test2@gmail.com', 'test', '123', '123')
        assert 'The password is not strong enough' in rv.data

    def test_login_logout(self):
        rv = self.success_login('test')
        assert 'log out' in rv.data
        rv = self.app.get('/login', follow_redirects=True)
        assert 'log out' in rv.data
        rv = self.app.get('/register', follow_redirects=True)
        assert 'log out' in rv.data
        self.assert_flashes('You were logged in')
        rv = self.logout()
        self.assert_flashes('out')
        rv = self.login('fakeuser', 'pass')
        assert 'Wrong user' in rv.data
        rv = self.login('test@gmail.com', 'fakepass')
        assert 'Wrong user' in rv.data

    @patch('pposter.auth_return')
    def test_google_openid(self, appMock):
        #TODO: test log in with Google
        self.success_login('test')
        rv = self.app.get('/google_auth', follow_redirects=True)
        assert 'log out' in rv.data
        rv = self.app.get('/auth_return', follow_redirects=True)
        assert 'log out' in rv.data
        self.logout()

        rv = self.app.get('/google_auth')
        assert '[302 FOUND]' in str(rv)
        assert 'https://accounts.google.com/o/oauth2/auth' in rv.data
        assert 'response_type=code' in rv.data
        assert 'auth_return' in rv.data
        rv = self.app.get('/auth_return', follow_redirects=True)
        assert 'Authentication failed, please log in again!'

        rv = self.app.get('/auth_return?code=fakecode', follow_redirects=True)
        assert 'fakecode' in rv.data

    def test_session(self):
        rv = self.app.get('/')
        assert 'log in' in rv.data
        rv = self.success_login('test')
        with self.app.session_transaction() as session:
            assert session['user_id'] == 'test@gmail.com'
        assert 'log out' in rv.data
        self.logout()
        with self.app.session_transaction() as session:
            assert 'user_id' not in session
        self.success_login('test2')
        with self.app.session_transaction() as session:
            assert session['user_id'] == 'test2@gmail.com'

    def test_timeline(self):
        rv = self.app.get('/user1001')
        assert 'log in' in rv.data
        rv = self.success_login('test')
        assert "What\'s on your mind" in rv.data
        assert "There's no message so far." in rv.data
        rv = self.add_tweet('', None)
        assert 'Tweet length error' in rv.data
        rv = self.add_tweet('Test tweet', (StringIO('fake image'), 'image.png'))
        assert 'Test tweet' in rv.data
        assert '<div class="tweet-image">' in rv.data
        assert "There's no message so far." not in rv.data

    def test_user_timeline(self):
        rv = self.app.get('/user1001', follow_redirects=True)
        assert 'log in' in rv.data
        self.success_login('test')
        rv = self.app.get('/user1001', follow_redirects=True)
        assert 'test' in rv.data
        assert "What\'s on your mind" in rv.data
        assert "There's no message so far." in rv.data
        assert "change avatar" in rv.data
        assert "updateinfo" in rv.data
        assert "follow</a>" not in rv.data

        self.logout()
        self.success_login('user2')
        rv = self.app.get('/user1001', follow_redirects=True)
        assert 'test' in rv.data
        assert "What\'s on your mind" not in rv.data
        assert "change avatar" not in rv.data

        rv = self.app.get('/user1003', follow_redirects=True)
        self.assert_flashes('There is no user with that id')

    def test_public_timeline(self):
        rv = self.app.get('/public')
        assert "There's no message so far." in rv.data

        self.success_login('test')
        rv = self.add_tweet('Test tweet', (StringIO('fake image'), 'image.png'), 'user1001')
        rv = self.app.get('/public')
        assert 'Test tweet' in rv.data

    def test_add_remove_tweet(self):
        rv = self.add_tweet('', None, 'user1001')
        assert 'log in' in rv.data
        rv = self.remove_tweet(3)
        assert 'log in' in rv.data

        self.success_login('test')
        rv = self.app.get('/user1001')

        rv = self.add_tweet('', None, 'user1001')
        assert 'Tweet length error' in rv.data
        rv = self.add_tweet('Test tweet', (StringIO('fake image'), 'image.png'), 'user1002')
        self.assert_flashes('Illegal access')
        rv = self.add_tweet('Test tweet')
        assert 'Test tweet' in rv.data
        assert "There's no message so far." not in rv.data

        self.add_tweet('Test 2', (StringIO('fake image'), 'image.png'), 'user1001')

        #Check timelines
        rv = self.app.get('/')
        assert 'Test tweet' in rv.data
        rv = self.app.get('/public')
        assert 'Test tweet' in rv.data

        #Remove tweet
        rv = self.remove_tweet(3)
        self.assert_flashes('Illegal access')
        rv = self.remove_tweet(1)
        assert 'Test tweet' not in rv.data
        assert 'Test 2' in rv.data

        rv = self.remove_tweet(2, 'user1002')
        self.assert_flashes('Illegal access')
        rv = self.remove_tweet(2, 'user1001')
        assert 'Test 2' not in rv.data

        rv = self.app.get('/remove_tweet', follow_redirects=True)
        assert 'change avatar' in rv.data

        #Add tweet with valid file
        img = open('./static/tmp/default_ava.png', 'rb')
        rv = self.add_tweet('Tweet with img', img, 'user1001')
        img.close()
        assert 'Tweet with img' in rv.data
        assert '<div class="tweet-image">' in rv.data

        #Add tweet with invalid file
        img2 = open('./static/tmp/style.css', 'rb')
        rv = self.add_tweet('Tweet with img', img2, 'user1001')
        img2.close()
        assert 'File ext not supported!' in rv.data

    def test_follow_unfollow(self):
        rv = self.app.get('/user1001/follow', follow_redirects=True)
        assert 'log in' in rv.data
        rv = self.app.get('/user1001/unfollow', follow_redirects=True)
        assert 'log in' in rv.data
        self.success_login('user1')
        rv = self.add_tweet('Test tweet', (StringIO('fake image'), 'image.png'), 'user1001')
        rv = self.app.get('/user1001/follow', follow_redirects=True)
        #TODO
        rv = self.app.get('/user1001/unfollow', follow_redirects=True)
        #TODO
        self.logout()
        self.success_login('user2')
        rv = self.app.get('/user1001/follow', follow_redirects=True)
        assert ">unfollow</a>" in rv.data
        rv = self.app.get('/user1001/unfollow', follow_redirects=True)
        assert ">follow</a>" in rv.data

    def test_timeline_with_followings(self):
        #Login/add tweets + follow few ppl with tweets
        for i in range(3):
            self.success_login('user' + str(i))
            rv = self.add_tweet('Test tweet from @' + str(i + 1), (StringIO('fake image'), 'image.png'), 'user100' + str(i + 1))
            self.logout()
        self.success_login('test')
        rv = self.app.get('/user1001/follow', follow_redirects=True)
        rv = self.app.get('/user1002/follow', follow_redirects=True)
        #PART1: Home timeline
        rv = self.app.get('/')
        #print rv.data
        assert 'Test tweet from @1' in rv.data
        assert 'Test tweet from @2' in rv.data
        assert 'Test tweet from @3' not in rv.data

        rv = self.app.get('/public')
        assert 'Test tweet from @1' in rv.data
        assert 'Test tweet from @2' in rv.data
        assert 'Test tweet from @3' in rv.data

        rv = self.app.get('/user1004')
        assert 'Test tweet from @1' not in rv.data
        assert 'Test tweet from @2' not in rv.data
        assert 'Test tweet from @3' not in rv.data

        #PART2: User timeline
        rv = self.app.get('/user1001')
        assert 'Test tweet from @1' in rv.data
        assert 'Test tweet from @2' not in rv.data

        rv = self.app.get('/user1001/unfollow', follow_redirects=True)
        rv = self.app.get('/')
        assert 'Test tweet from @1' not in rv.data
        assert 'Test tweet from @2' in rv.data

    def test_update_info(self):
        rv = self.update_info('user1001', 'phuong', 'user1001')
        assert 'log in' in rv.data
        rv = self.update_avatar('user1001', (StringIO('fake image'), 'image.png'))
        assert 'log in' in rv.data
        self.success_login('user1')
        rv = self.update_info('user1001', 'phuong', 'user1001')
        assert 'phuong' in rv.data
        rv = self.update_info('user1001', 'phuong', 'vanphuong')
        assert 'vanphuong' in rv.data
        rv = self.update_info('user1002', 'phuong', 'user1001')
        self.assert_flashes('Illegal access')
        self.logout()

        self.success_login('user2')
        rv = self.update_info('user1001', 'phuong', 'user1001')
        self.assert_flashes('Illegal access')
        rv = self.update_info('user1002', 'phuong', 'vanphuong')
        assert "Alias was used" in rv.data

        rv = self.update_avatar('user1001', (StringIO('fake image'), 'image.png'))
        self.assert_flashes('Illegal access')

        img = open('./static/tmp/default_ava.png', 'rb')
        rv = self.update_avatar('user1002', (StringIO('fake image'), 'image.png'))
        rv = self.update_avatar('user1002', img)
        assert '[200 OK]' in str(rv)
        img.close()

        img2 = open('./static/tmp/test2M.png', 'rb')
        rv = self.update_avatar('user1002', img2)
        assert '[413 REQUEST ENTITY TOO LARGE]' in str(rv)
        img2.close()

    def test_ajax(self):
        #TODO: login and add a lot of tweet
        rv = self.app.get('/timelinejson', follow_redirects=True)
        assert 'log in' in rv.data
        self.success_login('user1')
        for i in range(self.config['TWEETS_PER_PAGE'] + 5):
            rv = self.add_tweet('Test tweet no ' + str(i + 1), (StringIO('fake image'), 'image.png'))
        rv = self.app.get('/timelinejson', follow_redirects=True)
        assert "[404 NOT FOUND]" in str(rv)
        rv = self.app.get('/timelinejson?offset=' + str(self.config['TWEETS_PER_PAGE']), follow_redirects=True)
        assert 'Test tweet no 4' in rv.data

        rv = self.app.get('/user1001/timelinejson', follow_redirects=True)
        assert "[404 NOT FOUND]" in str(rv)
        rv = self.app.get('/user1001/timelinejson?offset=' + str(self.config['TWEETS_PER_PAGE']), follow_redirects=True)
        assert 'Test tweet no 4' in rv.data

        rv = self.app.get('/public/timelinejson', follow_redirects=True)
        assert "[404 NOT FOUND]" in str(rv)
        rv = self.app.get('/public/timelinejson?offset=' + str(self.config['TWEETS_PER_PAGE']), follow_redirects=True)
        assert 'Test tweet no 4' in rv.data

    def test_add_comment(self):
        rv = self.add_comment(1, 'cmt content')
        assert 'log in' in rv.data
        self.success_login('user1')
        rv = self.add_tweet('Test tweet')
        rv = self.add_comment(1, '')
        assert 'Comment length error' in rv.data
        rv = self.add_comment(1, 'cmt content')
        assert 'cmt content' in rv.data
        rv = self.add_comment(2, 'nothing')
        assert 'nothing' not in rv.data
        rv = self.add_comment(1, 'cmt content @3', 'user1001')
        assert 'cmt content @3' in rv.data
        assert 'user1001' in rv.data
        rv = self.add_comment(1, 'cmt content @4', 'user1002')
        assert 'cmt content @4' not in rv.data
        rv = self.app.get('/public')
        assert 'cmt content' in rv.data
        rv = self.app.get('/user1001')
        assert 'cmt content' in rv.data
        rv = self.app.get('/')
        assert 'cmt content' in rv.data

        #remove tweet with comments
        for i in range(5):
            self.add_comment(1, 'cmt:' + str(i))
        rv = self.remove_tweet(1)
        assert 'cmt:' not in rv.data

    def test_anchor(self):
        self.success_login('user1')
        for i in range(self.config['TWEETS_PER_PAGE'] + 5):
            rv = self.add_tweet('Test tweet no ' + str(i + 1) + '!')
        rv = self.app.get('/')
        assert 'Test tweet no 1!' not in rv.data
        assert 'Test tweet no ' + str(self.config['TWEETS_PER_PAGE'] + 1) + '!' in rv.data

        rv = self.app.get('/user1001')
        assert 'Test tweet no 1!' not in rv.data
        assert 'Test tweet no ' + str(self.config['TWEETS_PER_PAGE'] + 1) + '!' in rv.data
        rv = self.app.get('/public')
        assert 'Test tweet no 1!' not in rv.data
        assert 'Test tweet no ' + str(self.config['TWEETS_PER_PAGE'] + 1) + '!' in rv.data

        rv = self.add_comment(2, 'cmt content')
        assert 'Test tweet no 2' in rv.data
        assert 'cmt content' in rv.data
        rv = self.remove_tweet(3)
        assert 'Test tweet no 4' in rv.data

if __name__ == '__main__':
    unittest.main()
