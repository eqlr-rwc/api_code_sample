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


# Visual separators so each API's request/response is easy to find in the logs.
LOG_BANNER = "=" * 80
LOG_RULE = "-" * 80


def log_request(method, url, data=None):
    """Log an easy-to-spot banner for an outgoing API request."""
    body = json.dumps(data, indent=2) if data is not None else "(no request body)"
    logging.info(
        f"\n{LOG_BANNER}\n"
        f"==> REQUEST  {method} {url}\n"
        f"{LOG_RULE}\n"
        f"{body}"
    )


def log_response(url, resp_json):
    """Log an easy-to-spot banner for an API response."""
    logging.info(
        f"\n{LOG_RULE}\n"
        f"<== RESPONSE {url}\n"
        f"{LOG_RULE}\n"
        f"{json.dumps(resp_json, indent=2)}\n"
        f"{LOG_BANNER}"
    )


def make_rest_get_call(signed_jwt, url):
    """Makes an authorized GET request to the endpoint"""
    log_request("GET", url)
    response = requests.get(url, headers=build_headers(signed_jwt))
    result = response.json()
    log_response(url, result)
    return result


def make_rest_post_call(signed_jwt, url, data):
    """Makes an authorized POST request to the endpoint"""
    log_request("POST", url, data)
    response = requests.post(url, headers=build_headers(signed_jwt), json=data)
    result = response.json()
    log_response(url, result)
    return result


# ---------------------------------------------------------------------------
# Polling a GCS signed URL for batch (bulk) results
#
# The bulk endpoints (e.g. /v2/person/bulkSearch and /v2/org/bulkSearch) process
# the batch asynchronously. Rather than returning the data inline, they respond
# with a Google Cloud Storage (GCS) "signed URL" that points to a single result
# file. That same file is updated in place as the batch runs:
#
#   * While processing, the file holds a progress document, e.g.:
#         {"status": "Processing", "progress": "0/5"}
#     where "progress" is "<completed>/<total>".
#
#   * Once the batch finishes, the SAME file is overwritten with the final JSON
#     results (which no longer carry a "Processing" status).
#
# So the client just re-downloads the file on an interval until the
# "Processing" status disappears, at which point the file holds the results.
# ---------------------------------------------------------------------------
POLL_INTERVAL_SECONDS = 5     # wait this long between polls
POLL_TIMEOUT_SECONDS = 600    # give up after this many seconds (10 minutes)


def poll_signed_url(signed_url, interval=POLL_INTERVAL_SECONDS, timeout=POLL_TIMEOUT_SECONDS):
    """Poll a GCS signed URL until the batch finishes, then return the results.

    Returns the parsed JSON results once the file is no longer in the
    "Processing" state. Raises TimeoutError if the batch does not finish within
    `timeout` seconds.

    NOTE: A signed URL is pre-authenticated -- the credentials are baked into
    the URL itself. Fetch it as a plain HTTP GET; do NOT attach the Equilar API
    key or the Google ID token (those are only for api.equilar.cloud calls).
    """
    deadline = time.time() + timeout
    while True:
        response = requests.get(signed_url)  # no auth headers; the URL is signed
        response.raise_for_status()
        result = response.json()

        # While the batch is running the file looks like:
        #   {"status": "Processing", "progress": "3/5"}
        if isinstance(result, dict) and result.get("status") == "Processing":
            logging.info(f"Batch still processing: {result.get('progress')}")
            if time.time() >= deadline:
                raise TimeoutError(
                    f"Batch did not finish within {timeout} seconds "
                    f"(last progress: {result.get('progress')})."
                )
            time.sleep(interval)
            continue

        # No "Processing" status -> the file now holds the final results.
        logging.info("Batch complete; results are ready.")
        return result


