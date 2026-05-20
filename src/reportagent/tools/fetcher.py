"""Web content fetcher tool."""

import asyncio
import httpx
from urllib.robotparser import RobotFileParser
from datetime import datetime
import structlog

log = structlog.get_logger()


async def fetch_urls(urls: list[str]) -> list[tuple[str, str, datetime]]:
    """
    Fetches the raw HTML content of a list of URLs asynchronously, respecting robots.txt.
    Returns list of (url, html, fetched_at) tuples.
    """
    results = []
    errors = []

    async def fetch_single(url: str, session: httpx.AsyncClient) -> None:
        try:
            # Check robots.txt
            robot_parser = RobotFileParser()
            robot_url = f"{httpx.URL(url).scheme}://{httpx.URL(url).host}/robots.txt"

            try:
                robot_parser.set_url(robot_url)
                robot_parser.read()
                if not robot_parser.can_fetch("GenAI-Report-Agent/1.0", url):
                    log.warning("url_blocked_by_robots_txt", url=url)
                    return
            except Exception:
                # If robots.txt check fails, continue anyway
                pass

            # Fetch the URL
            response = await session.get(
                url,
                timeout=10.0,
                headers={"User-Agent": "GenAI-Report-Agent/1.0"},
            )
            response.raise_for_status()

            results.append((url, response.text, datetime.utcnow()))
            log.debug("url_fetched", url=url)

        except httpx.HTTPError as e:
            log.error("http_error", url=url, error=str(e))
            errors.append(str(e))
        except Exception as e:
            log.error("fetch_error", url=url, error=str(e))
            errors.append(str(e))

    # Fetch with concurrency limit
    async with httpx.AsyncClient() as session:
        semaphore = asyncio.Semaphore(5)

        async def bounded_fetch(url: str):
            async with semaphore:
                await fetch_single(url, session)

        await asyncio.gather(*[bounded_fetch(url) for url in urls])

    log.info("urls_fetched", count=len(results), errors=len(errors))
    return results
