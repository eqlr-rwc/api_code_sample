"""Sample client demonstrating how to authenticate against and call the
Equilar API.

Equilar's APIs are fronted by a Google Cloud Endpoint and require two
credentials on every request: an API key (sent as the `x-api-key` header) and a
Google ID token (sent as a Bearer token). This script shows the full flow:

  1. Sign a JWT with the service account's private key (`generate_jwt`).
  2. Exchange that JWT for a short-lived Google ID token (`get_id_token`).
  3. Reuse the ID token across requests until it nears expiry, only minting a
     new one when needed (`get_valid_id_token`).
  4. Make authenticated GET/POST calls with the shared headers
     (`make_rest_get_call` / `make_rest_post_call`).

The `main()` function exercises a few representative Equilar endpoints:

  - POST /v2/org/search           - match an organization by name/ticker/website
  - GET  /v2/org/executives/{id}  - list executives for the matched org
  - POST /v2/person/bulkSearch    - resolve several people in one call
  - POST /v2/org/bulkSearch       - resolve several organizations in one call

Configuration (API key, service account file path, optional host) is read from
a `.env` file; the service account email is derived from the JSON key file. See
README.md for setup and the License.
"""

import http.client as httplib
import json
import os
import sys
import time
import urllib

# This sample requires Python 3.10+ (matching the pinned dependency versions).
MIN_PYTHON = (3, 10)
if sys.version_info < MIN_PYTHON:
    sys.exit(
        f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required, "
        f"but you are running {sys.version.split()[0]}."
    )

import google.auth.crypt
import google.auth.jwt
import requests
import logging
from dotenv import load_dotenv

logging.basicConfig(format='%(asctime)s,%(msecs)d %(levelname)s [%(filename)s:%(lineno)d] %(message)s', datefmt='%Y-%m-%d:%H:%M:%S', level=logging.INFO)

### Configuration is loaded from a .env file (see .env.example).
### Replace the values there with the credentials shared by Equilar.
load_dotenv()

HOST = os.getenv("HOST", "api.equilar.cloud")
SERVICE_ACCOUNT_PRIVATE_FILE_PATH = os.getenv("SERVICE_ACCOUNT_PRIVATE_FILE_PATH", "./service_account.json")
KEY = os.getenv("KEY")

# The service account email is read from the "client_email" field of the
# service account JSON file, so it does not need to be configured separately.
with open(SERVICE_ACCOUNT_PRIVATE_FILE_PATH) as sa_file:
    SERVICE_ACCOUNT_EMAIL = json.load(sa_file)["client_email"]

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


# ---------------------------------------------------------------------------
# Token reuse
#
# The Google ID token returned above is valid for one hour. You should REUSE
# the same token for every API call and only mint a new one once the current
# token is expired (or about to expire). Do NOT call generate_jwt() /
# get_id_token() before every request -- that is unnecessary and slower.
#
# The helper below shows one simple way to do this: cache the token together
# with its expiry time and hand back the cached token until it is close to
# expiring, refreshing a few minutes early as a safety margin.
# ---------------------------------------------------------------------------
TOKEN_EXPIRY_SECONDS = 3600          # tokens are valid for one hour
TOKEN_REFRESH_BUFFER_SECONDS = 300   # refresh 5 minutes early to be safe

_cached_id_token = None
_cached_id_token_expiry = 0  # epoch seconds at which the cached token expires


def get_valid_id_token():
    """Return a valid Google ID token, reusing the cached one until it nears
    expiry.

    A new JWT and ID token are generated only when nothing is cached yet or the
    cached token is within TOKEN_REFRESH_BUFFER_SECONDS of expiring.
    """
    global _cached_id_token, _cached_id_token_expiry

    now = int(time.time())
    if _cached_id_token and now < (_cached_id_token_expiry - TOKEN_REFRESH_BUFFER_SECONDS):
        logging.info("Reusing cached ID token (still valid).")
        return _cached_id_token

    logging.info("No valid ID token cached; generating a new one.")
    signed_jwt = generate_jwt(sa_keyfile=SERVICE_ACCOUNT_PRIVATE_FILE_PATH,
                              expiry_length=TOKEN_EXPIRY_SECONDS)
    _cached_id_token = get_id_token(signed_jwt)
    _cached_id_token_expiry = now + TOKEN_EXPIRY_SECONDS
    return _cached_id_token


def build_headers(signed_jwt):
    """Build the authorization headers shared by every API request."""
    return {
        'Authorization': 'Bearer {}'.format(signed_jwt),
        'content-type': 'application/json',
        'x-api-key': KEY,
        'Referer': 'https://api.equilar.com',
        'User-Agent': 'Mozilla/5.0'
    }


def make_rest_get_call(signed_jwt, url):
    """Makes an authorized GET request to the endpoint"""
    response = requests.get(url, headers=build_headers(signed_jwt))
    json_resp = json.dumps(response.json(), indent=2)
    logging.info(f"output:\n{json_resp}")
    return response.json()


def make_rest_post_call(signed_jwt, url, data):
    """Makes an authorized POST request to the endpoint"""
    logging.info(f"{url}:\ninput:\n{data}")
    response = requests.post(url, headers=build_headers(signed_jwt), json=data)
    json_resp = json.dumps(response.json(), indent=2)
    logging.info(f"output:\n{json_resp}")
    return response.json()


def main():
    url = 'https://'+ HOST +'/v2/org/search'
    # Reuse the token across every call below. get_valid_id_token() only
    # generates a new token when the cached one is missing or near expiry,
    # so it is safe (and recommended) to call before each request.
    id_token = get_valid_id_token()

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
    '''

    url = 'https://'+ HOST +'/v2/person/bulkSearch'
    data = {}
    data["payload"] = []
    data["payload"].append({"firstName":"Sundar","lastName":"Pichai", "organizationName":"Alphabet Inc."})
    data["payload"].append({"firstName":"Satya","lastName":"Nadella", "organizationName":"Microsoft"})
    data["payload"].append({"firstName":"Shantanu","lastName":"Narayen", "organizationName":"Adobe"})
    data["payload"].append({"firstName":"Elon","lastName":"Musk", "organizationName":"Tesla"})
    make_rest_post_call(signed_jwt=id_token, url=url, data=data)


    url = 'https://'+ HOST +'/v2/org/bulkSearch'
    data = {}
    data["payload"] = []
    data["payload"].append({"name":"Intapp"})
    data["payload"].append({"name": "Palantir", "ticker":"PLTR"})
    data["payload"].append({"websites":["ibm.com"]})
    data["payload"].append({"linkedInUrl":"https://www.linkedin.com/company/tredence"})
    data["payload"].append({"name": "Amgen", "websites":["amgen.com"]})
    make_rest_post_call(signed_jwt=id_token, url=url, data=data)

    '''
    '''


if __name__ == '__main__':
    main()