def get_bulk_results(bulk_res, label="bulk"):
    """Retrieve the results of a bulk request.

    Bulk endpoints respond with a GCS signed URL (in the "signedURL" field)
    that points to the result file. This extracts that URL, polls it until the
    batch finishes, logs the results, and returns them -- or returns None if the
    response did not contain a signed URL.
    """
    signed_url = bulk_res.get("signedURL") if isinstance(bulk_res, dict) else None
    if not signed_url:
        logging.warning(f"No signed URL found in the {label} response; "
                        "update the key used to read it from the response.")
        return None

    results = poll_signed_url(signed_url)
    log_response(f"{label} (from signed URL)", results)
    return results


def main():
    """Walk through a typical Equilar API session end to end.

    The steps below mirror how a real integration would use these APIs:
    authenticate once, look up an organization, fetch related data, and submit
    bulk jobs whose results are retrieved from a signed URL.
    """

    # ---- Step 1: Authenticate -------------------------------------------
    # Obtain a Google ID token to authorize the API calls. get_valid_id_token()
    # reuses a cached token and only mints a new one when it is missing or near
    # expiry, so it is safe (and recommended) to call before each request.
    id_token = get_valid_id_token()

    # ---- Step 2: Match a single organization ----------------------------
    # POST /v2/org/search resolves an org from any combination of name, ticker,
    # and website(s). The response tells us whether it matched and, if so, the
    # matching organization(s).
    url = 'https://'+ HOST +'/v2/org/search'
    data = {"name":"Apple", "ticker":"AAPL", "websites":["apple.com"]}
    res = make_rest_post_call(signed_jwt=id_token, url=url, data=data)

    # Confirm we got a match and grab the organizationId for the next call.
    match = res['match']
    if match == 'MATCH':
        org_id = res['orgList'][0]['organizationId']
    else:
        raise Exception("Organization not found")

    # ---- Step 3: Fetch executives for the matched org -------------------
    # GET /v2/org/executives/{id} returns the org's executives. Use limit/offset
    # to page through results (here: the first 10).
    url = f"https://api.equilar.cloud/v2/org/executives/{org_id}?limit=10&offset=0"
    res = make_rest_get_call(signed_jwt=id_token, url=url)

    # ---- Step 4: Bulk person search (async) -----------------------------
    # POST /v2/person/bulkSearch resolves many people in one request. Bulk
    # endpoints run asynchronously: instead of returning data inline, the
    # response carries a GCS signed URL. get_bulk_results() then polls that file
    # until the batch finishes and returns the results.
    url = 'https://'+ HOST +'/v2/person/bulkSearch'
    data = {}
    data["payload"] = []
    data["payload"].append({"firstName":"Sundar","lastName":"Pichai", "organizationName":"Alphabet Inc."})
    data["payload"].append({"firstName":"Satya","lastName":"Nadella", "organizationName":"Microsoft"})
    data["payload"].append({"firstName":"Shantanu","lastName":"Narayen", "organizationName":"Adobe"})
    data["payload"].append({"firstName":"Elon","lastName":"Musk", "organizationName":"Tesla"})
    bulk_res = make_rest_post_call(signed_jwt=id_token, url=url, data=data)
    get_bulk_results(bulk_res, label="Bulk person search")

    # ---- Step 5: Bulk org search (async) --------------------------------
    # POST /v2/org/bulkSearch resolves many organizations in one request; each
    # payload entry can match on name, ticker, website(s), and/or LinkedIn URL.
    # Like Step 4, results are retrieved by polling the signed URL via
    # get_bulk_results().
    url = 'https://'+ HOST +'/v2/org/bulkSearch'
    data = {}
    data["payload"] = []
    data["payload"].append({"name":"Intapp"})
    data["payload"].append({"name": "Palantir", "ticker":"PLTR"})
    data["payload"].append({"websites":["ibm.com"]})
    data["payload"].append({"linkedInUrl":"https://www.linkedin.com/company/tredence"})
    data["payload"].append({"name": "Amgen", "websites":["amgen.com"]})
    bulk_res = make_rest_post_call(signed_jwt=id_token, url=url, data=data)
    get_bulk_results(bulk_res, label="Bulk org search")


if __name__ == '__main__':
    main()
