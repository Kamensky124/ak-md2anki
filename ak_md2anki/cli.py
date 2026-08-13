"""CLI entry-point: build / sync / export / list."""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from pathlib import Path

from ak_md2anki.enrich import enrich
from ak_md2anki.extract import extract_prose, extract_text
from ak_md2anki.models import Card
from ak_md2anki.sink import export_apkg, sync_cards
from ak_md2anki.store import load, save

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format="%(levelname)-7s %(message)s", level=level, force=True)


def _scan_path(path: Path) -> list[Path]:
    """Collect .md files from a file or directory (recursive)."""
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.md"))
    print(f"error: path not found: {path}", file=sys.stderr)
    sys.exit(1)


# ── subcommands ─────────────────────────────────────────────────────────────


def cmd_build(args: argparse.Namespace) -> None:
    _setup_logging(args.verbose)
    target = Path(args.path)
    files = _scan_path(target)
    if not files:
        print("No .md files found.", file=sys.stderr)
        sys.exit(1)

    out_path = args.out or "cards.json"
    existing_cards = load(out_path) if not args.force else []

    existing_by_source: dict[str, tuple[str, list[Card]]] = {}
    for c in existing_cards:
        if c.source:
            try:
                norm = str(Path(c.source).resolve())
                if norm not in existing_by_source:
                    existing_by_source[norm] = (c.source_hash, [])
                existing_by_source[norm][1].append(c)
            except Exception:
                pass

    all_cards: list[Card] = []
    reused_count = 0

    for fp in files:
        rel = fp.relative_to(target) if target.is_dir() else fp.name
        abs_path = str(fp.resolve())
        try:
            content = fp.read_text(encoding="utf-8")
        except Exception:
            logger.error("Failed to read %s", fp, exc_info=True)
            sys.exit(1)

        current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        use_prose = getattr(args, "prose", False)
        is_force = getattr(args, "force", False)

        if (
            not is_force
            and abs_path in existing_by_source
            and existing_by_source[abs_path][0] == current_hash
        ):
            cached_cards = existing_by_source[abs_path][1]
            logger.info("Skipping unchanged %s (%d cards reused)", rel, len(cached_cards))
            all_cards.extend(cached_cards)
            reused_count += len(cached_cards)
            continue

        logger.info("Parsing %s", rel)
        try:
            # Prose extractor only runs when no structured cards were found:
            # both extractors share the same id scheme, so running both on one
            # file would emit duplicate ids (violating the one-card-per-id
            # invariant). Prose is for files lacking tables / Q: blocks.
            parsed = extract_text(content, source=str(fp))
            if not parsed and use_prose:
                logger.info("  No structured cards found. Running prose extractor…")
                parsed = extract_prose(content, source=str(fp))

            all_cards.extend(parsed)
            logger.info("  → %d cards", len(parsed))
        except Exception:
            logger.error("Failed to parse %s", fp, exc_info=True)
            sys.exit(1)

    if not args.no_enrich:
        unenriched_count = sum(1 for c in all_cards if not c.enriched)
        if unenriched_count > 0:
            logger.info("Enriching %d cards via OpenRouter…", unenriched_count)
            all_cards = enrich(
                all_cards,
                cache_path=args.cache_file,
                cache_enabled=not args.no_cache,
            )
        else:
            logger.info("All cards are already enriched — skipping OpenRouter API calls")

    save(out_path, all_cards)
    n_vocab = sum(1 for c in all_cards if c.type.value == "vocab")
    n_qa = sum(1 for c in all_cards if c.type.value == "qa")
    n_enriched = sum(1 for c in all_cards if c.enriched)
    reused_msg = f", {reused_count} reused" if reused_count > 0 else ""
    print(
        f"✅ {len(all_cards)} cards ({n_vocab} vocab, {n_qa} qa, {n_enriched} enriched{reused_msg})"
    )
    print(f"   written to {out_path}")


def cmd_sync(args: argparse.Namespace) -> None:
    _setup_logging(args.verbose)
    in_path = args.in_ or "cards.json"
    cards = load(in_path)
    if not cards:
        print("No cards to sync.", file=sys.stderr)
        sys.exit(1)

    if args.deck:
        cards = [c for c in cards if c.deck == args.deck]
        if not cards:
            print(f"No cards for deck '{args.deck}'.", file=sys.stderr)
            sys.exit(1)

    dry = args.dry_run or False
    try:
        counts = sync_cards(cards, dry_run=dry)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)

    label = "would sync" if dry else "synced"
    print(f"✅ {label}: {counts['added']} added, {counts['updated']} updated")


def cmd_export(args: argparse.Namespace) -> None:
    _setup_logging(args.verbose)
    in_path = args.in_ or "cards.json"
    cards = load(in_path)
    if not cards:
        print("No cards to export.", file=sys.stderr)
        sys.exit(1)

    if args.deck:
        cards = [c for c in cards if c.deck == args.deck]
        if not cards:
            print(f"No cards for deck '{args.deck}'.", file=sys.stderr)
            sys.exit(1)

    apkg_path = args.apkg if args.apkg.endswith(".apkg") else f"{args.apkg}.apkg"
    export_apkg(cards, apkg_path)
    print(f"✅ exported {len(cards)} cards → {apkg_path}")


def cmd_list(args: argparse.Namespace) -> None:
    _setup_logging(args.verbose)
    in_path = args.in_ or "cards.json"
    cards = load(in_path)
    if not cards:
        print("No cards found.")
        return

    if args.deck:
        cards = [c for c in cards if c.deck == args.deck]

    for c in sorted(cards, key=lambda x: x.id):
        e = "✨" if c.enriched else "  "
        print(
            f"  [{c.type.value}]{e} {c.id:50s}  {c.fields.get('Term','') or c.fields.get('Question','')}"
        )
    print(f"\n{len(cards)} cards")


# ── main ────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ak-md2anki")
    ap.add_argument("--verbose", "-v", action="store_true")
    sub = ap.add_subparsers(dest="command", required=True)

    b = sub.add_parser("build", help="Build cards.json from Markdown")
    b.add_argument("path", help="Markdown file or directory (recursive .md)")
    b.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force full rebuild ignoring cached source hashes",
    )
    b.add_argument(
        "--prose",
        action="store_true",
        help="Enable LLM prose extractor for unstructured Markdown notes",
    )
    b.add_argument("--no-enrich", action="store_true", help="Skip AI enrichment")
    b.add_argument("--out", default="cards.json", help="Output path (default: cards.json)")
    b.add_argument("--cache-file", help="Path to enrichment cache JSON file")
    b.add_argument(
        "--no-cache", action="store_true", help="Disable reading/writing enrichment cache"
    )
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("sync", help="Upsert cards into Anki via AnkiConnect")
    s.add_argument("--in", dest="in_", default="cards.json", help="cards.json path")
    s.add_argument("--deck", help="Sync only this deck")
    s.add_argument("--dry-run", action="store_true", help="Show what would change without writing")
    s.set_defaults(func=cmd_sync)

    e = sub.add_parser("export", help="Export a portable .apkg file")
    e.add_argument("--apkg", required=True, help="Output .apkg path")
    e.add_argument("--in", dest="in_", default="cards.json", help="cards.json path")
    e.add_argument("--deck", help="Export only this deck")
    e.set_defaults(func=cmd_export)

    ls = sub.add_parser("list", help="List cards from cards.json")
    ls.add_argument("--in", dest="in_", default="cards.json", help="cards.json path")
    ls.add_argument("--deck", help="Show only this deck")
    ls.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
