"""
Build the evaluation index with the application's own ingestion code (the baseline
representation: no enrichment).

    python -m eval.build_index

Documents: the four NIST PDFs, domain "technical", chunked by rag.ingestion.pdf_loader.
Vehicles:  the EPA snapshot, domain "vehicles", one document per row by rag.ingestion.csv_loader.
The index is written to eval/work/chroma, separate from the application's own storage.
"""

import json
import shutil
import time

from eval import fetch_data, sources
from rag import config
from rag.ingestion.csv_loader import load_csv_as_documents
from rag.ingestion.pdf_loader import load_pdfs_from_directory
from rag.retrieval.vector_store import get_chroma_client, index_documents

INDEX_DIR = sources.WORK_DIR / "chroma"


def main() -> None:
    if not fetch_data.verify():
        raise SystemExit("Data files do not match their pinned checksums. Run: python -m eval.fetch_data nist")
    if INDEX_DIR.exists():
        shutil.rmtree(INDEX_DIR)
    INDEX_DIR.mkdir(parents=True)

    started = time.time()
    pdf_chunks = load_pdfs_from_directory(str(sources.NIST_DIR), domain="technical")
    vehicle_docs = load_csv_as_documents(str(sources.EPA_SNAPSHOT), domain="vehicles")
    client = get_chroma_client(INDEX_DIR)
    collection = client.create_collection(config.COLLECTION_NAME)
    index_documents(collection, pdf_chunks + vehicle_docs)

    info = {
        "pdf_chunks": len(pdf_chunks),
        "vehicle_documents": len(vehicle_docs),
        "total": collection.count(),
        "seconds": round(time.time() - started, 1),
        "vehicle_text_example": vehicle_docs[0].page_content,
        "vehicle_metadata_keys_example": sorted(vehicle_docs[0].metadata.keys()),
    }
    (sources.WORK_DIR / "index_info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps({k: v for k, v in info.items() if not k.startswith("vehicle_text")}, indent=2))


if __name__ == "__main__":
    main()
