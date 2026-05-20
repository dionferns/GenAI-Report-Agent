"""Custom report structure evaluator."""

from datetime import datetime
from pathlib import Path

from reportagent.storage.archive import Archive


def run_summary_eval():
    """Evaluate all persisted reports for structural validity."""
    archive = Archive()

    # Get all reports from archive
    # For this simple version, we'll get the latest report
    latest_report = archive.get_latest_report("uk_ai_regulation")

    if not latest_report:
        print("No reports found in archive")
        return

    print("Evaluating report structure...\n")

    # Check summary word count
    summary_words = len(latest_report.summary.split())
    summary_valid = 90 <= summary_words <= 165
    print(f"✓ Summary word count: {summary_words} (valid: {summary_valid})")

    # Check key takeaways count
    takeaways_count = len(latest_report.key_takeaways)
    takeaways_valid = 3 <= takeaways_count <= 5
    print(f"✓ Key takeaways count: {takeaways_count} (valid: {takeaways_valid})")

    # Check organisations mentioned
    orgs_count = len(latest_report.organisations_mentioned)
    orgs_valid = orgs_count > 0
    print(f"✓ Organisations mentioned: {orgs_count} (valid: {orgs_valid})")

    # Check key terms
    terms_count = len(latest_report.key_terms)
    terms_valid = terms_count > 0
    print(f"✓ Key terms: {terms_count} (valid: {terms_valid})")

    # Check source URLs
    urls_count = len(latest_report.source_urls)
    urls_valid = urls_count > 0
    print(f"✓ Source URLs: {urls_count} (valid: {urls_valid})")

    # Check article IDs
    articles_count = len(latest_report.article_ids)
    articles_valid = articles_count > 0
    print(f"✓ Article IDs: {articles_count} (valid: {articles_valid})")

    # Overall pass
    all_valid = all([summary_valid, takeaways_valid, orgs_valid, terms_valid, urls_valid, articles_valid])

    print(f"\n{'='*50}")
    print(f"Overall report validity: {'✅ PASS' if all_valid else '❌ FAIL'}")
    print(f"{'='*50}")

    # Save results to markdown
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"summary_eval_{timestamp}.md"

    with open(results_file, "w") as f:
        f.write("# Report Structure Evaluation\n\n")
        f.write(f"**Run at:** {datetime.now().isoformat()}\n\n")
        f.write("## Validation Results\n\n")
        f.write(f"- Summary word count (90-165): **{summary_valid}** ({summary_words} words)\n")
        f.write(f"- Key takeaways (3-5): **{takeaways_valid}** ({takeaways_count} items)\n")
        f.write(f"- Organisations mentioned (>0): **{orgs_valid}** ({orgs_count} items)\n")
        f.write(f"- Key terms (>0): **{terms_valid}** ({terms_count} items)\n")
        f.write(f"- Source URLs (>0): **{urls_valid}** ({urls_count} items)\n")
        f.write(f"- Article IDs (>0): **{articles_valid}** ({articles_count} items)\n")
        f.write(f"\n**Overall: {'PASS ✅' if all_valid else 'FAIL ❌'}**\n")

    print(f"Results saved to: {results_file}")


if __name__ == "__main__":
    run_summary_eval()
