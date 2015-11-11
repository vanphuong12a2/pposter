#!/usr/bin/env python

"""
This is the 1st assignment in the Global Internship Program at HDE. The target is a Twitter clone with basic functions.
Project name: pposter
Developer: Phuong Nguyen
Date: 10 Nov 2015
"""

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import os
from flask import Flask, url_for, render_template, request, redirect, flash, session
import redis
import time
from oauth2client.client import flow_from_clientsecrets
import httplib2
from apiclient.discovery import build
from werkzeug import secure_filename
from common import make_key, allowed_file

app = Flask(__name__)
app.config.from_object('config')
app.config.from_envvar('PPOSTER_SETTINGS', silent=True)

r = redis.StrictRedis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'], db=app.config['REDIS_DB'])


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


@app.route('/google_auth')
def google_auth():
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile', redirect_uri=url_for('auth_return', _external=True))
    auth_uri = flow.step1_get_authorize_url()
    return redirect(auth_uri)


@app.route('/auth_return', methods=['GET'])
def auth_return():
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile', redirect_uri=url_for('auth_return', _external=True))
    if 'code' in request.args:
        code = request.args.get('code')
        credentials = flow.step2_exchange(code)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('plus', 'v1', http=http)
        user_info = service.people().get(userId='me').execute()
        if user_info['id'] == app.config['GOOGLE_ID']:
            session['logged_in'] = True
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            return render_template('layout.html', error='Wrong user!')
    else:
        return render_template('layout.html', error='Authentication failed, please log in again!')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You were logged out!')
    return redirect(url_for('do_nothing'))


@app.route('/timeline')
def timeline():
    tweet_ids = r.lrange('tweet_ids', 0, -1)
    tweets = []
    for tid in tweet_ids:
        tname = make_key('tweet', tid)
        hkeys = r.hkeys(tname)
        tweet = {}
        for k in hkeys:
            tweet[k] = r.hmget(tname, k)[0]
        tweets.append(tweet)
    #tweets = [r.hvals(make_key('tweet', tid))[0] for tid in tweet_ids]
    return render_template('timeline.html', tweets=tweets)


@app.route('/add_tweet', methods=['POST'])
def add_tweet():
    if request.method == 'POST':
        #Add tweet id
        if r.get('new_tweet_id') is None:
            r.set('new_tweet_id', 0)
        tweet_id = r.incr('new_tweet_id')
        r.lpush('tweet_ids', tweet_id)

        #Get tweet
        #TODO: check content!!!
        tweet_content = request.form['tweet']
        tweet_img = None
        tweet_file = request.files['img']

        #TODO: return a warning for user in case the file is illegal
        if tweet_file and allowed_file(tweet_file.filename, app.config['ALLOWED_EXTENSIONS']):
            #TODO: change to relative path
            tweet_img = os.path.join('tmp', secure_filename(tweet_file.filename))
            tweet_file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(tweet_file.filename)))

        #Add tweet
        r.hmset(make_key('tweet', tweet_id), {'tweet_content': tweet_content, 'tweet_img': tweet_img, 'tweet_time': time.time()})
        return redirect(url_for('timeline'))

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
