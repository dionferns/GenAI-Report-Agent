"""Test script to insert and retrieve a chunk from OpenSearch."""

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from reportagent.config import get_settings
import json
import argparse
import time


def connect_to_opensearch():
    """Connect to OpenSearch Serverless using AWS credentials."""
    settings = get_settings()

    if not settings.opensearch_endpoint:
        raise ValueError("OPENSEARCH_ENDPOINT not configured in .env")

    session = boto3.Session(
        profile_name="default",
        region_name=settings.aws_default_region
    )
    credentials = session.get_credentials().get_frozen_credentials()

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


def delete_all_documents(client, index_name):
    """Delete all documents from an index using bulk API."""
    print(f"Deleting all documents from index '{index_name}'...\n")

    try:
        # First, retrieve all document IDs
        response = client.search(
            index=index_name,
            body={"query": {"match_all": {}}, "size": 1000}
        )

        docs = response["hits"]["hits"]
        if not docs:
            print("No documents to delete.\n")
            return 0

        # Build bulk delete actions
        actions = []
        for doc in docs:
            actions.append({"delete": {"_index": index_name, "_id": doc["_id"]}})

        # Execute bulk delete
        bulk_response = client.bulk(body=actions)

        # Check for errors
        if bulk_response.get("errors"):
            error_count = sum(1 for item in bulk_response["items"] if "error" in item.get("delete", {}))
            print(f"⚠️  Bulk delete had {error_count} errors")

        deleted_count = len(docs)
        print(f"Deleted {deleted_count} documents")

        # Wait for deletion to be reflected (OpenSearch Serverless has eventual consistency)
        print("Waiting 20 seconds for deletion to be reflected...")
        time.sleep(20)

        # Verify deletion
        verify_response = client.search(
            index=index_name,
            body={"query": {"match_all": {}}, "size": 1}
        )
        remaining = verify_response["hits"]["total"]["value"]
        print(f"✅ Remaining documents in index: {remaining}\n")

        return deleted_count

    except Exception as e:
        print(f"❌ Error deleting documents: {e}\n")
        import traceback
        traceback.print_exc()
        return 0


