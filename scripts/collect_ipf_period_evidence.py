"""Preserve primary IPF period rules and publication context for annual tables."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

DOCUMENTS = {
    "rules-2019.pdf": "https://www.ipf.si/media/110436/pravila-o-delitvi-nadomestil-izvajalcev-z-dne-23-8-2019.pdf",
    "rules-2017.pdf": "https://www.ipf.si/media/1516/20171022-pravilnik-o-delitvi-nadomestil-izvajalcev.pdf",
    "rules-2020.pdf": "https://www.ipf.si/media/110689/pravila-o-delitvi-nadomestil-izvajalcev-z-dne-25-8-2020.pdf",
    "rules-2021.pdf": "https://www.ipf.si/media/110779/pravila-o-delitvi-nadomestil-izvajalcev-z-dne-15072021.pdf",
    "rules-2022.pdf": "https://www.ipf.si/media/110916/pravila-o-delitvi-nadomestil-izvajalcev-07122022.pdf",
    "rules-2023.pdf": "https://www.ipf.si/media/111161/pravila-o-delitvi-nadomestil-imetnikov-pravic-izvajalcev-na-fonogramih-230828.pdf",
    "rules-index.html": "https://www.ipf.si/ipf-ko/temeljni-akti-in-pravila-ipf-ko-zakonodaja/",
    "statistics-2019.html": "https://ipf.si/ste-ustvarjalec/statistika/najbolj-predvajani-izvajalci-in-izvedbe/?y=2019",
    "publication-2025.html": "https://www.ipf.si/ipf-ko/novice/arhiv-novic/2026/zan-sercic-nina-puslar-in-mrfy-na-vrhu-lestvice-ipf-najveckrat-predvajanih-skladb-in-videospotov-v-letu-2025/",
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collect(output):
    output.mkdir(parents=True, exist_ok=False)
    captures, findings = [], []
    with requests.Session() as client:
        for name, url in DOCUMENTS.items():
            response = client.get(url, timeout=40)
            response.raise_for_status()
            path = output / name
            path.write_bytes(response.content)
            captures.append(
                dict(
                    path=name,
                    url=response.url,
                    sha256=sha(path),
                    obtained_at=datetime.now(UTC).isoformat(),
                )
            )
            if name.endswith(".pdf"):
                reader = PdfReader(path)
                texts = [page.extract_text() for page in reader.pages]
                (output / (name + ".txt")).write_text("\n\f\n".join(texts), encoding="utf8")
                pages = [i for i, text in enumerate(texts) if "koledarsko leto" in text]
                render_pages = pages or sorted({0, min(1, len(texts) - 1), len(texts) - 1})
                pdf = pypdfium2.PdfDocument(str(path))
                for index in render_pages:
                    page = pdf[index]
                    page.render(scale=1.4).to_pil().save(output / f"{name}-page-{index + 1}.png")
                    page.close()
                pdf.close()
                findings.append(
                    dict(
                        document=name,
                        period_definition_pages=[i + 1 for i in pages],
                        pdf_pages=len(texts),
                        requires_visual_period_review=not pages,
                        rendered_pages=[i + 1 for i in render_pages],
                    )
                )
            else:
                (output / (name + ".txt")).write_text(
                    BeautifulSoup(response.content, "html.parser").get_text("\n", strip=True),
                    encoding="utf8",
                )
    result = dict(
        version="ipf-primary-period-evidence-v1",
        captures=captures,
        findings=findings,
        scientific_approval=False,
        source_scope="IPF national performance statistics",
        implementation_sha256=sha(Path(__file__)),
        output_hashes={p.name: sha(p) for p in output.iterdir() if p.is_file()},
    )
    (output / "manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(json.dumps(findings))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    collect(args.output)
