#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This is the 1st assignment in the Global Internship Program at HDE. The target is a Twitter clone with basic functions.
Project name: pposter
Developer: Phuong Nguyen
Date: 10 Nov 2015
"""

from flask import Flask, g, url_for, render_template, request, redirect, flash, session, abort
import redis
from oauth2client.client import flow_from_clientsecrets
import httplib2
from apiclient.discovery import build
import boto3
import json
from flask_jsglue import JSGlue
from common import allowed_file
from redis_model import RedisModel


jsglue = JSGlue()
app = Flask(__name__)
jsglue.init_app(app)
app.config.from_object('config')
app.config.from_envvar('PPOSTER_SETTINGS', silent=True)


r = redis.StrictRedis(host=app.config['REDIS_HOST'], port=app.config['REDIS_PORT'], db=app.config['REDIS_DB'])
if app.config['TEST']:
    conn = None
else:
    conn = boto3.resource('s3')
model = RedisModel(r, conn, app.config)


@app.before_request
def before_request():
    g.test = app.config['TEST']
    g.curr_user = None
    if 'user_id' in session:
        g.curr_user = {'name': model.get_username(session['user_id']), 'alias': model.get_useralias(session['user_id'])}


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    error = None
    if request.method == 'POST':
        if model.is_valid_user(request.form['email'], request.form['password']):
            session['user_id'] = request.form['email']
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            error = "Wrong user!"
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    error = None
    if request.method == 'POST':
        if not request.form['email'] or '@' not in request.form['email']:
            error = 'You have to enter an valid email'
        elif model.is_registered(request.form['email']):
            error = 'This email was registered'
        elif not request.form['name']:
            error = 'You have to enter your name'
        elif not request.form['password']:
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        else:
            model.add_user(request.form['email'], request.form['name'], request.form['password'])
            flash('You were successfully registered and can login now')
            return redirect(url_for('login'))
    return render_template('register.html', error=error)


@app.route('/google_auth')
def google_auth():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile email', redirect_uri=url_for('auth_return', _external=True))
    auth_uri = flow.step1_get_authorize_url()
    return redirect(auth_uri)


@app.route('/auth_return', methods=['GET'])
def auth_return():
    if g.curr_user is not None:
        return redirect(url_for('timeline'))
    flow = flow_from_clientsecrets(app.config['GCLIENT_SECRETS'], scope='profile', redirect_uri=url_for('auth_return', _external=True))
    if 'code' in request.args:
        code = request.args.get('code')
        credentials = flow.step2_exchange(code)
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = build('plus', 'v1', http=http)
        user_info = service.people().get(userId='me').execute()
        if user_info['id'] == app.config['GOOGLE_ID']:
            session['user_id'] = user_info['emails'][0]['value']  # Need to be checked
            model.add_user(session['user_id'], user_info['name']['givenName'])
            flash("You were logged in!")
            return redirect(url_for('timeline'))
        else:
            return render_template('layout.html', error='Wrong user!')
    else:
        return render_template('layout.html', error='Authentication failed, please log in again!')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You were logged out!')
    return redirect(url_for('timeline'))


@app.route('/', methods=['GET'])
def timeline():
    if g.curr_user is None:
        return render_template('login.html')
    lusers = model.get_following_ids(session['user_id']) + [session['user_id']]
    tweets, more_tweet = model.get_tweets(lusers=lusers, offset=0)
    return render_template('timeline.html', tweets=tweets, more_tweet=more_tweet)


@app.route('/timelinejson', methods=['GET'])
def timelinejson():
    if g.curr_user is None:
        return render_template('login.html')
    if 'offset' in request.args:
        lusers = model.get_following_ids(session['user_id']) + [session['uid']]
        offset = int(request.args['offset'])
        tweets, more_tweet = model.get_tweets(lusers=lusers, offset=offset)
        return json.dumps({'tweets': tweets, 'more_tweet': more_tweet})
    else:
        abort(404)


@app.route('/<useralias>')
def user_timeline(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(useralias)
    if model.is_registered(uid):
        tweets, more_tweet = model.get_tweets(lusers=[uid], offset=0)
        followed = model.check_followed(session['user_id'], uid)
        timelineowner = {'name': model.get_username(uid), 'alias': useralias, 'followed': followed}
        if uid == session['user_id']:
            timelineowner['followers'] = model.get_followers(uid)
            timelineowner['followings'] = model.get_followings(uid)
        return render_template('timeline.html', tweets=tweets, timelineowner=timelineowner, more_tweet=more_tweet)
    else:
        flash("There is no user with that id")
        return redirect(url_for('timeline'))


@app.route('/<useralias>/timelinejson', methods=['GET'])
def user_timelinejson(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    if 'offset' in request.args:
        uid = model.get_userid(useralias)
        if model.registered(uid):
            offset = int(request.args['offset'])
            tweets, more_tweet = model.get_tweets(lusers=[uid], offset=offset)
            return json.dumps({'tweets': tweets, 'more_tweet': more_tweet})
        else:
            return redirect(url_for('user_timeline', useralias=g.curr_user[1]), more_tweet=True)
    else:
        abort(404)


@app.route('/<useralias>/follow')
def follow(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(useralias)
    model.add_follower(session['user_id'], uid)
    return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/<useralias>/unfollow')
def unfollow(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    uid = model.get_userid(useralias)
    model.remove_follower(session['user_id'], uid)
    return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/<useralias>/followers')
def followers(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    followers = model.get_followers(model.get_userid(useralias))
    return render_template("timeline.html", followers=followers)


@app.route('/<useralias>/followings')
def followings(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    followings = model.get_followings(model.get_userid(useralias))
    return render_template("timeline.html", followings=followings)


@app.route('/<useralias>/update_avatar', methods=['POST'])
def update_avatar(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    else:
        if request.method == 'POST':
            new_avatar = request.files['avatar']
            model.add_user_avatar(session['user_id'], new_avatar)
            return redirect(url_for('user_timeline', useralias=useralias))
        else:
            abort(404)


@app.route('/<useralias>/update_info', methods=['POST'])
def update_info(useralias):
    if g.curr_user is None:
        return render_template('login.html')
    else:
        if request.method == 'POST':
            new_name = request.form['name']
            new_alias = request.form['alias']
            if model.check_alias(new_alias):
                model.update_user(session['user_id'], new_name, new_alias)
                return redirect(url_for('user_timeline', useralias=useralias))
            else:
                return 'alias was used'
        else:
            abort(404)


@app.route('/public')
def public_timeline():
    tweets, more_tweet = model.get_tweets(offset=0)
    return render_template('timeline.html', tweets=tweets, more_tweet=more_tweet)


@app.route('/public/timelinejson', methods=['GET'])
def public_timelinejson():
    if 'offset' in request.args:
        offset = int(request.args['offset'])
        tweets, more_tweet = model.get_tweets(offset=offset)
        return json.dumps({'tweets': tweets, 'more_tweet': more_tweet})
    else:
        abort(404)


@app.route('/add_tweet', methods=['POST'])
@app.route('/<useralias>/add_tweet', methods=['POST'])
def add_tweet(useralias=None):
    if g.curr_user is None:
        return render_template('login.html')
    if useralias is not None and useralias != g.curr_user['alias']:
        return "Illegal post"
    if request.method == 'POST':
        tweet_content = request.form['tweet']
        if len(tweet_content) not in range(app.config['TWEET_MIN_LEN'], app.config['TWEET_MAX_LEN'] + 1):
            return render_template("timeline.html", error="Tweet length error!")
        tweet_file = request.files['img']
        if tweet_file and not allowed_file(tweet_file.filename, app.config['ALLOWED_EXTENSIONS']):
            return render_template("timeline.html", error="File ext not supported!")
        if tweet_file:
            model.add_tweet(tweet_content, session['user_id'], tweet_file)
        else:
            model.add_tweet(tweet_content, session['user_id'])
        if useralias is None:
            return redirect(url_for('timeline'))
        else:
            return redirect(url_for('user_timeline', useralias=useralias))


@app.route('/remove_tweet', methods=['GET'])
@app.route('/<useralias>/remove_tweet')
def remove_tweet(useralias=None):
    if 'tweet_id' not in request.args:
        abort(404)
    tweet_id = request.args['tweet_id']
    model.remove_tweet(tweet_id)
    if useralias is not None:
        return redirect(url_for('user_timeline', useralias=useralias))
    return redirect(url_for('timeline'))

if __name__ == '__main__':
    if app.config['TEST']:
        app.run(debug=app.config['DEBUG'])
    else:
        app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])
