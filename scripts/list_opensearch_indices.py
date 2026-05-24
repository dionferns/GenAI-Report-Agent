"""List all indices in OpenSearch collection."""

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

print(f"📍 Listing indices in collection: {COLLECTION_ENDPOINT}")

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
    indices = client.indices.get_alias(index="*")
    if indices:
        print("📋 Indices found:")
        for index_name in indices:
            stats = client.indices.stats(index=index_name)
            count = stats["indices"][index_name]["total"]["docs"]["count"]
            print(f"  - {index_name}: {count} documents")
    else:
        print("❌ No indices found")
except Exception as e:
    print(f"❌ Error listing indices: {e}")
    sys.exit(1)
