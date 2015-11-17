#!/usr/bin/env python

"""
Test modules
"""

import pposter
import unittest
import tempfile
from redis_model import RedisModel
from StringIO import StringIO

assert pposter
assert tempfile


class PposterTestCase(unittest.TestCase):
    def setUp(self):
        self.app = pposter.app.test_client()
        self.config = pposter.app.config
        self.config['TEST'] = True
        pposter.model = RedisModel(self.config)

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

    def login_with_google(self):
        #TODO
        pass

    def add_tweet(self, tweet_content, tweet_img, useralias=None):
        if useralias:
            return self.app.post('/' + useralias + '/add_tweet', data=dict(tweet=tweet_content, img=tweet_img), follow_redirects=True)
        else:
            return self.app.post('/add_tweet', data=dict(tweet=tweet_content, img=tweet_img), follow_redirects=True)

    def follow(self, useralias):
        return self.app.get('/' + useralias + '/follow', follow_redirects=True)

    def unfollow(self, useralias):
        return self.app.get('/' + useralias + '/unfollow', follow_redirects=True)

    def update_avatar(self, useralias, avatar):
        return self.app.post('/' + useralias + '/update_avatar', data=dict(avatar=avatar), follow_redirects=True)

    def update_info(self, useralias, new_name, new_alias):
        return self.app.post('/' + useralias + '/update_info', data=dict(name=new_name, alias=new_alias), follow_redirects=True)

    def add_comment(self, tweet_id, uid, content):
        #TODO
        pass

    def assert_flashes(self, expected_message, expected_category='message'):
        with self.app.session_transaction() as session:
            try:
                category, message = session['_flashes'][-1]
            except KeyError:
                raise AssertionError('nothing flashed')
            assert expected_message in message
            assert expected_category == category

    def test_boto3(self):
        #TODO
        pass

    def test_login_logout(self):
        rv = self.success_login('test')
        assert 'log out' in rv.data
        self.assert_flashes('You were logged in')
        rv = self.logout()
        self.assert_flashes('out')
        rv = self.login('fakeuser', 'pass')
        assert 'Wrong user' in rv.data
        rv = self.login('test@gmail.com', 'fakepass')
        assert 'Wrong user' in rv.data
        #TODO: test log in with Google

    def test_session(self):
        rv = self.app.get('/')
        with self.app.session_transaction() as session:
            if 'logged_in' in session and session['logged_in']:
                assert 'log out' in rv.data
            else:
                assert 'log in' in rv.data
        #TODO: force session variable here
        #TODO: test invalid call with logged user

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

    def test_timeline(self):
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
        self.success_login('test')
        rv = self.app.get('/user1001')
        assert 'test' in rv.data
        assert "What\'s on your mind" in rv.data
        assert "There's no message so far." in rv.data
        assert "change avatar" in rv.data
        assert "updateinfo" in rv.data
        assert "follow</a>" not in rv.data

        rv = self.add_tweet('', None, 'user1001')
        assert 'Tweet length error' in rv.data
        rv = self.add_tweet('Test tweet', (StringIO('fake image'), 'image.png'), 'user1001')
        assert 'Test tweet' in rv.data
        assert '<div class="tweet-image">' in rv.data
        assert "There's no message so far." not in rv.data

        self.logout()
        self.success_login('user2')
        rv = self.app.get('/user1001')
        assert 'test' in rv.data
        assert "What\'s on your mind" not in rv.data
        assert "change avatar" not in rv.data

    def test_public_timeline(self):
        rv = self.app.get('/public')
        assert "There's no message so far." in rv.data

        self.success_login('test')
        rv = self.add_tweet('Test tweet', (StringIO('fake image'), 'image.png'), 'user1001')
        rv = self.app.get('/public')
        assert 'Test tweet' in rv.data

    def test_follow_unfollow(self):
        self.success_login('user1')
        rv = self.add_tweet('Test tweet', (StringIO('fake image'), 'image.png'), 'user1001')
        self.logout()
        self.success_login('user2')
        rv = self.app.get('/user1001/follow', follow_redirects=True)
        assert ">unfollow</a>" in rv.data
        rv = self.app.get('/user1001/unfollow', follow_redirects=True)
        assert ">follow</a>" in rv.data

    def test_update_info(self):
        self.success_login('user1')
        rv = self.update_info('user1001', 'phuong', 'user1001')
        rv = self.update_info('user1001', 'phuong', 'vanphuong')
        rv = self.update_info('user1002', 'phuong', 'user1001')

        rv = self.update_avatar('user1001', (StringIO('fake image'), 'image.png'))
        rv = self.update_avatar('user1002', (StringIO('fake image'), 'image.png'))
        assert rv

    def test_ajax(self):
        pass


if __name__ == '__main__':
    unittest.main()
