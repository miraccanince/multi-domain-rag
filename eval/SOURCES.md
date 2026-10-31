# Evaluation data sources

Checked on 2026-10-31. License statements are quoted from the pages named below; they are
not legal advice. Re-check them before redistributing anything.

## Technical documents: four NIST Special Publications

| File | Download URL | SHA-256 (of the PDF as downloaded) |
|------|--------------|------------------------------------|
| NIST.SP.800-40r4.pdf | https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-40r4.pdf | 351f4a828d6c0bc8bf98f25ba3f87ec5add0ed8cf8bb4a6e6cb4e7e4a9731833 |
| NIST.SP.800-61r3.pdf | https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-61r3.pdf | e5593d6bb85daecec7e8d9549400c7b3473bcc3f06e469c82218073afa7fba2d |
| NIST.SP.800-63B-4.pdf | https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63B-4.pdf | d9ab89576b5ae2cfb3ba37781110788dea27a85a5079496dbfc1a79834670afd |
| NIST.SP.800-88r2.pdf | https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-88r2.pdf | 39bb805c72723ed74f08e5806cd8463ca2554a62abb4f97b9d19c0398a8a7c55 |

Titles: SP 800-40r4 Guide to Enterprise Patch Management Planning; SP 800-61r3 Incident Response
Recommendations and Considerations for Cybersecurity Risk Management; SP 800-63B-4 Digital Identity
Guidelines, Authentication and Authenticator Management; SP 800-88r2 Guidelines for Media Sanitization.
Together: 253 PDF pages, about 3.6 MB.

License: https://www.nist.gov/open/license states "Works authored by NIST employees are not subject to
Copyright protection within the United States." Foreign rights are reserved. Attribution is requested
("Republished courtesy of the National Institute of Standards and Technology"). The page also warns that
"some works published by NIST may have been written by third parties and may be subject to copyright
protection". SP 800-61r3 says on its own page 3: "This publication may be used by nongovernmental
organizations on a voluntary basis and is not subject to copyright in the United States. Attribution
would, however, be appreciated by NIST."

Redistribution decision: the PDFs are not committed. `python -m eval.fetch_data nist` downloads them and
checks the SHA-256 values above. `questions.jsonl` quotes short verbatim spans from them as gold evidence.

## Product records: EPA fuel economy vehicle data

| Item | Value |
|------|-------|
| Source page | https://www.fueleconomy.gov/feg/ws/index.shtml (section "Download the Vehicle Data") |
| Download URL | https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip |
| Zip as downloaded | 2,212,193 bytes, server Last-Modified 2026-09-29 19:47 GMT |
| Zip SHA-256 | 33d32caa0343cdb11c47be631e8a80b7ed7c351ee8503646a4e96485bd67b22f |
| Full file | 50,407 vehicles (model years 1984 to 2027), 84 columns |
| Snapshot | `eval/data/epa_vehicles_2023_2024.csv`: the rows with year 2023 or 2024, all 84 columns, original order, 2,607 rows (1,330 for 2023 and 1,277 for 2024) |
| Snapshot SHA-256 | 7b1a79543f1c6cc0b6e34fe5909af8457aef15d7cb9335f5d5400ce742feb910 |

The snapshot was produced by `python -m eval.fetch_data epa-snapshot`. The live file is updated about
weekly, so a rebuild can differ from the committed snapshot. The committed snapshot is the version used
for all results.

License: the data.gov record for this dataset (https://catalog.data.gov/dataset/www-fueleconomy-gov) points
to the EPA Data License, https://edg.epa.gov/EPA_Data_License.htm: "Unless otherwise specified, all data
produced by the U.S EPA is by default in the public domain." The same page says "no warranty expressed or
implied is made regarding the accuracy or utility of the data." Caveats: the fueleconomy.gov download page
itself states no license, and the site is administered by Oak Ridge National Laboratory for the Department
of Energy and the EPA, so the public domain status rests on the EPA data license and the data.gov record.

Redistribution decision: the snapshot is committed (public domain under the EPA data license, 1.1 MB).
Attribution: U.S. Environmental Protection Agency and U.S. Department of Energy, fueleconomy.gov.

## Sources considered and not used

* Open Food Facts: product descriptions are richer, but the database is under ODbL (attribution and
  share-alike, so a committed subset would carry those terms). Its search API returned "temporarily
  unavailable" when tried, and the bulk export is large.
* FAA aviation handbooks: about 100 MB per PDF, and no license statement could be retrieved automatically.
