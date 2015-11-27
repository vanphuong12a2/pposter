# pposter
A mock Twitter project developed using Flask with unittest (coverage: 90%)

# Requirentment
- Redis
- Virtualenv
- Nginx verision 1.4 or up for deploying
 
# Preparation
- Clone the pposter project
        
- Create environment

        mkdir env
        virtualenv env
        source env/bin/activate
        pip install -r requirements.txt

# Configuation
- Config file is in `config/config.py`, turn on the flag for LOCAL to store img in local machine instead of S3 server. 

# Makefile
- Running on the builtin wsgi
        make run

- Cleaning up
        make clean

# Deploy on Nginx with uWsgi or gunicorn

uWsgi config: `pposter.ini`

gunicorn: 
        PATH=/path/to/vertual/env/bin
        cd /path/to/pposter
        gunicorn --worker-class eventlet pposter:app

nginx https config: (http listen on port 80 without ssl certificate)
```
server{
    listen               443;
    ssl                  on;
    ssl_certificate      path to certificate;
    ssl_certificate_key  path to key;
    server_name  localhost;

    location / {
        #for gunicorn
        proxy_pass http://127.0.0.1:8000;
        #for uwsgi which does not work for socketio currently
        #include uwsgi_params; 
        #uwsgi_pass unix:/tmp/pposter.sock;
        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
    location /socket.io {
        proxy_pass http://127.0.0.1:8000/socket.io;
        proxy_redirect off;
        proxy_buffering off;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
    }
}
```
