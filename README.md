# S1SuperTimeline

A command line tool that creates a super timeline from SentinelOne's Deep Visibility data

## What does it do?

The script accepts a S1QL query and returns a XLSX, CSV, or JSON document with deep visibility data. This method
automates downloading
datasets that are
over 20K records (Deep Visibility's limit). For example, a hosts entire deep visibility history could be downloaded
using
this script.

## How to run it

### Install dependencies

```commandline
pip install -r requirements.txt
```

### Run

```commandline
# Hour Increments
python3 s1_supertimeline.py -t my_api_token -url sentinelone.com -from 2020-01-01T00:00 -to 2020-01-01T12:30 -hr
```

## Help Page

```commandline
python3 s1_supertimeline.py -h
```

```commandline
usage: s1_supertimeline.py [-h] -t S1_API_TOKEN -url S1_URL -from FROM_DATE -to TO_DATE [-u] [-aid ACCOUNT_IDS] (-s | -m | -hr | -d)

SentinelOne SuperTimeline | Deep Viz Downloader | 2.0

options:
  -h, --help            show this help message and exit
  -s, --seconds         Breakup queries by seconds (slow but most likely to return full data)
  -m, --minutes         Breakup queries by minutes
  -hr, --hours          Breakup queries by hours
  -d, --days            Breakup queries by days

Required Arguments:
  -t S1_API_TOKEN, --s1_api_token S1_API_TOKEN
                        SentinelOne API Token
  -url S1_URL, --s1_url S1_URL
                        SentinelOne Console Url
  -from FROM_DATE, --from_date FROM_DATE
                        From Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD
  -to TO_DATE, --to_date TO_DATE
                        To Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD
  -u, --utc             Accepts --date_from/--date_to as UTC, Default is local time
  -aid ACCOUNT_IDS, --account_ids ACCOUNT_IDS
                        Account ID filter for deep visibility. This will limit search scope to a specific account. Accepts multiple accountids. Input multiple ids with comma seperator

```
