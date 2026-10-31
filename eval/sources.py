"""Pinned sources for the evaluation data. See eval/SOURCES.md for licenses."""

from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DATA_DIR = EVAL_DIR / "data"
NIST_DIR = DATA_DIR / "nist"
RESULTS_DIR = EVAL_DIR / "results"
WORK_DIR = EVAL_DIR / "work"

NIST_BASE_URL = "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/"

# file name -> SHA-256 of the PDF downloaded on 2026-10-31
NIST_FILES = {
    "NIST.SP.800-40r4.pdf": "351f4a828d6c0bc8bf98f25ba3f87ec5add0ed8cf8bb4a6e6cb4e7e4a9731833",
    "NIST.SP.800-61r3.pdf": "e5593d6bb85daecec7e8d9549400c7b3473bcc3f06e469c82218073afa7fba2d",
    "NIST.SP.800-63B-4.pdf": "d9ab89576b5ae2cfb3ba37781110788dea27a85a5079496dbfc1a79834670afd",
    "NIST.SP.800-88r2.pdf": "39bb805c72723ed74f08e5806cd8463ca2554a62abb4f97b9d19c0398a8a7c55",
}

EPA_ZIP_URL = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip"
# SHA-256 of the zip the snapshot was made from (server Last-Modified: 2026-09-29 19:47 GMT)
EPA_ZIP_SHA256 = "33d32caa0343cdb11c47be631e8a80b7ed7c351ee8503646a4e96485bd67b22f"
EPA_YEARS = ("2023", "2024")
EPA_SNAPSHOT = DATA_DIR / "epa_vehicles_2023_2024.csv"
# SHA-256 of the committed snapshot; checked by `python -m eval.fetch_data verify`
EPA_SNAPSHOT_SHA256 = "7b1a79543f1c6cc0b6e34fe5909af8457aef15d7cb9335f5d5400ce742feb910"
