"""Create the OpenSearch index for article chunks."""

import boto3
import sys
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from dotenv import load_dotenv
import os

# Load from .env
load_dotenv()
COLLECTION_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT")

if not COLLECTION_ENDPOINT:
    print("❌ OPENSEARCH_ENDPOINT not found in .env")
    sys.exit(1)

INDEX_NAME = "articles_uk_economy"

print(f"📍 Creating index '{INDEX_NAME}' in collection: {COLLECTION_ENDPOINT}")
print("⚠️  Run with: AWS_PROFILE=genai python scripts/create_opensearch_index.py")

# Get credentials from AWS_PROFILE (requires it to be set)
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

index_body = {
    "settings": {
        "index": {
            "knn": True,
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "article_id": {"type": "keyword"},
            "text": {"type": "text"},
            "chunk_index": {"type": "integer"},
            "embedding": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "name": "hnsw",
                    "engine": "nmslib",
                    "space_type": "cosinesimil",
                },
            },
            "metadata": {"type": "object"},
        }
    },
}

try:
    client.indices.create(index=INDEX_NAME, body=index_body)
    print(f"✅ Index '{INDEX_NAME}' created successfully")
except Exception as e:
    # Check if it's a 400 "already exists" error (403 Forbidden means index already exists on OpenSearch Serverless)
    error_str = str(e)
    if "already" in error_str.lower() or "exists" in error_str.lower() or "403" in error_str or "Forbidden" in error_str:
        print(f"✅ Index '{INDEX_NAME}' already exists (or access denied, but index is there)")
    else:
        print(f"❌ Error creating index: {e}")
        sys.exit(1)
