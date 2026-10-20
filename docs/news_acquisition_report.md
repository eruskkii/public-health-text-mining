# News acquisition report

## Acquisition specification

- Query: `vaccine OR vaccination OR immunization OR immunisation`
- Collection: United States - National (`34412234`)
- Period: 2020-01-01 through 2025-12-31, inclusive
- Acquisition method: Media Cloud CSV exports supplied by the researcher; public article pages fetched with robots.txt checks, a per-domain delay, timeouts, and exponential-backoff retries.
- Sampling: fixed seed `20202025`, year-stratified, publisher-diversified sample.

## Results

- Candidate URLs selected: 3,000
- URLs with an HTTP response: 2,437
- Pages successfully fetched (HTTP 2xx): 1,859
- Successful qualifying extractions before text deduplication: 1,350
- Duplicate extracted bodies removed: 4
- Usable unique English vaccine articles: 1,346
- Extraction success rate: 44.9% of selected candidate URLs
- Usable date range: 2020-01-31 to 2025-12-31
- Median article length: 822 words

## Rejections and failures

- too_short_under_300_words: 389
- access_restricted_http_403: 304
- request_error_SSLError: 231
- http_404: 161
- request_error_ConnectionError: 157
- robots_disallowed: 122
- retryable_http_429: 109
- irrelevant_no_vaccine_term_in_body: 62
- empty_extraction: 58
- robots_http_403: 31
- timeout: 22
- retryable_http_503: 2
- http_410: 1
- robots_http_401: 1

## Annual distribution

- 2020: 166
- 2021: 178
- 2022: 219
- 2023: 241
- 2024: 261
- 2025: 281

## Publisher distribution (top 25)

- theguardian.com: 68
- seattletimes.com: 60
- newsweek.com: 52
- foxnews.com: 45
- cnn.com: 38
- latimes.com: 38
- nypost.com: 37
- theconversation.com: 34
- huffpost.com: 33
- sun-sentinel.com: 31
- cnbc.com: 31
- businessinsider.com: 30
- chicagotribune.com: 29
- mercurynews.com: 29
- cbsnews.com: 28
- nbcnews.com: 28
- newsday.com: 27
- sandiegouniontribune.com: 27
- breitbart.com: 26
- baltimoresun.com: 25
- dailykos.com: 24
- npr.org: 21
- azcentral.com: 20
- denverpost.com: 20
- usatoday.com: 20

## Input exports

- `mc-onlinenews-mediacloud-20261020103943-content.csv`: 172,203 rows, 2020-01-01 to 2020-12-31
- `mc-onlinenews-mediacloud-20261020104806-content.csv`: 170,336 rows, 2021-01-01 to 2021-06-30
- `mc-onlinenews-mediacloud-20261020105053-content.csv`: 138,243 rows, 2021-07-01 to 2021-12-31
- `mc-onlinenews-mediacloud-20261020105319-content.csv`: 82,356 rows, 2022-01-01 to 2022-12-31
- `mc-onlinenews-mediacloud-20261020105443-content.csv`: 27,870 rows, 2023-01-01 to 2023-12-31
- `mc-onlinenews-mediacloud-20261020105513-content.csv`: 19,266 rows, 2024-01-01 to 2024-12-31
- `mc-onlinenews-mediacloud-20261020105534-content.csv`: 31,400 rows, 2025-01-01 to 2025-12-31

## Known biases and limitations

- This is a reproducible stratified sample, not a census. Years are equally sampled even though Media Cloud contains many more matching records in 2020–2022.
- Media Cloud coverage depends on its source list, feed/indexing success, and the United States – National collection definition.
- Publisher availability is non-random: deleted pages, changed URLs, robots exclusions, paywalls, authentication, anti-bot systems, and JavaScript-only rendering reduce extraction success.
- No paywalls, CAPTCHAs, authentication, or access controls were bypassed.
- English and relevance filters can make classification errors. Relevance requires a vaccine-related term in the extracted body; headlines/snippets are never substituted for article text.
- Syndicated wire stories may remain when their extracted text differs enough to have a different exact SHA-256 hash.

## Reproduction

From the project root, place Media Cloud exports under `data/raw/News/media cloud/`, then run:

```powershell
python -m pip install --target R/news_acquisition/.vendor -r R/news_acquisition/requirements.txt
python R/news_acquisition/run_pipeline.py --candidates-per-year 500 --workers 8
```

The checkpoint at `data/raw/mediacloud/fetch_checkpoint.csv` makes interrupted runs resumable. Delete it only when intentionally starting a new acquisition run.
