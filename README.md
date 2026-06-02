# Equilar API Sample Client

`main.py` is a sample client showing how to authenticate against and call the
Equilar API. Equilar's APIs are fronted by a Google Cloud Endpoint and require
two credentials on every request: an **API key** and a **Google ID token**.

## What this sample demonstrates

The full authentication flow:

1. Sign a JWT with the service account's private key (`generate_jwt`).
2. Exchange that JWT for a short-lived Google ID token (`get_id_token`).
3. Reuse the ID token across requests until it nears expiry, only minting a new
   one when needed (`get_valid_id_token`).
4. Make authenticated GET/POST calls with the shared headers
   (`make_rest_get_call` / `make_rest_post_call`).
5. For bulk endpoints, poll the returned GCS signed URL until the batch
   finishes and the results are ready (`poll_signed_url`). See
   [Bulk endpoints and result polling](#bulk-endpoints-and-result-polling).

`main()` then exercises a few representative Equilar endpoints:

| Endpoint | Purpose |
| --- | --- |
| `POST /v2/org/search` | Match an organization by name, ticker, or website |
| `GET /v2/org/executives/{id}` | List executives for the matched organization |
| `POST /v2/person/bulkSearch` | Resolve several people in one call |
| `POST /v2/org/bulkSearch` | Resolve several organizations in one call |

## Authentication

All Equilar APIs use both an **API Key** and a **Google ID token**:

- The **API Key** is passed as a query parameter.
- The **Google ID token** is passed in the request header.

> **Note:** The token expires after one hour. Renew it every hour for
> uninterrupted access.

### Reuse the token — don't regenerate it per request

The Google ID token is valid for **one hour**. Generate it **once and reuse it**
for every API call; only mint a new token when the current one is missing or
about to expire. Generating a fresh JWT/token before every request is
unnecessary and adds latency.

`main.py` demonstrates this with `get_valid_id_token()`, which caches the token
along with its expiry time and returns the cached token until it is within a
short refresh buffer of expiring (5 minutes, by default), at which point it
transparently generates a new one. Call it wherever you need a token — it does
the right thing automatically.

## Bulk endpoints and result polling

The bulk endpoints (`/v2/person/bulkSearch` and `/v2/org/bulkSearch`) process
the batch **asynchronously**. Instead of returning the data inline, they
respond with a **Google Cloud Storage (GCS) signed URL** that points to a single
result file. That same file is updated in place as the batch runs:

- **While processing**, the file holds a progress document:

  ```json
  {
    "status": "Processing",
    "progress": "0/5"
  }
  ```

  where `progress` is `"<completed>/<total>"`.

- **When finished**, the *same* file is overwritten with the final JSON
  results (which no longer carry a `"Processing"` status).

So after you receive the signed URL, **poll it**: re-download the file on an
interval until the `"Processing"` status disappears — at that point the file
contains your results. `main.py` demonstrates this with `poll_signed_url()`.

> **Note:** A signed URL is pre-authenticated — the credentials are encoded in
> the URL itself. Fetch it with a plain HTTP `GET`; do **not** attach the
> Equilar API key or the Google ID token (those are only for
> `api.equilar.cloud` requests).

## Endpoint

```
api.equilar.cloud
```

## Configuration

Copy `.env.example` to `.env` and set the values provided by Equilar:

| Variable | Description |
| --- | --- |
| `SERVICE_ACCOUNT_PRIVATE_FILE_PATH` | Path to your service account private key file, e.g. `./service_account.json` |
| `KEY` | Your API key, e.g. `AI..............Lg` |

The service account email is read automatically from the `client_email` field
of the service account JSON file, so it does not need to be configured.

## Requirements

- **Python 3.10 or newer** (required by the pinned dependency versions)
- Dependencies listed in `requirements.txt`

The expected Python version is enforced in two places so you find out early:
`start.sh` checks it before creating the virtual environment, and `main.py`
checks it on startup. A `.python-version` file is also included for
[pyenv](https://github.com/pyenv/pyenv) users.

## Usage

Run the startup script. It creates the virtual environment (if it doesn't
already exist), installs dependencies, and runs the sample client:

```bash
./start.sh
```

Or do it manually:

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
python3 main.py
```

## License

Licensed under the Apache License, Version 2.0 (the "License"); you may not use
this file except in compliance with the License. You may obtain a copy of the
License at:

```
http://www.apache.org/licenses/LICENSE-2.0
```

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
