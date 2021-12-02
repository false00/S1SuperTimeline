# S1SuperTimeline
A command line tool that creates a super timeline from SentinelOne's Deep Visibility data

## What does it do?
The script accepts a S1QL query and returns a XLSX document with all the data. The script has mulithreading capabilities
and allows the user to break up queries by minute increments. This method automates downloading datasets that are
over 20K records (Deep Visibility's limit). For example, a hosts entire deep visbility history could be downloaded using
this script. Assuming you do not go over 1,048,576 records (xlsx limit). 

## How to run it
### Install dependencies
```commandline
pip install -r requirements.txt
```
### Run
```commandline
# Hour Increments (60 min)
python3 s1_supertimeline.py -t my_api_token -url sentinelone.com -from 2020-01-01T00:00 -to 2020-01-01T12:30 -min 60
```

## Help Page
```commandline
python3 s1_supertimeline.py -h
```
```commandline
usage: s1_supertimeline.py [-h] -t S1_API_TOKEN -url S1_URL -from FROM_DATE -to TO_DATE -min MIN_INCREMENTS [-u]

SentinelOne SuperTimeline :: By Juan Ortega <falseflag00@protonmail.com>

options:
  -h, --help            show this help message and exit

Required Arguments:
  -t S1_API_TOKEN, --s1_api_token S1_API_TOKEN
                        SentinelOne API Token
  -url S1_URL, --s1_url S1_URL
                        SentinelOne Console Url
  -from FROM_DATE, --from_date FROM_DATE
                        From Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD
  -to TO_DATE, --to_date TO_DATE
                        To Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD
  -min MIN_INCREMENTS, --min_increments MIN_INCREMENTS
                        Minute increments to split time date range by
  -u, --utc             Accepts --date_from/--date_to as UTC, Default is local time

```
## Troubleshooting 
If you have issues running the script. Try installing tablib like this:
```commandline
pip install "tablib['xlsx']"
```