"""
Download and verify the evaluation data.

    python -m eval.fetch_data nist           download the NIST PDFs, verify SHA-256
    python -m eval.fetch_data verify         verify the NIST PDFs and the EPA snapshot
    python -m eval.fetch_data epa-snapshot   rebuild the EPA snapshot from the live EPA file

The EPA snapshot is committed, so `epa-snapshot` is only needed to check where it came from.
The live EPA file changes about weekly, so a rebuild can differ from the committed snapshot.
"""

import csv
import hashlib
import io
import sys
import urllib.request
import zipfile

from eval import sources

USER_AGENT = "multi-domain-rag-eval/0.1"


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def fetch_nist() -> bool:
    sources.NIST_DIR.mkdir(parents=True, exist_ok=True)
    ok = True
    for name, expected in sources.NIST_FILES.items():
        path = sources.NIST_DIR / name
        if not path.exists() or sha256_of(path) != expected:
            print(f"downloading {name}")
            path.write_bytes(download(sources.NIST_BASE_URL + name))
        actual = sha256_of(path)
        status = "ok" if actual == expected else f"MISMATCH (got {actual})"
        print(f"{name}: {status}")
        ok = ok and actual == expected
    return ok


def verify() -> bool:
    ok = True
    for name, expected in sources.NIST_FILES.items():
        path = sources.NIST_DIR / name
        actual = sha256_of(path) if path.exists() else "missing"
        print(f"{name}: {'ok' if actual == expected else actual}")
        ok = ok and actual == expected
    if sources.EPA_SNAPSHOT_SHA256:
        actual = sha256_of(sources.EPA_SNAPSHOT)
        print(f"{sources.EPA_SNAPSHOT.name}: {'ok' if actual == sources.EPA_SNAPSHOT_SHA256 else actual}")
        ok = ok and actual == sources.EPA_SNAPSHOT_SHA256
    return ok


def make_epa_snapshot() -> None:
    data = download(sources.EPA_ZIP_URL)
    print("EPA zip SHA-256:", hashlib.sha256(data).hexdigest(), f"({len(data)} bytes)")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        text = archive.read("vehicles.csv").decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    year = header.index("year")
    sources.DATA_DIR.mkdir(parents=True, exist_ok=True)
    kept = 0
    with open(sources.EPA_SNAPSHOT, "w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)
        for row in reader:
            if row[year] in sources.EPA_YEARS:
                writer.writerow(row)
                kept += 1
    print(f"wrote {kept} rows to {sources.EPA_SNAPSHOT}")
    print("snapshot SHA-256:", sha256_of(sources.EPA_SNAPSHOT))


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "nist":
        return 0 if fetch_nist() else 1
    if command == "verify":
        return 0 if verify() else 1
    if command == "epa-snapshot":
        make_epa_snapshot()
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
