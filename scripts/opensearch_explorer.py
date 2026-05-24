"""Simple OpenSearch explorer — connect and view index stats."""

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from reportagent.config import get_settings
import json
import argparse


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
    print(f"Has session token: {credentials.token is not None}")

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


def list_all_indexes(client):
    """List all indexes in the OpenSearch cluster."""
    try:
        print("Listing all indexes...\n")
        response = client.indices.get(index="*")

        if not response:
            print("No indexes found.")
            return []

        indexes = []
        for index_name in response.keys():
            try:
                # Get doc count for each index
                count_response = client.search(index=index_name, body={"size": 0, "query": {"match_all": {}}})
                doc_count = count_response["hits"]["total"]["value"]
                indexes.append({"name": index_name, "doc_count": doc_count})
            except Exception as e:
                print(f"  Error querying {index_name}: {e}")
                continue

        print(f"Found {len(indexes)} index(es):\n")
        for idx in indexes:
            print(f"  • {idx['name']}: {idx['doc_count']} documents")

        return indexes

    except Exception as e:
        print(f"❌ Error listing indexes: {e}")
        print(f"   Exception type: {type(e).__name__}")
        return []


def get_index_stats(client, index_name="articles_uk_economy"):
    """Get stats and sample data from the index."""

    try:
        print(f"Attempting to search index '{index_name}'...\n")

        # Try different search queries
        print("Trying match_all query...")
        response = client.search(index=index_name, body={"size": 0, "query": {"match_all": {}}})
        doc_count = response["hits"]["total"]["value"]
        print(f"   match_all result: {doc_count} documents")

        if doc_count == 0:
            print("\nTrying with no query (default)...")
            response = client.search(index=index_name, body={"size": 0})
            doc_count = response["hits"]["total"]["value"]
            print(f"   default result: {doc_count} documents")

        print(f"\n✅ Index '{index_name}' found!")
        print(f"   Total chunks: {doc_count}\n")

        # Get a sample document to see structure
        sample_response = client.search(
            index=index_name,
            body={"size": 1, "_source": True}
        )

        if sample_response["hits"]["hits"]:
            sample = sample_response["hits"]["hits"][0]["_source"]
            print("Sample chunk structure:")
            print(f"   Fields stored: {list(sample.keys())}")

            # Print details
            if "text" in sample:
                preview = sample["text"][:100] + "..." if len(sample["text"]) > 100 else sample["text"]
                print(f"\n   Text preview: {preview}")

            if "metadata" in sample:
                print(f"\n   Metadata: {json.dumps(sample['metadata'], indent=6)}")

            if "embedding" in sample:
                embedding_size = len(sample["embedding"]) if sample["embedding"] else 0
                print(f"\n   Embedding vector size: {embedding_size} dimensions")

            # Print other fields
            for key in ["article_id", "chunk_index"]:
                if key in sample:
                    print(f"   {key}: {sample[key]}")

        return {"index": index_name, "total_chunks": doc_count}

    except Exception as e:
        print(f"\n❌ Error searching index:")
        print(f"   Exception type: {type(e).__name__}")
        print(f"   Error message: {e}")
        if hasattr(e, 'info'):
            print(f"   Info: {e.info}")
        return {}


def main():
    """Connect and display stats."""
    parser = argparse.ArgumentParser(description="OpenSearch Explorer")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all indexes"
    )
    parser.add_argument(
        "--index",
        type=str,
        default="articles_uk_economy",
        help="Index name to inspect (default: articles_uk_economy)"
    )

    args = parser.parse_args()

    settings = get_settings()
    print("Connecting to OpenSearch...")
    print(f"  Endpoint: {settings.opensearch_endpoint}")
    print(f"  Region: {settings.aws_default_region}\n")

    try:
        client = connect_to_opensearch()
        print("✅ Connected successfully!\n")

        if args.list:
            list_all_indexes(client)
        else:
            print("Index Stats:")
            print("=" * 60)
            stats = get_index_stats(client, index_name=args.index)

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        raise


if __name__ == "__main__":
    main()