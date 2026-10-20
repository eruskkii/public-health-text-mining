#!/usr/bin/env python3
"""Build a reproducible, respectful vaccine-news corpus from Media Cloud exports."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import random
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2]
VENDOR = Path(__file__).resolve().parent / ".vendor"
sys.path.insert(0, str(VENDOR))

import pandas as pd
import requests
import trafilatura
from langdetect import DetectorFactory, detect_langs

DetectorFactory.seed = 271828

QUERY = "vaccine OR vaccination OR immunization OR immunisation"
COLLECTION = "United States - National"
COLLECTION_ID = "34412234"
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
USER_AGENT = "University vaccine discourse research/1.0 (respectful academic corpus builder)"
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
VACCINE_RE = re.compile(
    r"\b(vaccin(?:e|es|ated|ation|ations|ating)|immuni[sz](?:e|ed|ation|ations|ing)|"
    r"inoculat(?:e|ed|ion|ions|ing)|anti[- ]?vax(?:x|xer|xers|xing)?)\b",
    re.IGNORECASE,
)

thread_local = threading.local()
domain_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
domain_last_request: dict[str, float] = defaultdict(float)
robots_cache: dict[str, tuple[bool, str]] = {}
robots_guard = threading.Lock()


def canonicalize(raw_url: str) -> str:
    try:
        p = urlsplit(raw_url.strip())
        if p.scheme not in {"http", "https"} or not p.netloc:
            return ""
        host = p.netloc.lower().removeprefix("www.")
        path = re.sub(r"/{2,}", "/", p.path or "/")
        if path != "/":
            path = path.rstrip("/")
        query = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=False)
            if not k.lower().startswith("utm_") and k.lower() not in TRACKING_KEYS
        ]
        return urlunsplit((p.scheme.lower(), host, path, urlencode(sorted(query)), ""))
    except Exception:
        return ""


def session() -> requests.Session:
    if not hasattr(thread_local, "session"):
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        thread_local.session = s
    return thread_local.session


def polite_get(url: str, timeout: int = 20) -> requests.Response:
    domain = urlsplit(url).netloc.lower()
    with domain_locks[domain]:
        wait = 1.0 - (time.monotonic() - domain_last_request[domain])
        if wait > 0:
            time.sleep(wait)
        response = session().get(url, timeout=timeout, allow_redirects=True)
        domain_last_request[domain] = time.monotonic()
    return response


def robots_allowed(url: str) -> tuple[bool, str]:
    p = urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    with robots_guard:
        cached = robots_cache.get(base)
    if cached is not None:
        return cached
    robots_url = base + "/robots.txt"
    try:
        r = polite_get(robots_url, timeout=10)
        if r.status_code in {401, 403}:
            result = (False, f"robots_http_{r.status_code}")
        elif r.status_code >= 400:
            result = (True, f"robots_unavailable_http_{r.status_code}")
        else:
            parser = RobotFileParser()
            parser.set_url(robots_url)
            parser.parse(r.text.splitlines())
            allowed = parser.can_fetch(USER_AGENT, url)
            result = (allowed, "robots_allowed" if allowed else "robots_disallowed")
    except requests.RequestException as exc:
        # Standard robots convention permits access when robots.txt is unavailable.
        result = (True, f"robots_unavailable_{type(exc).__name__}")
    with robots_guard:
        robots_cache[base] = result
    return result


def read_metadata(input_dir: Path) -> tuple[list[dict], list[dict]]:
    csv_files = sorted(input_dir.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No Media Cloud CSV files found under {input_dir}")
    rows, inputs = [], []
    for path in csv_files:
        count = 0
        dates = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"id", "language", "media_name", "publish_date", "title", "url"}
            if not required.issubset(reader.fieldnames or []):
                continue
            for row in reader:
                count += 1
                date = (row.get("publish_date") or "")[:10]
                dates.append(date)
                if row.get("language") != "en" or not (START_DATE <= date <= END_DATE):
                    continue
                canonical = canonicalize(row.get("url", ""))
                if canonical:
                    row["canonical_url"] = canonical
                    row["date"] = date
                    row["input_file"] = path.name
                    rows.append(row)
        inputs.append({"file": path.name, "rows": count, "min_date": min(dates), "max_date": max(dates)})
    # Deterministic canonical-URL deduplication.
    unique = {}
    for row in rows:
        unique.setdefault(row["canonical_url"], row)
    return list(unique.values()), inputs


def stratified_sample(rows: list[dict], per_year: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_year: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_year[row["date"][:4]].append(row)
    selected = []
    for year in map(str, range(2020, 2026)):
        pool = by_year[year]
        rng.shuffle(pool)
        # Cap each publisher first to improve coverage, then backfill if necessary.
        counts = Counter()
        year_rows, overflow = [], []
        publisher_cap = max(3, per_year // 40)
        for row in pool:
            publisher = row.get("media_name") or urlsplit(row["canonical_url"]).netloc
            if counts[publisher] < publisher_cap and len(year_rows) < per_year:
                counts[publisher] += 1
                year_rows.append(row)
            else:
                overflow.append(row)
        if len(year_rows) < per_year:
            year_rows.extend(overflow[: per_year - len(year_rows)])
        selected.extend(year_rows)
    return selected


def language_is_english(text: str) -> tuple[bool, str, float]:
    try:
        guesses = detect_langs(text[:10000])
        top = guesses[0]
        return top.lang == "en" and top.prob >= 0.90, top.lang, float(top.prob)
    except Exception:
        return False, "unknown", 0.0


def fetch_one(row: dict) -> dict:
    result = {
        "id": row.get("id", ""), "date": row["date"], "source": row.get("media_name", ""),
        "title": row.get("title", ""), "url": row.get("url", ""),
        "canonical_url": row["canonical_url"], "status": "failed", "reason": "unknown",
        "http_status": "", "final_url": "", "language_detected": "", "language_probability": "",
        "word_count": 0, "text_hash": "", "text": "", "fetched_at_utc": "",
    }
    allowed, robot_note = robots_allowed(row["canonical_url"])
    if not allowed:
        result["reason"] = robot_note
        return result
    last_error = ""
    for attempt in range(3):
        try:
            response = polite_get(row["canonical_url"])
            result["http_status"] = response.status_code
            result["final_url"] = response.url
            result["fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
            if response.status_code in {401, 402, 403, 407, 451}:
                result["reason"] = f"access_restricted_http_{response.status_code}"
                return result
            if response.status_code == 429 or response.status_code >= 500:
                last_error = f"retryable_http_{response.status_code}"
                time.sleep(2 ** attempt)
                continue
            if response.status_code >= 400:
                result["reason"] = f"http_{response.status_code}"
                return result
            ctype = response.headers.get("content-type", "").lower()
            if "html" not in ctype:
                result["reason"] = "not_html"
                return result
            text = trafilatura.extract(
                response.text, url=response.url, include_comments=False, include_tables=False,
                favor_precision=True, deduplicate=True,
            ) or ""
            text = re.sub(r"\s+", " ", text).strip()
            words = len(text.split())
            result["word_count"] = words
            if not text:
                result["reason"] = "empty_extraction"
                return result
            if words < 300:
                result["reason"] = "too_short_under_300_words"
                return result
            if not VACCINE_RE.search(text):
                result["reason"] = "irrelevant_no_vaccine_term_in_body"
                return result
            is_en, lang, prob = language_is_english(text)
            result["language_detected"] = lang
            result["language_probability"] = round(prob, 6)
            if not is_en:
                result["reason"] = "non_english_body"
                return result
            result["text"] = text
            result["text_hash"] = hashlib.sha256(text.lower().encode("utf-8")).hexdigest()
            result["status"] = "success"
            result["reason"] = "usable"
            return result
        except requests.Timeout:
            last_error = "timeout"
        except requests.TooManyRedirects:
            result["reason"] = "too_many_redirects"
            return result
        except requests.RequestException as exc:
            last_error = f"request_error_{type(exc).__name__}"
        except Exception as exc:
            result["reason"] = f"extraction_error_{type(exc).__name__}"
            return result
        time.sleep(2 ** attempt)
    result["reason"] = last_error or "retries_exhausted"
    return result


FIELDS = [
    "id", "date", "source", "title", "url", "canonical_url", "status", "reason", "http_status",
    "final_url", "language_detected", "language_probability", "word_count", "text_hash", "text",
    "fetched_at_utc",
]


def load_checkpoint(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = {row["canonical_url"]: row for row in csv.DictReader(handle)}
    # Versions before 2026-10-20 mislabeled a robots denial as
    # "robots_allowed". Normalize old resumable checkpoints in memory.
    for row in rows.values():
        if row.get("status") == "failed" and row.get("reason") == "robots_allowed":
            row["reason"] = "robots_disallowed"
    return rows


def append_checkpoint(path: Path, result: dict, lock: threading.Lock) -> None:
    with lock:
        new_file = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
            if new_file:
                writer.writeheader()
            writer.writerow(result)
            handle.flush()


def write_outputs(results: list[dict], parquet_path: Path, report_path: Path, inputs: list[dict],
                  candidate_count: int, seed: int) -> int:
    successful = [r for r in results if r.get("status") == "success"]
    unique_text = {}
    duplicate_text = 0
    for row in successful:
        if row["text_hash"] in unique_text:
            duplicate_text += 1
        else:
            unique_text[row["text_hash"]] = row
    usable = list(unique_text.values())
    records = [{
        "document_id": "mediacloud:" + r["id"], "text": r["text"],
        # Fastparquet writes this as a standard timestamp at midnight. In R,
        # arrow::read_parquet() returns a POSIXct-compatible column that can be
        # converted losslessly with as.Date().
        "date": pd.to_datetime(r["date"]), "source": r["source"],
        "source_type": "news_article", "dataset_origin": "mediacloud", "language": "en",
        "url": r["canonical_url"],
    } for r in usable]
    frame = pd.DataFrame(records, columns=[
        "document_id", "text", "date", "source", "source_type", "dataset_origin", "language", "url"
    ])
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(parquet_path, engine="fastparquet", index=False, compression="snappy")

    reasons = Counter(r.get("reason", "unknown") for r in results if r.get("status") != "success")
    years = Counter(r["date"][:4] for r in usable)
    publishers = Counter(r["source"] for r in usable)
    word_counts = sorted(int(r["word_count"]) for r in usable)
    median = (word_counts[(len(word_counts)-1)//2] + word_counts[len(word_counts)//2]) / 2 if word_counts else 0
    responded = sum(bool(r.get("http_status")) for r in results)
    fetched = sum(str(r.get("http_status", "")).isdigit() and 200 <= int(r["http_status"]) < 300 for r in results)
    success_rate = (100 * len(usable) / candidate_count) if candidate_count else 0
    lines = [
        "# News acquisition report", "", "## Acquisition specification", "",
        f"- Query: `{QUERY}`", f"- Collection: {COLLECTION} (`{COLLECTION_ID}`)",
        f"- Period: {START_DATE} through {END_DATE}, inclusive",
        "- Acquisition method: Media Cloud CSV exports supplied by the researcher; public article pages fetched with robots.txt checks, a per-domain delay, timeouts, and exponential-backoff retries.",
        f"- Sampling: fixed seed `{seed}`, year-stratified, publisher-diversified sample.", "",
        "## Results", "", f"- Candidate URLs selected: {candidate_count:,}",
        f"- URLs with an HTTP response: {responded:,}",
        f"- Pages successfully fetched (HTTP 2xx): {fetched:,}",
        f"- Successful qualifying extractions before text deduplication: {len(successful):,}",
        f"- Duplicate extracted bodies removed: {duplicate_text:,}",
        f"- Usable unique English vaccine articles: {len(usable):,}",
        f"- Extraction success rate: {success_rate:.1f}% of selected candidate URLs",
        f"- Usable date range: {min((r['date'] for r in usable), default='n/a')} to {max((r['date'] for r in usable), default='n/a')}",
        f"- Median article length: {median:,.0f} words", "", "## Rejections and failures", "",
    ]
    if reasons:
        lines.extend(f"- {reason}: {count:,}" for reason, count in reasons.most_common())
    else:
        lines.append("- None")
    lines += ["", "## Annual distribution", ""]
    lines.extend(f"- {year}: {years.get(year, 0):,}" for year in map(str, range(2020, 2026)))
    lines += ["", "## Publisher distribution (top 25)", ""]
    lines.extend(f"- {source}: {count:,}" for source, count in publishers.most_common(25))
    lines += ["", "## Input exports", ""]
    lines.extend(f"- `{x['file']}`: {x['rows']:,} rows, {x['min_date']} to {x['max_date']}" for x in inputs)
    lines += [
        "", "## Known biases and limitations", "",
        "- This is a reproducible stratified sample, not a census. Years are equally sampled even though Media Cloud contains many more matching records in 2020–2022.",
        "- Media Cloud coverage depends on its source list, feed/indexing success, and the United States – National collection definition.",
        "- Publisher availability is non-random: deleted pages, changed URLs, robots exclusions, paywalls, authentication, anti-bot systems, and JavaScript-only rendering reduce extraction success.",
        "- No paywalls, CAPTCHAs, authentication, or access controls were bypassed.",
        "- English and relevance filters can make classification errors. Relevance requires a vaccine-related term in the extracted body; headlines/snippets are never substituted for article text.",
        "- Syndicated wire stories may remain when their extracted text differs enough to have a different exact SHA-256 hash.",
        "", "## Reproduction", "",
        "From the project root, place Media Cloud exports under `data/raw/News/media cloud/`, then run:", "",
        "```powershell",
        "python -m pip install --target R/news_acquisition/.vendor -r R/news_acquisition/requirements.txt",
        "python R/news_acquisition/run_pipeline.py --candidates-per-year 500 --workers 8",
        "```", "",
        "The checkpoint at `data/raw/mediacloud/fetch_checkpoint.csv` makes interrupted runs resumable. Delete it only when intentionally starting a new acquisition run.",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(usable)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=ROOT / "data/raw/News/media cloud")
    parser.add_argument("--runtime-dir", type=Path, default=ROOT / "data/raw/mediacloud")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/vaccine_news.parquet")
    parser.add_argument("--report", type=Path, default=ROOT / "docs/news_acquisition_report.md")
    parser.add_argument("--candidates-per-year", type=int, default=500)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=20202025)
    args = parser.parse_args()

    args.runtime_dir.mkdir(parents=True, exist_ok=True)
    metadata, inputs = read_metadata(args.input_dir)
    candidates = stratified_sample(metadata, args.candidates_per_year, args.seed)
    manifest = {
        "query": QUERY, "collection": COLLECTION, "collection_id": COLLECTION_ID,
        "period": [START_DATE, END_DATE], "seed": args.seed,
        "candidates_per_year": args.candidates_per_year, "candidate_count": len(candidates),
        "input_exports": inputs,
    }
    (args.runtime_dir / "acquisition_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    checkpoint = args.runtime_dir / "fetch_checkpoint.csv"
    existing = load_checkpoint(checkpoint)
    pending = [r for r in candidates if r["canonical_url"] not in existing]
    print(f"Metadata unique URLs: {len(metadata):,}; candidates: {len(candidates):,}; pending: {len(pending):,}", flush=True)
    checkpoint_lock = threading.Lock()
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fetch_one, row): row for row in pending}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            append_checkpoint(checkpoint, result, checkpoint_lock)
            existing[result["canonical_url"]] = result
            completed += 1
            if completed % 50 == 0:
                usable_so_far = sum(r.get("status") == "success" for r in existing.values())
                print(f"Completed {completed:,}/{len(pending):,}; successes in checkpoint: {usable_so_far:,}", flush=True)

    candidate_urls = {r["canonical_url"] for r in candidates}
    results = [r for url, r in existing.items() if url in candidate_urls]
    count = write_outputs(results, args.output, args.report, inputs, len(candidates), args.seed)
    print(f"Wrote {args.output} with {count:,} usable articles", flush=True)


if __name__ == "__main__":
    main()

