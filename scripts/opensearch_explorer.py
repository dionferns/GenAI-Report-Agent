"""Simple OpenSearch explorer — connect and view index stats."""

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from reportagent.config import get_settings
import json


def connect_to_opensearch():
    """Connect to OpenSearch Serverless using AWS credentials."""
    settings = get_settings()

    if not settings.opensearch_endpoint:
        raise ValueError("OPENSEARCH_ENDPOINT not configured in .env")

    # Get AWS credentials from ~/.aws/credentials [default] profile
    session = boto3.Session(
        profile_name="default",
        region_name=settings.aws_default_region
    )
    credentials = session.get_credentials().get_frozen_credentials()

    print(f"Using AWS credentials: {credentials.access_key[:10]}...")

    awsauth = AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        settings.aws_default_region,
        "aoss",
        session_token=credentials.token,
    )

    host = settings.opensearch_endpoint.replace("https://", "")

    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )

    return client


def get_index_stats(client):
    """Get stats for all indices."""
    # Try searching the known index directly
    index_name = "articles_uk_economy"

    try:
        print(f"Attempting to search index '{index_name}'...")
        response = client.search(index=index_name, body={"size": 0})

        doc_count = response["hits"]["total"]["value"]
        print(f"✅ Index '{index_name}' found!")
        print(f"   Document count: {doc_count}")
        return [{"index": index_name, "doc_count": doc_count}]

    except Exception as e:
        print(f"\n❌ Error searching index:")
        print(f"   Exception type: {type(e).__name__}")
        print(f"   Error message: {e}")
        if hasattr(e, 'info'):
            print(f"   Info: {e.info}")
        return []


def main():
    """Connect and display stats."""
    settings = get_settings()
    print("Connecting to OpenSearch...")
    print(f"  Endpoint: {settings.opensearch_endpoint}")
    print(f"  Region: {settings.aws_default_region}\n")

    try:
        client = connect_to_opensearch()
        print("✅ Connected successfully!\n")

        print("Index Stats:")
        print("-" * 60)

        indices = get_index_stats(client)

        if not indices:
            print("Could not retrieve index information.")
            return

        for idx in indices:
            print(f"Index: {idx['index']}")
            print(f"  Documents: {idx.get('doc_count', 'N/A')}")

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise


if __name__ == "__main__":
    main()