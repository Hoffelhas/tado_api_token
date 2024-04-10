import os
import time
import requests
import yaml

# Obtain initial token by using log-in information
# Client secret can be found at https://app.tado.com/env.js
def initialise():

    data = {
        'client_id': 'tado-web-app',
        'grant_type': 'password',
        'scope': 'home.user',
        'username': os.environ['MY_MAIL'],
        'password': os.environ['MY_PASS'],
        'client_secret': os.environ['MY_CLIENT'],
    }

    response = requests.post('https://auth.tado.com/oauth/token', data=data).json()
    access_token = response['access_token']
    refresh_token = response['refresh_token'] 
    
    return access_token, refresh_token

# Refresh the token, since it expires every 10 minutes
def refresh(refresh_token):

    data = {
        'grant_type': 'refresh_token',
        'refresh_token': '',
        'client_id': 'tado-web-app',
        'scope': 'home.user',
        'client_secret': os.environ['MY_CLIENT'],
    }
    data['refresh_token'] = refresh_token
    
    response = requests.post('https://auth.tado.com/oauth/token', data=data)
    response = response.json()
    access_token = response['access_token']
    refresh_token = response['refresh_token']   
    
    return access_token, refresh_token

# Update token in the docker homepage services.yaml to use in the custom API
def update_tado_key_in_yaml_service(access_token):
   with open("/homepage/services.yaml", "r") as f:
      data = yaml.safe_load(f)
      new_key = 'Bearer ' + access_token
      data[0]['Services'][2]['Tado']['widget']['headers']['Authorization'] = new_key
   # Writing a new yaml file with the modifications
   with open("services.yaml", "w") as f:
      yaml.dump(data, f)

access_token, refresh_token = initialise()

# Keep updating the token
while 1:
   access_token, refresh_token = refresh(refresh_token)
   update_tado_key_in_yaml_service(access_token)
   time.sleep(10*60)


    

