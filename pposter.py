#!/usr/bin/env python

"""
This is the 1st assignment in the Global Internship Program at HDE. The target is a Twitter clone with basic functions.
Project name: pposter
Developer: Phuong Nguyen
Date: 10 Nov 2015
"""

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

from flask import Flask, url_for, render_template, request, redirect, flash, session
import redis
import time

app = Flask(__name__)
app.config.from_object('config')
app.config.from_envvar('PPOSTER_SETTINGS', silent=True)

r = redis.StrictRedis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'], db=app.config['REDIS_DB'])
r.setnx('users', (app.config['USERNAME'], app.config['PASSWORD']))


def make_key(ktype, val):
    return ktype + ':' + str(val)


@app.route('/')
def do_nothing():
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for('timeline'))
    else:
        return render_template('layout.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if (app.config['USERNAME'], app.config['PASSWORD']) == (request.form['username'], request.form['password']):
            session['logged_in'] = True
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            error = "Wrong user!"
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out!')
    return redirect(url_for('do_nothing'))


@app.route('/timeline')
def timeline():
    tweet_ids = r.lrange('tweet_ids', 0, -1)
    tweets = [r.hvals(make_key('tweet', tid))[0] for tid in tweet_ids]
    return render_template('timeline.html', tweets=tweets)


@app.route('/add_tweet', methods=['POST'])
def add_tweet():
    if request.method == 'POST':
        #Add tweet id
        if r.get('new_tweet_id') is None:
            r.set('new_tweet_id', 0)
        tweet_id = r.incr('new_tweet_id')
        r.lpush('tweet_ids', tweet_id)

        #Add tweet
        r.hmset(make_key('tweet', tweet_id), {'tweet_content': request.form['tweet'], 'tweet_time': time.time()})
        return redirect(url_for('timeline'))

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
