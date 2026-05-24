"""Delete all documents from OpenSearch index."""

import boto3
import sys
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from dotenv import load_dotenv
import os

load_dotenv()
COLLECTION_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT")

if not COLLECTION_ENDPOINT:
    print("❌ OPENSEARCH_ENDPOINT not found in .env")
    sys.exit(1)

INDEX_NAME = "articles_uk_economy"

print(f"📍 Cleaning index '{INDEX_NAME}' in collection: {COLLECTION_ENDPOINT}")
print("⚠️  Run with: AWS_PROFILE=genai python scripts/clean_opensearch.py")

credentials = boto3.Session().get_credentials()
if not credentials:
    print("❌ No AWS credentials found. Make sure AWS_PROFILE=genai is set")
    sys.exit(1)

awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    "eu-west-2",
    "aoss",
    session_token=credentials.token,
)

client = OpenSearch(
    hosts=[{"host": COLLECTION_ENDPOINT.replace("https://", ""), "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=30,
)

try:
    # Delete all documents
    response = client.delete_by_query(
        index=INDEX_NAME,
        body={"query": {"match_all": {}}},
    )

    print(f"✅ Deleted {response['deleted']} documents")

except Exception as e:
    print(f"❌ Error cleaning index: {e}")
    sys.exit(1)
