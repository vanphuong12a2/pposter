# pposter
A mock Twitter project developed using Flask

# Requirentment
- Redis
- Virtualenv

# Install
- Clone the pposter project
        
- Create environment

        mkdir env
        virtualenv env
        source env/bin/activate
        pip install -r requirements.txt


# Configuation
- Config file is in `config/config.py` 

# Run
        make run

# Deploy

uWsgi config: `pposter.ini`

nginx https config:
```
server{
        listen               443;
        ssl                  on;
        ssl_certificate      path to certificate;
        ssl_certificate_key  path to key;
        server_name  localhost;

        location / {
                include uwsgi_params;
                uwsgi_pass unix:/tmp/pposter.sock;
        } 
}
```
