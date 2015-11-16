#!/usr/bin/env python

"""
Test modules
"""

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import pposter
import unittest
import tempfile

assert pposter
assert tempfile


class PposterTestCase(unittest.TestCase):
    def setUp(self):
        self.app = pposter.app.test_client()

    def tearDown(self):
        pass

    def login(self, username, password):
        return self.app.post('/login', data=dict(
            username=username,
            password=password), follow_redirects=True)

    def logout(self):
        return self.app.get('/logout', follow_redirects=True)

    def register(self):
        pass

    def login_with_google(self):
        pass

    def add_tweet(self):
        return self.app.post('/add_tweet', data=dict(tweet=tweet_content), follow_redirects=True)

    def follow(self):
        pass

    def unfollow(self):
        pass

    def update_avatar(self):
        pass

    def update_info(self):
        pass

    def assert_flashes(self, expected_message, expected_category='message'):
        with self.app.session_transaction() as session:
            try:
                category, message = session['_flashes'][-1]
            except KeyError:
                raise AssertionError('nothing flashed')
            assert expected_message in message
            assert expected_category == category

    def test_login_logout(self):
        rv = self.login(pposter.app.config['USERNAME'], pposter.app.config['PASSWORD'])
        assert 'log out' in rv.data
        self.assert_flashes('You were logged in')
        rv = self.logout()
        self.assert_flashes('out')
        rv = self.login('fakeuser', 'pass')
        assert 'Wrong user' in rv.data
        rv = self.login('user', 'fakepass')
        assert 'Wrong user' in rv.data

    def test_session(self):
        rv = self.app.get('/')
        with self.app.session_transaction() as session:
            if 'logged_in' in session and session['logged_in']:
                assert 'log out' in rv.data
            else:
                assert 'log in' in rv.data

    def test_timeline(self):
        rv = self.login(pposter.app.config['USERNAME'], pposter.app.config['PASSWORD'])
        assert "What\'s on your mind" in rv.data

        rv = self.add_tweet('Test tweet')
        assert 'Test tweet' in rv.data

    def test_user_timeline(self):
        pass

    def test_public_timeline(self):
        pass

    def test_follow_unfollow(self):
        pass

    def test_update_info(self):
        pass

    def test_add_remove_tweet(self):
        pass

    def test_ajax(self):
        pass


if __name__ == '__main__':
    unittest.main()
