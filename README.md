# Equilar API Sample Client

`main.py` is a sample client that connects to Equilar's APIs using Google ID
token authentication. It calls the Equilar org match API to find a matching
organization and retrieves 10 executives for that organization.

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
