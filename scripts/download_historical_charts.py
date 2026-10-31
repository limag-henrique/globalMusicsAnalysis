"""Download public, version-pinned chart archives with resumable local checkpoints."""

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/raw/historical_backfill/20261030"


def download_ranges(client, url, part, size):
    """Four bounded streams; resume each completed range without repeating bytes."""
    offset = part.stat().st_size if part.exists() else 0
    chunks = [(start, min(start + 64 * 1024**2, size) - 1)
              for start in range(offset, size, 64 * 1024**2)]

    def acquire(bounds):
        start, end = bounds
        target = part.with_name(f"{part.name}.{start}-{end}")
        if target.exists() and target.stat().st_size == end - start + 1:
            return target
        for attempt in range(3):
            try:
                with client.stream("GET", url, headers={"Range": f"bytes={start}-{end}"}) as r:
                    r.raise_for_status()
                    if r.status_code != 206 or r.headers.get("content-range") != (
                            f"bytes {start}-{end}/{size}"):
                        raise ValueError("unexpected ranged response")
                    with target.open("wb") as handle:
                        for block in r.iter_bytes(1024 * 1024):
                            handle.write(block)
                if target.stat().st_size != end - start + 1:
                    raise ValueError("incomplete download range")
                print(json.dumps(dict(range_start=start, range_end=end,
                                      status="range_downloaded")), flush=True)
                return target
            except (httpx.HTTPError, ValueError):
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)

    with ThreadPoolExecutor(4) as pool, part.open("ab") as output:
        for target in pool.map(acquire, chunks):
            with target.open("rb") as handle:
                while block := handle.read(1024 * 1024):
                    output.write(block)
            output.flush()
            target.unlink()


def download(client, url, path, *, size=None, checksum=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    if path.exists():
        if size is not None and path.stat().st_size != size:
            raise ValueError(f"existing file has unexpected size: {path.name}")
        if checksum:
            with path.open("rb") as handle:
                if hashlib.file_digest(handle, "md5").hexdigest() != checksum:
                    raise ValueError(f"existing checksum mismatch: {path.name}")
        return
    if size and size > 1024**3:
        download_ranges(client, url, part, size)
        if part.stat().st_size != size:
            raise ValueError("incomplete ranged download")
        part.replace(path)
        with path.open("rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        path.with_suffix(path.suffix + ".sha256").write_text(digest + "\n")
        print(json.dumps(dict(file=path.name, status="downloaded", bytes=size)), flush=True)
        return
    for attempt in range(3):
        offset = part.stat().st_size if part.exists() else 0
        try:
            headers = {"Range": f"bytes={offset}-"} if offset else {}
            with client.stream("GET", url, headers=headers) as response:
                response.raise_for_status()
                if offset and response.status_code != 206:
                    raise ValueError("server did not honor resume range")
                with part.open("ab" if offset else "wb") as handle:
                    last_report = time.monotonic()
                    for block in response.iter_bytes(1024 * 1024):
                        handle.write(block)
                        if time.monotonic() - last_report >= 15:
                            print(json.dumps(dict(file=path.name, bytes=handle.tell(),
                                                  expected_bytes=size)), flush=True)
                            last_report = time.monotonic()
            if size is not None and part.stat().st_size != size:
                raise ValueError("incomplete archive size")
            if checksum:
                with part.open("rb") as handle:
                    if hashlib.file_digest(handle, "md5").hexdigest() != checksum:
                        raise ValueError("archive checksum mismatch")
            part.replace(path)
            with path.open("rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            path.with_suffix(path.suffix + ".sha256").write_text(digest + "\n")
            print(json.dumps(dict(file=path.name, status="downloaded",
                                  bytes=path.stat().st_size)), flush=True)
            return
        except (httpx.HTTPError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=("zenodo", "kaggle"), required=True)
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        if args.source == "zenodo":
            destination = args.output / "zenodo-23645386"
            response = client.get("https://zenodo.org/api/records/23645386")
            response.raise_for_status()
            record = response.json()
            destination.mkdir(parents=True, exist_ok=True)
            (destination / "record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
            files = [f for f in record["files"]
                     if "_positions_" in f["key"] or f["key"].startswith("raw_")
                     or f["key"] == "README.md"]

            def acquire(file):
                download(client, file["links"]["self"], destination / file["key"],
                         size=file["size"], checksum=file["checksum"].removeprefix("md5:"))

            with ThreadPoolExecutor(2) as pool:
                list(pool.map(acquire, files))
        else:
            ref = "gonzalopezgil/spotify-charts-daily-updated"
            # Freeze the inspected version even when the publisher updates overnight.
            version = 151
            destination = args.output / f"kaggle-gonzalopezgil-v{version}"
            destination.mkdir(parents=True, exist_ok=True)
            record_path = destination / "record.json"
            if not record_path.exists():
                response = client.get(f"https://www.kaggle.com/api/v1/datasets/view/{ref}")
                response.raise_for_status()
                record = response.json()
                if record["currentVersionNumber"] != version:
                    raise ValueError("Kaggle metadata changed; inspect the pinned version first")
                record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
            files = [{"name": "charts_songs_daily.csv", "totalBytes": 11_071_427_195}]
            for file in files:
                if file["name"] != "charts_songs_daily.csv":
                    continue
                url = (f"https://www.kaggle.com/api/v1/datasets/download/{ref}/{file['name']}"
                       f"?datasetVersionNumber={version}")
                download(client, url, destination / file["name"], size=file["totalBytes"])


if __name__ == "__main__":
    main()
