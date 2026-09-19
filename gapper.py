#!/usr/bin/env python3
"""Query-independent public HN/Make acquisition. Python 3 standard library only."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HN = "https://hacker-news.firebaseio.com/v0"
MAKE = "https://community.make.com"
UTC = timezone.utc


def stamp():
    return datetime.now(UTC).isoformat()


def parse_time(value):
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, UTC)
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("Timestamp needs timezone")
        return dt.astimezone(UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def in_window(value, start, end):
    dt = parse_time(value)
    return dt is not None and start <= dt < end


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
    tmp.replace(path)


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "br", "div", "li", "pre"}:
            self.parts.append("\n")


def plain(value):
    p = Text()
    p.feed(value or "")
    return "".join(p.parts).strip()


def retry_delay(header, attempt):
    try:
        return max(0, float(header))
    except (ValueError, TypeError):
        try:
            return max(0, (parsedate_to_datetime(header) - datetime.now(UTC)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 2 ** attempt


class Client:
    """Success cache + full response archive; retries remain visible in attempts."""
    def __init__(self, root, source, rps):
        self.root, self.source, self.rps = Path(root), source, rps
        self.lock = threading.Lock()
        self.next_request = 0.0

    def pace(self):
        with self.lock:
            now = time.monotonic()
            slot = max(now, self.next_request)
            self.next_request = slot + 1 / self.rps
        time.sleep(max(0, slot - now))

    def fetch(self, url):
        key = hashlib.sha256(url.encode()).hexdigest()
        relative = Path("responses") / self.source / (key + ".json.gz")
        path = self.root / relative
        previous = None
        if path.exists():
            with gzip.open(path, "rt") as f:
                previous = json.load(f)
            if previous["ok"]:
                return previous
        attempts = list(previous.get("attempts", [])) if previous else []
        for attempt in range(4):
            self.pace()
            status, headers, body, error = None, {}, "", None
            try:
                req = Request(url, headers={"User-Agent": "gapper-research-probe/0.1",
                                             "Accept": "application/json"})
                with urlopen(req, timeout=30) as response:
                    status = response.status
                    headers = dict(response.headers.items())
                    body = response.read().decode("utf-8")
            except HTTPError as exc:
                status, headers = exc.code, dict(exc.headers.items())
                try:
                    body = exc.read().decode("utf-8", errors="replace")
                finally:
                    exc.close()
                error = "HTTPError"
            except (URLError, TimeoutError, OSError, UnicodeError) as exc:
                error = type(exc).__name__
            retrieved = stamp()
            payload, decoded = None, False
            if status == 200:
                try:
                    payload = json.loads(body)
                    decoded = True
                except ValueError:
                    error = "InvalidJSON"
            ok = status == 200 and decoded
            attempts.append({"retrieved_at": retrieved, "status": status,
                             "headers": headers, "body": body, "error": error})
            result = {"url": url, "source": self.source, "retrieved_at": retrieved,
                      "status": status, "ok": ok, "payload": payload,
                      "response_ref": str(relative), "attempts": attempts}
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            with gzip.open(tmp, "wt", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False)
            tmp.replace(path)
            if ok or status in {400, 401, 403, 404, 410}:
                return result
            if attempt < 3:
                retry_after = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
                delay = retry_delay(retry_after, attempt)
                if delay > 60:
                    # Respect a long cooldown by stopping, not retrying too early.
                    return result
                time.sleep(delay)
        return result


def hn_parent(item):
    return item.get("parent") or item.get("poll")


def hn_root(item_id, nodes):
    seen = set()
    depth = 0
    while item_id not in seen:
        seen.add(item_id)
        node = nodes.get(item_id)
        if not node:
            return None, None
        parent = hn_parent(node)
        if not parent:
            # A deleted/malformed comment without a parent is not a root story.
            return (item_id, depth) if node.get("type") in {"story", "job", "poll"} else (None, None)
        item_id, depth = parent, depth + 1
    return None, None


def hn_collect(client, start, end, workers=16, max_ids=60000, max_context=15000):
    stats = {"method": "contiguous descending item IDs, no topical filters",
             "guard_hours": 6, "max_ids": max_ids, "max_context": max_context,
             "failed_ids": [], "null_ids": [], "missing_time_ids": [],
             "timestamp_inversions": 0, "context_failed_ids": []}
    maximum = client.fetch(HN + "/maxitem.json")
    if not maximum["ok"] or not isinstance(maximum["payload"], int):
        stats["stop_reason"] = "maxitem_unavailable"
        return [], [], stats
    top = maximum["payload"]
    stats["maxitem_snapshot"] = top
    nodes, responses, scanned, latest = {}, {}, [], None
    def fetch(i):
        return i, client.fetch(f"{HN}/item/{i}.json")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        reason = "id_cap"
        for offset in range(0, min(top, max_ids), 400):
            ids = list(range(top - offset, max(0, top - min(offset + 400, max_ids)), -1))
            batch_times = []
            for i, response in pool.map(fetch, ids):
                scanned.append(i)
                responses[i] = response
                item = response["payload"]
                if not response["ok"]:
                    stats["failed_ids"].append(i)
                elif item is None:
                    stats["null_ids"].append(i)
                elif not isinstance(item, dict) or item.get("id") != i:
                    stats["failed_ids"].append(i)
                else:
                    nodes[i] = item
                    dt = parse_time(item.get("time"))
                    if dt is None:
                        stats["missing_time_ids"].append(i)
                    else:
                        batch_times.append(dt)
                        if latest is not None and dt > latest:
                            stats["timestamp_inversions"] += 1
                        latest = dt
            print(f"HN scanned {len(scanned)} IDs; oldest batch timestamp "
                  f"{min(batch_times).isoformat() if batch_times else 'unknown'}", flush=True)
            if len(batch_times) >= 50 and max(batch_times) < start - timedelta(hours=6):
                reason = "guard_boundary_reached"
                break
            if len(stats["failed_ids"]) >= 100 and not batch_times:
                reason = "source_unavailable"
                break
        stats.update(stop_reason=reason, scanned_ids=len(scanned),
                     scanned_min_id=min(scanned) if scanned else None,
                     scanned_max_id=top)
        selected = {i for i, p in nodes.items() if in_window(p.get("time"), start, end)}
        needed = set(selected)
        pending = {hn_parent(nodes[i]) for i in needed if hn_parent(nodes[i])}
        visited = set()
        fetched_context = 0
        while pending:
            frontier = pending - visited
            if not frontier:
                break
            visited.update(frontier)
            missing = sorted(frontier - responses.keys())
            remaining = max_context - fetched_context
            if len(missing) > remaining:
                stats["context_cap_hit"] = True
                missing = missing[:max(0, remaining)]
            for i, response in pool.map(fetch, missing):
                fetched_context += 1
                responses[i] = response
                if response["ok"] and isinstance(response["payload"], dict):
                    nodes[i] = response["payload"]
                else:
                    stats["context_failed_ids"].append(i)
            needed.update(frontier & nodes.keys())
            pending = {hn_parent(nodes[i]) for i in frontier if i in nodes and hn_parent(nodes[i])}
        records = []
        for i in sorted(needed):
            p = nodes[i]
            root, depth = hn_root(i, nodes)
            dt = parse_time(p.get("time"))
            records.append({"source": "hacker_news", "native_id": str(i),
                "item_type": p.get("type", "unknown"), "author": p.get("by"),
                "created_at": dt.isoformat() if dt else None, "title": p.get("title"),
                "text": plain(p.get("text")), "body_html": p.get("text"),
                "body_raw": None, "url": f"https://news.ycombinator.com/item?id={i}",
                "external_url": p.get("url"),
                "parent_id": str(hn_parent(p)) if hn_parent(p) else None,
                "thread_id": str(root) if root else None, "depth": depth,
                "child_ids": [str(x) for x in p.get("kids", [])],
                "scope": "sample" if i in selected else "context",
                "retrieved_at": responses[i]["retrieved_at"],
                "response_ref": responses[i]["response_ref"], "source_native": p})
        stats["unresolved_thread_sample_ids"] = [r["native_id"] for r in records
                                                  if r["scope"] == "sample" and not r["thread_id"]]
        stats["context_requests"] = fetched_context
    return [r for r in records if r["scope"] == "sample"], [r for r in records if r["scope"] == "context"], stats


def make_collect(client, start, end, max_pages=100, max_topic_posts=2000):
    stats = {"method": "public latest posts across all exposed categories, before-ID pagination",
             "guard_hours": 6, "page_urls": [], "failed_urls": [], "stream_gaps": {},
             "missing_time_ids": [], "timestamp_inversions": 0, "topic_caps": [],
             "max_pages": max_pages, "max_topic_posts": max_topic_posts}
    posts, responses, topics = {}, {}, {}
    before, last_time = None, None
    reason = "page_cap"
    for page in range(max_pages):
        url = MAKE + "/posts.json" + (f"?before={before}" if before else "")
        result = client.fetch(url)
        stats["page_urls"].append(url)
        if not result["ok"] or not isinstance(result["payload"], dict):
            stats["failed_urls"].append(url)
            reason = "page_unavailable"
            break
        batch = result["payload"].get("latest_posts")
        if not isinstance(batch, list):
            reason = "unexpected_schema"
            break
        if not batch:
            reason = "feed_exhausted"
            break
        times = []
        for p in batch:
            posts[p["id"]], responses[p["id"]] = p, result
            dt = parse_time(p.get("created_at"))
            if dt is None:
                stats["missing_time_ids"].append(p["id"])
            else:
                times.append(dt)
                if last_time and dt > last_time:
                    stats["timestamp_inversions"] += 1
                last_time = dt
        print(f"Make page {page + 1}: {len(batch)} posts", flush=True)
        cursor = min(p["id"] for p in batch)
        if before is not None and cursor >= before:
            reason = "nonadvancing_cursor"
            break
        before = cursor
        if times and len(times) == len(batch) and max(times) < start - timedelta(hours=6):
            reason = "guard_boundary_reached"
            break
    stats["stop_reason"] = reason
    stats["enumerated_post_count"] = len(posts)
    selected = {i for i, p in posts.items() if in_window(p.get("created_at"), start, end)}
    feed_topic_ids = {posts[i]["topic_id"] for i in selected}
    topic_candidates = set(feed_topic_ids)
    # Public latest posts omit some system/hidden posts. Supplement with the
    # unfiltered recent-activity topic listing, then select by post creation time.
    stats["activity_page_urls"] = []
    stats["activity_stop_reason"] = "page_cap"
    seen_topics = set()
    for page in range(max_pages):
        url = MAKE + "/latest.json" + (f"?page={page}" if page else "")
        result = client.fetch(url)
        stats["activity_page_urls"].append(url)
        if not result["ok"] or not isinstance(result["payload"], dict):
            stats["failed_urls"].append(url)
            stats["activity_stop_reason"] = "page_unavailable"
            break
        listing = result["payload"].get("topic_list", {})
        batch = listing.get("topics")
        if not isinstance(batch, list):
            stats["activity_stop_reason"] = "unexpected_schema"
            break
        if not batch:
            stats["activity_stop_reason"] = "feed_exhausted"
            break
        ids = {t["id"] for t in batch}
        if not ids - seen_topics:
            stats["activity_stop_reason"] = "nonadvancing_page"
            break
        seen_topics.update(ids)
        times = []
        for topic in batch:
            dt = parse_time(topic.get("bumped_at") or topic.get("last_posted_at") or topic.get("created_at"))
            if dt is None or dt >= start - timedelta(hours=6):
                topic_candidates.add(topic["id"])
            if not topic.get("pinned"):
                times.append(dt)
        if times and all(dt is not None and dt < start - timedelta(hours=6) for dt in times):
            stats["activity_stop_reason"] = "guard_boundary_reached"
            break
        if not listing.get("more_topics_url"):
            stats["activity_stop_reason"] = "feed_exhausted"
            break
    topic_ids = sorted(topic_candidates)
    stats["activity_extra_topic_ids"] = sorted(topic_candidates - feed_topic_ids)
    needed = set(selected)
    for index, topic_id in enumerate(topic_ids):
        url = f"{MAKE}/t/{topic_id}.json"
        result = client.fetch(url)
        if not result["ok"] or not isinstance(result["payload"], dict):
            stats["failed_urls"].append(url)
            continue
        topic = result["payload"]
        topics[topic_id] = topic
        stream = topic.get("post_stream", {})
        returned = stream.get("posts", [])
        # Preserve feed records as the primary observation when already fetched.
        for p in returned:
            posts.setdefault(p["id"], p)
            responses.setdefault(p["id"], result)
            needed.add(p["id"])
        wanted = stream.get("stream", [])
        if len(wanted) > max_topic_posts:
            stats["topic_caps"].append(topic_id)
        missing = [i for i in wanted[:max_topic_posts] if i not in posts]
        for offset in range(0, len(missing), 20):
            query = urlencode({"post_ids[]": missing[offset:offset + 20]}, doseq=True)
            url = f"{MAKE}/t/{topic_id}/posts.json?{query}"
            block = client.fetch(url)
            if not block["ok"] or not isinstance(block["payload"], dict):
                stats["failed_urls"].append(url)
                continue
            for p in block["payload"].get("post_stream", {}).get("posts", []):
                posts.setdefault(p["id"], p)
                responses.setdefault(p["id"], block)
        needed.update(i for i in wanted if i in posts)
        gaps = [i for i in wanted if i not in posts]
        if gaps:
            stats["stream_gaps"][str(topic_id)] = gaps
        if index % 10 == 0:
            print(f"Make context {index + 1}/{len(topic_ids)} topics", flush=True)
    # Topic retrieval can reveal additional in-window posts omitted by the feed.
    original_selected = set(selected)
    selected.update(i for i in needed if in_window(posts[i].get("created_at"), start, end))
    stats["in_window_discovered_via_context"] = sorted(selected - original_selected)
    sample_topics = {posts[i]["topic_id"] for i in selected}
    needed = {i for i in needed if posts[i]["topic_id"] in sample_topics}
    lookup = {(p["topic_id"], p["post_number"]): i for i, p in posts.items()}
    records = []
    for i in sorted(needed):
        p = posts[i]
        topic_id = p["topic_id"]
        topic = topics.get(topic_id, {})
        number = p["post_number"]
        reply_number = p.get("reply_to_post_number")
        parent_number = (reply_number or 1) if number != 1 else None
        parent = lookup.get((topic_id, parent_number)) if parent_number else None
        dt = parse_time(p.get("created_at"))
        records.append({"source": "make", "native_id": str(i),
            "item_type": "topic" if number == 1 else "system" if p.get("post_type") == 3 else "reply",
            "native_post_type": p.get("post_type"), "author": p.get("username"),
            "created_at": dt.isoformat() if dt else None,
            "title": p.get("topic_title") or topic.get("title"),
            "text": plain(p.get("cooked")), "body_html": p.get("cooked"), "body_raw": p.get("raw"),
            "url": f"{MAKE}/t/{topic_id}/{number}", "parent_id": str(parent) if parent else None,
            "thread_id": str(topic_id), "post_number": number,
            "reply_to_post_number": reply_number,
            "parent_ref": f"{MAKE}/t/{topic_id}/{parent_number}" if parent_number else None,
            "parent_relation": "explicit_reply" if reply_number else "topic" if number != 1 else None,
            "category_id": p.get("category_id", topic.get("category_id")),
            "tags": topic.get("tags"), "scope": "sample" if i in selected else "context",
            "retrieved_at": responses[i]["retrieved_at"],
            "response_ref": responses[i]["response_ref"], "source_native": p})
    stats["candidate_topics_fetched"] = len(topic_ids)
    stats["participating_topics"] = len(sample_topics)
    stats["unresolved_parent_sample_ids"] = [r["native_id"] for r in records
        if r["scope"] == "sample" and r["post_number"] != 1 and not r["parent_id"]]
    categories = client.fetch(MAKE + "/categories.json")
    stats["categories_response_ref"] = categories["response_ref"]
    if not categories["ok"]:
        stats["failed_urls"].append(categories["url"])
    return [r for r in records if r["scope"] == "sample"], [r for r in records if r["scope"] == "context"], stats


def chronological(records):
    unique = {(r["source"], r["native_id"]): r for r in records}
    return sorted(unique.values(), key=lambda r: (r["created_at"] or "", r["source"], int(r["native_id"])))


def summary(records):
    dates = [r["created_at"] for r in records if r["created_at"]]
    return {"items": len(records), "types": dict(Counter(r["item_type"] for r in records)),
            "with_text": sum(bool(r["text"].strip()) for r in records),
            "text_characters": sum(len(r["text"]) for r in records),
            "text_utf8_bytes": sum(len(r["text"].encode()) for r in records),
            "earliest_creation": min(dates) if dates else None,
            "latest_creation": max(dates) if dates else None,
            "deleted": sum(bool(r["source_native"].get("deleted") or r["source_native"].get("deleted_at")) for r in records),
            "dead": sum(bool(r["source_native"].get("dead")) for r in records),
            "categories": dict(Counter(str(r["category_id"]) for r in records if "category_id" in r)),
            "hourly": dict(sorted(Counter(r["created_at"][:13] for r in records if r["created_at"]).items()))}


def export(root, results, manifest):
    sample, context = [], []
    report = {"window": manifest["window"], "reported_at": stamp(), "sources": {}}
    for source, (s, c, coverage) in results.items():
        sample.extend(s)
        context.extend(c)
        report["sources"][source] = {"sample": summary(s), "context": summary(c), "coverage": coverage}
        traversal_ok = coverage.get("stop_reason") in {"guard_boundary_reached", "feed_exhausted"}
        if source == "make":
            traversal_ok = traversal_ok and coverage.get("activity_stop_reason") in {"guard_boundary_reached", "feed_exhausted"}
        failed = coverage.get("failed_ids") or coverage.get("failed_urls")
        coverage["enumeration_status"] = "traversed_with_documented_limits" if traversal_ok and not failed else "partial"
    for name, records in [("sample", sample), ("context", context)]:
        path = root / (name + ".jsonl")
        tmp = path.with_suffix(".tmp")
        with tmp.open("w") as f:
            for record in chronological(records):
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        tmp.replace(path)
    report["limitations"] = [
        "Live snapshots, not immutable historical versions; edits/deletions can occur during retrieval.",
        "Guarded ID traversal is evidence of coverage, not proof against arbitrarily backdated/imported items.",
        "HN null or timestampless IDs cannot be assigned to the interval with confidence; see raw archive.",
        "Make feed omits some posts visible in public topics; recent-activity topic enumeration supplements it. Inaccessible content remains unavailable.",
        "HN context is ancestor-only, not all siblings; Make context includes participating topic streams up to the cap.",
        "HTTP failures, pagination caps, stream gaps and unresolved relationships remain explicit in coverage.",
        "Plain text is derived from HTML; raw bodies/native payloads remain available for alternate parsing."]
    report["artifacts"] = {}
    for name in ["sample.jsonl", "context.jsonl"]:
        data = (root / name).read_bytes()
        report["artifacts"][name] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    write_json(root / "report.json", report)
    lines = ["# Acquisition report", "", f"Window: {manifest['window']['start']} ≤ creation < {manifest['window']['end']}",
             "", "| Source | Sample | Types | With text | Text chars | Context | Stop |",
             "| --- | ---: | --- | ---: | ---: | ---: | --- |"]
    for source, info in report["sources"].items():
        s = info["sample"]
        lines.append(f"| {source} | {s['items']} | {s['types']} | {s['with_text']} | {s['text_characters']} | "
                     f"{info['context']['items']} | {info['coverage']['stop_reason']} |")
    lines += ["", "Detailed failures, gaps, counts, hourly volume and artifact hashes: `report.json`.", "",
              "## Limits", ""] + ["- " + x for x in report["limitations"]]
    (root / "report.md").write_text("\n".join(lines) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--end", help="Timezone-aware ISO timestamp; default latest completed UTC hour")
    parser.add_argument("--hours", type=float, default=24)
    parser.add_argument("--source", choices=["both", "hacker_news", "make"], default="both")
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--hn-rps", type=float, default=40)
    parser.add_argument("--make-rps", type=float, default=1)
    parser.add_argument("--max-hn-ids", type=int, default=60000)
    args = parser.parse_args()
    if min(args.hours, args.workers, args.hn_rps, args.make_rps, args.max_hn_ids) <= 0:
        parser.error("Limits must be positive")
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=True)
    # One run per directory; avoid concurrent cache/export writers.
    import fcntl
    lock = (root / ".run.lock").open("a")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        parser.error("Output directory is in use")
    path = root / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text())
        start, end = (parse_time(manifest["window"][x]) for x in ["start", "end"])
        if args.end and parse_time(args.end) != end:
            parser.error("Existing run has a different window; choose a new output directory")
        if (end - start).total_seconds() != args.hours * 3600:
            parser.error("Existing run has a different duration")
    else:
        end = parse_time(args.end) if args.end else datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        if end is None:
            parser.error("--end must include a timezone")
        start = end - timedelta(hours=args.hours)
        manifest = {"schema_version": 1, "created_at": stamp(),
                    "window": {"start": start.isoformat(), "end": end.isoformat(), "inclusion": "start <= created_at < end"},
                    "selection": "source enumeration and creation time only; no topical filters"}
        write_json(path, manifest)
    manifest.setdefault("invocations", []).append({
        "started_at": stamp(), "source": args.source, "workers": args.workers,
        "hn_rps": args.hn_rps, "make_rps": args.make_rps, "max_hn_ids": args.max_hn_ids,
        "collector_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    write_json(path, manifest)
    results = {}
    for source in ["make", "hacker_news"]:
        saved = root / (source + ".result.json")
        if args.source in {"both", source}:
            print(f"Collecting {source}: {start.isoformat()} to {end.isoformat()}", flush=True)
            client = Client(root, source, args.make_rps if source == "make" else args.hn_rps)
            value = make_collect(client, start, end) if source == "make" else hn_collect(
                client, start, end, args.workers, args.max_hn_ids)
            write_json(saved, value)
        if saved.exists():
            results[source] = json.loads(saved.read_text())
        export(root, results, manifest)
    manifest["last_finished_at"] = stamp()
    write_json(path, manifest)
    print(f"Report: {root / 'report.md'}", flush=True)


if __name__ == "__main__":
    main()
