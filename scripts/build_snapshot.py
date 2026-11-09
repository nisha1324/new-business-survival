"""Build the tidy snapshot in data/ from the raw ABS workbooks in data/raw/.

Writes four gzipped CSVs (gzip timestamp fixed at 0, so a rebuild from the
same workbooks is byte-identical) and data/SNAPSHOT.json with the SHA-256 of
every input and output file.
"""
from pathlib import Path
import gzip
import hashlib
import io
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cabee import load  # noqa: E402
from scripts.download_data import FILES, url_for  # noqa: E402


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_csv_gz(df, path: Path) -> str:
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0) as gz:
        gz.write(df.to_csv(index=False, lineterminator="\n").encode("utf-8"))
    path.write_bytes(buf.getvalue())
    return sha256_bytes(buf.getvalue())


def main() -> int:
    missing = [n for n in FILES if not (load.RAW / n).exists()]
    if missing:
        print("missing raw files, run scripts/download_data.py first:", ", ".join(missing))
        return 1
    meta = {
        "source": "Australian Bureau of Statistics, Counts of Australian Businesses, including Entries and Exits (cat. no. 8165.0)",
        "licence": "CC BY 4.0, (c) Commonwealth of Australia",
        "inputs": {n: {"sha256": FILES[n][0], "url": url_for(n)} for n in FILES},
        "outputs": {},
    }
    for name, fn in load.TABLES.items():
        df = fn()
        out = load.DATA / f"{name}.csv.gz"
        digest = write_csv_gz(df, out)
        meta["outputs"][out.name] = {"rows": len(df), "columns": list(df.columns), "sha256": digest}
        print(f"{out.name}: {len(df):,} rows, {out.stat().st_size:,} bytes")
    (load.DATA / "SNAPSHOT.json").write_text(json.dumps(meta, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
