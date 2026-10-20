# Media Cloud vaccine-news acquisition

This directory contains the reproducible acquisition pipeline for the Media
Cloud vaccine-news corpus. It does not use or modify the Reddit/Twitter data.

The pipeline reads Media Cloud CSV exports, draws a fixed-seed sample balanced
across years, checks `robots.txt`, fetches public article pages, extracts article
bodies, validates English language and vaccine relevance, deduplicates URLs and
body text, writes a resumable checkpoint, and produces the requested Parquet
file and report.

From the RStudio project root:

```powershell
python -m pip install --target R/news_acquisition/.vendor -r R/news_acquisition/requirements.txt
python R/news_acquisition/run_pipeline.py --candidates-per-year 500 --workers 8
```

The script accepts `--input-dir` if exports are stored elsewhere. Its default
search includes the supplied `data/raw/News/media cloud` folder. Runtime files
are stored under the already Git-ignored `data/raw/mediacloud/` directory.

