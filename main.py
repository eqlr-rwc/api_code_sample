#
# Licensed under the Apache License, Version 2.0(the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Example of calling a Google Cloud Endpoint API from Google App Engine
Default Service Account using Google ID token."""

import http.client as httplib
import json
import time
import urllib
import google.auth.crypt
import google.auth.jwt
import requests
import logging

logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)s [%(filename)s:%(lineno)d] %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', level=logging.INFO)

### Please replace the below variables with approriate values shared by Equilar
#Dev environment
#SERVICE_ACCOUNT_EMAIL = "xxx@*.iam.gserviceaccount.com"
#HOST = "api.equilar.cloud"
#SERVICE_ACCOUNT_PRIVATE_FILE_PATH="./service_account.json"
#KEY="A****************8Y"

#Production environment
SERVICE_ACCOUNT_EMAIL = "xxx@equilar-xxx.iam.gserviceaccount.com"
HOST = "api.equilar.cloud"
SERVICE_ACCOUNT_PRIVATE_FILE_PATH="./service_account.json"
KEY="AI..."

TARGET_AUD = SERVICE_ACCOUNT_EMAIL

#Method to generate JWT signed with the private key of service account
def generate_jwt(sa_keyfile, expiry_length=3600):

    """Generates a signed JSON Web Token using a Google API Service Account."""

    now = int(time.time())

    # build payload
    payload = {
        'iat': now,
        # expires after 'expiry_length' seconds.
        "exp": now + expiry_length,
        # iss must match 'issuer' in the security configuration in your
        # swagger spec (e.g. service account email). It can be any string.
        'iss': SERVICE_ACCOUNT_EMAIL,
        # aud must be either your Endpoints service name, or match the value
        # specified as the 'x-google-audience' in the OpenAPI document.
        'aud':  'https://www.googleapis.com/oauth2/v4/token',

        "target_audience": TARGET_AUD,
        # sub and email should match the service account's email address
        'sub': SERVICE_ACCOUNT_EMAIL,
        'email': SERVICE_ACCOUNT_EMAIL
    }

    # sign with keyfile
    signer = google.auth.crypt.RSASigner.from_service_account_file(sa_keyfile)
    jwt = google.auth.jwt.encode(signer, payload)
    return jwt

#Method to generate Google token using the signed JWT
def get_id_token(signed_jwt):
    """Request a Google ID token using a JWT."""
    params = urllib.parse.urlencode({
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': signed_jwt})
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    conn = httplib.HTTPSConnection("www.googleapis.com")
    conn.request("POST", "/oauth2/v4/token", params, headers)
    res = json.loads(conn.getresponse().read())
    conn.close()
    logging.info(res['id_token'])
    return res['id_token']

def make_rest_get_call(signed_jwt, url):
    """Makes an authorized request to the endpoint"""
    headers = {
        'Authorization': 'Bearer {}'.format(signed_jwt),
        'content-type': 'application/json',
        'x-api-key': KEY,
        'Referer': 'https://api.equilar.com',
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.get(url, headers=headers)
    logging.info(f"get response: {response.text}")
    json_resp = json.dumps(response.json(), indent=2)
    logging.info(f"output:\n{json_resp}")
    return response.json()

def make_rest_post_call(signed_jwt, url, data):
    logging.info(f"{url}:\ninput:\n{data}")
    """Makes an authorized request to the endpoint"""
    headers = {
        'Authorization': 'Bearer {}'.format(signed_jwt),
        'content-type': 'application/json',
        'x-api-key': KEY,
        'Referer': 'https://api.equilar.com',
        'User-Agent': 'Mozilla/5.0'
    }
    response = requests.post(url, headers=headers, json=data)
    json_resp = json.dumps(response.json(), indent=2)
    logging.info(f"output:\n{json_resp}")
    return response.json()
    #response.raise_for_status()


def main():
    url = 'https://'+ HOST +'/v2/org/search'
    #We need not generate JWT every time as it is valid for 1 hour
    signed_jwt = generate_jwt(sa_keyfile=SERVICE_ACCOUNT_PRIVATE_FILE_PATH)
    id_token = get_id_token(signed_jwt)
    
    data = {"name":"Apple", "ticker":"AAPL", "websites":["apple.com"]}
    res = make_rest_post_call(signed_jwt=id_token, url=url, data=data)

    match = res['match']
    if match == 'MATCH':
        org_id = res['orgList'][0]['organizationId']
    else:
        raise Exception("Organization not found")

    url = f"https://api.equilar.cloud/v2/org/executives/{org_id}?limit=10&offset=0"
    
    res = make_rest_get_call(signed_jwt=id_token, url=url)

    '''

    url = 'https://'+ HOST +'/v2/person/bulkSearch'
    data = {}
    data["payload"] = []
    data["payload"].append({"firstName":"Sundar","lastName":"Pichai", "organizationName":"Alphabet Inc."})
    data["payload"].append({"firstName":"Satya","lastName":"Nadella", "organizationName":"Microsoft"})
    data["payload"].append({"firstName":"Shantanu","lastName":"Narayen", "organizationName":"Adobe"})
    #make_rest_post_call(signed_jwt=id_token, url=url, data=data)


    url = 'https://'+ HOST +'/v2/org/bulkSearch'
    data = {}
    data["payload"] = []
    data["payload"].append({"name":"Intapp"})
    data["payload"].append({"name": "Coinbase", "ticker":"COIN"})
    data["payload"].append({"websites":["ibm.com"]})
    data["payload"].append({"linkedInUrl":"https://www.linkedin.com/company/tredence"})
    data["payload"].append({"name": "Amgen", "websites":["amgen.com"]})
    #make_rest_post_call(signed_jwt=id_token, url=url, data=data)

    '''


if __name__ == '__main__':
    main()
