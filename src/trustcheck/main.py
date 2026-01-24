"""
TrustCheck Main Entry Point.

Application startup and CLI interface.
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

import uvicorn

from trustcheck.config import settings


def setup_logging() -> None:
    """Configure application logging."""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


def run_server() -> None:
    """Run the FastAPI server."""
    setup_logging()

    uvicorn.run(
        "trustcheck.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


async def run_scrape(source: str | None = None) -> None:
    """Run a one-time scrape."""
    setup_logging()

    from trustcheck.database import init_db
    from trustcheck.domain import DataSource
    from trustcheck.services import get_ingestion_service

    await init_db()

    service = get_ingestion_service()

    if source:
        try:
            data_source = DataSource(source.upper())
            print(f"Scraping {data_source.value}...")
            result = await service.ingest_source(data_source)
            print(f"Result: {result.status.value}")
            print(f"  Processed: {result.entities_processed}")
            print(f"  Added: {result.entities_added}")
            print(f"  Modified: {result.entities_modified}")
            print(f"  Removed: {result.entities_removed}")
            if result.error_message:
                print(f"  Error: {result.error_message}")
        except ValueError:
            print(f"Invalid source: {source}")
            print("Valid sources: OFAC_SDN, UN, EU, UK")
            sys.exit(1)
    else:
        print("Scraping all sources...")
        results = await service.ingest_all_sources()
        for src, result in results.items():
            print(f"\n{src.value}: {result.status.value}")
            print(f"  Processed: {result.entities_processed}")
            print(f"  Added: {result.entities_added}")
            print(f"  Modified: {result.entities_modified}")
            print(f"  Removed: {result.entities_removed}")


async def run_screen(name: str, threshold: float = 0.8) -> None:
    """Run a one-time screening."""
    setup_logging()

    from trustcheck.database import init_db
    from trustcheck.domain import ScreeningRequest
    from trustcheck.services import get_screening_service

    await init_db()

    service = get_screening_service()
    request = ScreeningRequest(name=name, threshold=threshold)

    print(f"Screening: {name}")
    print(f"Threshold: {threshold}")
    print("-" * 50)

    result = await service.screen(request)

    if not result.matches:
        print("No matches found.")
    else:
        print(f"Found {len(result.matches)} matches:")
        for i, match in enumerate(result.matches, 1):
            print(f"\n{i}. {match.entity.primary_name}")
            print(f"   Score: {match.score:.2%}")
            print(f"   Type: {match.entity.entity_type.value}")
            print(f"   Match type: {match.match_type.value}")
            if match.entity.programs:
                print(f"   Programs: {', '.join(match.entity.programs[:3])}")

    print(f"\nProcessing time: {result.processing_time_ms:.2f}ms")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="TrustCheck - Sanctions Screening Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  trustcheck serve              Start the web server
  trustcheck scrape             Scrape all sanctions lists
  trustcheck scrape OFAC_SDN    Scrape only OFAC SDN
  trustcheck screen "John Doe"  Screen a name
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start the web server")
    serve_parser.add_argument("--host", default=settings.host, help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=settings.port, help="Port to bind to")

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Run a scraping operation")
    scrape_parser.add_argument(
        "source",
        nargs="?",
        help="Source to scrape (OFAC_SDN, UN, EU, UK). Omit to scrape all.",
    )

    # Screen command
    screen_parser = subparsers.add_parser("screen", help="Screen a name")
    screen_parser.add_argument("name", help="Name to screen")
    screen_parser.add_argument(
        "--threshold",
        "-t",
        type=float,
        default=0.8,
        help="Match threshold (0.0-1.0)",
    )

    args = parser.parse_args()

    if args.command == "serve":
        settings.host = args.host
        settings.port = args.port
        run_server()
    elif args.command == "scrape":
        asyncio.run(run_scrape(args.source))
    elif args.command == "screen":
        asyncio.run(run_screen(args.name, args.threshold))
    else:
        # Default to serve
        run_server()


if __name__ == "__main__":
    main()