def main():
    """Test insert and retrieve."""
    parser = argparse.ArgumentParser(description="OpenSearch test script")
    parser.add_argument(
        "--delete-all",
        action="store_true",
        help="Delete all documents from the index"
    )
    parser.add_argument(
        "--list-chunks",
        action="store_true",
        help="Only show all chunks in the index (TEST 6 only)"
    )
    parser.add_argument(
        "--index",
        type=str,
        default="articles_uk_economy",
        help="Index name (default: articles_uk_economy)"
    )
    args = parser.parse_args()

    settings = get_settings()
    index_name = args.index

    print("Connecting to OpenSearch...")
    client = connect_to_opensearch()
    print("✅ Connected successfully!\n")

    # Handle delete-all flag
    if args.delete_all:
        delete_all_documents(client, index_name)
        return

    # Handle list-chunks flag (TEST 6 only)
    if args.list_chunks:
        print("=" * 60)
        print("TEST 6: Retrieve ALL documents metadata")
        print("=" * 60)

        try:
            response = client.search(
                index=index_name,
                body={
                    "query": {"match_all": {}},
                    "size": 1000
                }
            )
            total = response["hits"]["total"]["value"]
            results = response["hits"]["hits"]

            print(f"Total documents in index: {total}")
            print(f"Displayed: {len(results)} documents (up to 1000)\n")

            if total > 1000:
                print("⚠️  Note: Index has more than 1000 documents.\n")

            print("Documents metadata:\n")

            for i, hit in enumerate(results, 1):
                doc = hit["_source"]
                print(f"{i}. ID: {hit['_id']}")
                print(f"   Article ID: {doc.get('article_id', 'N/A')}")
                print(f"   Chunk Index: {doc.get('chunk_index', 'N/A')}")
                print(f"   Text length: {len(doc.get('text', ''))} chars")
                embedding_dim = len(doc.get('embedding', [])) if doc.get('embedding') else 0
                print(f"   Embedding dimensions: {embedding_dim}")
                if doc.get('metadata'):
                    print(f"   Metadata: {doc['metadata']}")
                print()

        except Exception as e:
            print(f"❌ Error retrieving metadata: {e}\n")
        return

    # Test 1: Insert a single document
    print("=" * 60)
    print("TEST 1: Insert a test document")
    print("=" * 60)

    test_doc = {
        "id": "test-chunk-001",
        "article_id": "test-article-001",
        "text": "This is a test chunk about economics and artificial intelligence.",
        "chunk_index": 0,
        "embedding": [0.1] * 1024,  # OpenSearch expects 1024 dimensions!
        "metadata": {
            "url": "https://example.com/test",
            "source": "test",
            "topic": "uk_economy",
        }
    }

    try:
        # OpenSearch Serverless does NOT support explicit document IDs
        # We must let it generate IDs automatically
        actions = [
            {"index": {"_index": index_name}},  # No _id!
            test_doc
        ]
        response = client.bulk(body=actions)
        print(f"Bulk response: {json.dumps(response, indent=2)}")

        if response.get("errors"):
            print(f"❌ Bulk operation had errors!")
            for item in response["items"]:
                print(f"   {item}")
            return
        else:
            # Extract the generated ID
            generated_id = response["items"][0]["index"]["_id"]
            print(f"✅ Document inserted successfully")
            print(f"   Generated ID: {generated_id}\n")
            test_doc["_id"] = generated_id  # Save for later retrieval
    except Exception as e:
        print(f"❌ Error inserting: {e}\n")
        import traceback
        traceback.print_exc()
        return

    # Test 2: Wait and try refresh
    print("=" * 60)
    print("TEST 2: Wait for index to sync (10 seconds)")
    print("=" * 60)

    import time
    time.sleep(20)

    try:
        client.indices.refresh(index=index_name)
        print("✅ Index refreshed\n")
    except Exception as e:
        print(f"⚠️  Refresh failed (may not be needed): {type(e).__name__}")
        print("   Continuing anyway...\n")

    # Test 3: Verify document structure via search
    print("=" * 60)
    print("TEST 3: Verify document structure")
    print("=" * 60)

    try:
        # Search for the newly inserted document by text
        response = client.search(
            index=index_name,
            body={
                "query": {"match_all": {}},
                "size": 1,
                "sort": [{"_seq_no": {"order": "desc"}}]
            }
        )
        if response["hits"]["hits"]:
            doc = response["hits"]["hits"][0]["_source"]
            print(f"✅ Latest document found")
            print(f"   Article ID: {doc.get('article_id', 'N/A')}")
            print(f"   Chunk Index: {doc.get('chunk_index', 'N/A')}")
            embedding_dim = len(doc.get('embedding', [])) if doc.get('embedding') else 0
            print(f"   Embedding dimensions: {embedding_dim}")
            print(f"   Has metadata: {bool(doc.get('metadata'))}\n")
        else:
            print("❌ No documents found\n")
    except Exception as e:
        print(f"❌ Error verifying document: {e}\n")

    # Test 4: Search with match_all
    print("=" * 60)
    print("TEST 4: Search with match_all")
    print("=" * 60)

    try:
        response = client.search(
            index=index_name,
            body={"query": {"match_all": {}}, "size": 100}
        )
        doc_count = response["hits"]["total"]["value"]
        returned_count = len(response["hits"]["hits"])
        print(f"✅ Total documents in index: {doc_count}")
        print(f"   Returned: {returned_count} documents (up to 100)\n")
    except Exception as e:
        print(f"❌ Error searching: {e}\n")

    # Test 5: Search by text
    print("=" * 60)
    print("TEST 5: Search by text query")
    print("=" * 60)

    try:
        response = client.search(
            index=index_name,
            body={
                "query": {
                    "match": {
                        "text": "economics"
                    }
                },
                "size": 10
            }
        )
        results = response["hits"]["hits"]
        print(f"Found {len(results)} documents matching 'economics':")
        for i, hit in enumerate(results, 1):
            doc = hit["_source"]
            print(f"  {i}. Article: {doc.get('article_id', 'N/A')}, Chunk: {doc.get('chunk_index', 'N/A')}")
        print()
    except Exception as e:
        print(f"❌ Error searching by text: {e}\n")

    # Test 5b: KNN Vector Search (Critical for HybridRetriever)
    print("=" * 60)
    print("TEST 5b: KNN Vector Search (Hybrid Retriever test)")
    print("=" * 60)

    try:
        # Get first document's embedding to test KNN
        response = client.search(
            index=index_name,
            body={
                "query": {"match_all": {}},
                "size": 1,
                "_source": ["embedding"],
            }
        )

        if not response["hits"]["hits"]:
            print("❌ No documents with embeddings found. Skipping KNN test.\n")
        else:
            first_doc = response["hits"]["hits"][0]["_source"]
            embedding = first_doc.get("embedding")

            if not embedding:
                print("❌ First document has no embedding. KNN test skipped.\n")
            else:
                embedding_dim = len(embedding)
                print(f"✅ Found embedding with {embedding_dim} dimensions")
                print(f"   Testing KNN search with this embedding...\n")

                # Test KNN query (this is what HybridRetriever uses)
                knn_response = client.search(
                    index=index_name,
                    body={
                        "size": 5,
                        "query": {
                            "knn": {
                                "embedding": {
                                    "vector": embedding,
                                    "k": 5,
                                }
                            }
                        },
                        "_source": ["article_id", "chunk_index"],
                    }
                )

                knn_results = knn_response["hits"]["hits"]
                print(f"✅ KNN search successful!")
                print(f"   Results returned: {len(knn_results)} documents")
                print(f"   Top score: {knn_results[0]['_score']:.4f}")
                print(f"   Results metadata:")
                for i, hit in enumerate(knn_results, 1):
                    doc = hit["_source"]
                    print(f"     {i}. Article: {doc.get('article_id', 'N/A')}, Chunk: {doc.get('chunk_index', 'N/A')}, Score: {hit['_score']:.4f}")

                print("\n✅ KNN WORKS! HybridRetriever similarity_search() will work correctly.\n")

    except Exception as e:
        print(f"❌ KNN search failed: {type(e).__name__}: {str(e)}")
        print("⚠️  This means HybridRetriever.similarity_search() will fail!")
        print("    Verify OpenSearch index has KNN enabled and embeddings are stored.\n")

    # Test 6: Show all document counts and summary
    print("=" * 60)
    print("TEST 6: Index summary (all documents)")
    print("=" * 60)

    try:
        # Use match_all query to count all documents
        response = client.search(
            index=index_name,
            body={
                "query": {"match_all": {}},
                "size": 1000
            }
        )
        total = response["hits"]["total"]["value"]
        retrieved = len(response["hits"]["hits"])

        print(f"✅ Total documents in index: {total}")
        print(f"   Retrieved: {retrieved} documents (up to 1000)\n")

        if total > 1000:
            print("⚠️  Index has more than 1000 documents. Pagination in use.\n")

        # Show summary stats
        if retrieved > 0:
            article_ids = set()
            embedding_count = 0
            for hit in response["hits"]["hits"]:
                doc = hit["_source"]
                article_ids.add(doc.get('article_id', 'unknown'))
                if doc.get('embedding'):
                    embedding_count += 1

            print(f"Summary:")
            print(f"  Unique articles: {len(article_ids)}")
            print(f"  Chunks with embeddings: {embedding_count}/{retrieved}\n")

            # Only show chunk details if --list-chunks flag is used
            if args.list_chunks:
                print("Chunk details:")
                for i, hit in enumerate(response["hits"]["hits"], 1):
                    doc = hit["_source"]
                    print(f"{i}. Article: {doc.get('article_id', 'N/A')}, Chunk: {doc.get('chunk_index', 'N/A')}")
                    print(f"   Text: {doc.get('text', '')[:100]}...")
                    embedding_dim = len(doc.get('embedding', [])) if doc.get('embedding') else 0
                    print(f"   Embedding dims: {embedding_dim}\n")

    except Exception as e:
        print(f"❌ Error retrieving summary: {e}\n")


if __name__ == "__main__":
    main()
