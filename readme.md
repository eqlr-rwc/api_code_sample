Sample client for Equilar API

main.py is a code snippet to connect to Equilar's APIs using Google Id Token authentication. It also connects to the Equilar org match API to get the corresponding org and get 10 executives for the org. Our APIs use API Key and Google Id Token authentication for all the APIs, so the API Key must be passed in query and Google Id Token must be supplied in the header. The JWT token expires in an hour, please renew the JWT token every hour for uninterrupted access.

api.equilar.cloud is the endpoint

Also, replace SERVICE_ACCOUNT_PRIVATE_FILE_PATH variable with the path to your service account private key file shared earlier.

These 3 items will be provided by Equilar:
1. SERVICE_ACCOUNT_EMAIL = "xxx@xxx.iam.gserviceaccount.com" #you can find it in the service_account.json
2. SERVICE_ACCOUNT_PRIVATE_FILE_PATH="./service_account.json"
3. KEY="AI..............Lg"

Python requirements: 3.7+
Includes requirements.txt dependency file

```
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt 
python3 main.py 
```