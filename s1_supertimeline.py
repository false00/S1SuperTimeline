# SentinelOne SuperTimeline
# Author: Juan Ortega <falseflag00@protonmail.com>
import hashlib
import tablib
import argparse
import re
import requests
import json
from dateutil.parser import parse
from dateutil import tz
from datetime import datetime, timedelta, timezone
import sys
import time
import concurrent.futures


def main(args):
    s1_api = SentinelOne(args.s1_url, args.s1_api_token)
    should_continue = s1_api.check_auth()

    if should_continue:
        deep_viz_query = input('S1 SuperTimeline:: Input Deep Visibility Query \n')

        super_timeline = SuperTimeline(args.s1_url, args.s1_api_token)
        super_timeline.sentinelone_deepviz(args.min_increments, deep_viz_query, args.from_date, args.to_date, args.utc)


class SuperTimeline:

    def __init__(self, console_url, api_token):
        self.console_url = console_url
        self.api_token = api_token

    # Create Datasets
    super_ts_data = tablib.Dataset(title="Super Timeline")
    process_data = tablib.Dataset(title="Process")
    netflow_data = tablib.Dataset(title="Netflow")
    file_data = tablib.Dataset(title="File")
    url_data = tablib.Dataset(title="URL")
    scheduled_data = tablib.Dataset(title="Scheduled Task")
    dns_data = tablib.Dataset(title="DNS")
    book = tablib.Databook(
        (super_ts_data, process_data, file_data, netflow_data, url_data, scheduled_data, dns_data))

    super_ts_data.headers = ['siteName', 'agentName', 'trueContext', 'eventType', 'date (UTC)', 'user', 'message',
                             'processName', 'pid']
    process_data.headers = ['siteName', 'agentName', 'trueContext', 'eventType', 'user', 'parentProcessStartTime',
                            'processStartTime', 'parentProcessName', 'parentPid', 'processName', 'pid',
                            'processCmd', 'fileMd5', 'processImageSha1Hash', 'fileSha256']
    file_data.headers = ['siteName', 'agentName', 'trueContext', 'eventType', 'user', 'createdAt', 'fileModifyAt',
                         'fileFullName', 'fileMd5', 'fileSha1', 'pid',
                         'processName', 'oldFileName', 'oldFileMd5', 'oldFileSha1']
    netflow_data.headers = ['siteName', 'agentName', 'trueContext', 'eventType', 'createdAt', 'connectionStatus',
                            'direction', 'srcIp', 'srcPort', 'dstIp', 'dstPort', 'user', 'processStartTime',
                            'processName', 'pid']
    url_data.headers = ['siteName', 'agentName', 'trueContext', 'eventType', 'createdAt', 'networkSource',
                        'networkUrl', 'user', 'processStartTime', 'processName', 'pid']
    scheduled_data.headers = ['siteName', 'agentName', 'trueContext', 'eventType', 'objectType', 'user',
                              'createdAt', 'taskName', 'taskPath', 'processStartTime',
                              'parentPid', 'processName', 'pid']
    dns_data.headers = ['siteName', 'agentName', 'trueContext', 'eventType', 'user', 'eventTime', 'dnsRequest',
                        'dnsResponse', 'srcProcParentStartTime', 'srcProcParentImagePath', 'parentPid',
                        'processStartTime', 'srcProcCmdLine', 'pid']

    def sentinelone_deepviz(self, minutes, query, time_from, time_to, utc):
        # Create time_period by x minutes, return time intervals
        # Convert time to query format
        time_tools = TimeTools()
        time_from = time_tools.time_convert(time_from, utc)
        time_to = time_tools.time_convert(time_to, utc)

        # Create tuples for time range
        dts = [dt.strftime('%Y-%m-%dT%H:%M') for dt in
               time_tools.datetime_range(datetime.strptime(time_from, '%Y-%m-%dT%H:%M:%S.%fZ'),
                                         datetime.strptime(time_to, '%Y-%m-%dT%H:%M:%S.%fZ'),
                                         timedelta(minutes=int(minutes)))]

        # Use zip() + list slicing to perform pair iteration in list, res contains timestamps in pairs
        res = list(zip(dts, dts[1:] + dts[:1]))

        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as executor:
            futures = []

            # Iterate through time ranges
            for _ in res:
                # Convert to tuple to list to allow data manipulation
                _ = list(_)
                if time_from[:16] in _[1]:
                    _[1] = time_to[:16]
                print(f'S1 SuperTimeline:: Starting Query for time range: {_[0]} to {_[1]}')
                futures.append(executor.submit(self.get_dv_data, query=query, date_from=_[0], date_to=_[1]))

            for future in concurrent.futures.as_completed(futures):
                future.result()

        # Export XLSX
        # Write databases to Excel document
        book = tablib.Databook((self.super_ts_data, self.process_data, self.file_data, self.netflow_data,
                                self.url_data, self.scheduled_data, self.dns_data))

        output_file = time_from.replace(' ', 'T').replace(':', '').replace('-', '') + '_' + \
                      time_to.replace(' ', 'T').replace(':', '').replace('-', '') + '_' + \
                      re.sub('[^A-Za-z0-9]+', '', query[:100])
        try:
            with open('S1SuperTimeline_' + output_file + '.xlsx', 'wb') as f:
                f.write(book.export('xlsx'))
            print(f"S1 SuperTimeline:: Writing combined data to S1SuperTimeline_{output_file}.xlsx'")

        except:
            print("S1 SuperTimeline:: Error saving as XLSX, saving output as CSV")
            with open(output_file + '_S1SuperTimeline_super_ts_data.csv', 'w', newline='') as f:
                f.write(self.super_ts_data.export('csv'))
            with open(output_file + '_S1SuperTimeline_process_data.csv', 'w', newline='') as f:
                f.write(self.process_data.export('csv'))
            with open(output_file + '_S1SuperTimeline_netflow_data.csv', 'w', newline='') as f:
                f.write(self.netflow_data.export('csv'))
            with open(output_file + '_S1SuperTimeline_file_data.csv', 'w', newline='') as f:
                f.write(self.file_data.export('csv'))
            with open(output_file + '_S1SuperTimeline_url_data.csv', 'w', newline='') as f:
                f.write(self.url_data.export('csv'))
            with open(output_file + '_S1SuperTimeline_scheduled_data.csv', 'w', newline='') as f:
                f.write(self.scheduled_data.export('csv'))
            with open(output_file + '_S1SuperTimeline_dns_data.csv', 'w', newline='') as f:
                f.write(self.dns_data.export('csv'))
            print(f"S1 SuperTimeline:: Writing files CSV files with prefix: {output_file}\n")

    def get_dv_data(self, query, date_from, date_to):
        s1_api = SentinelOne(self.console_url, self.api_token)
        query_id = s1_api.get_query_id(query, date_from, date_to)

        event_types = ['Process', 'File', 'IP', 'URL', 'scheduled_task', 'DNS']

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
            futures = []

            for event_type in event_types:
                futures.append(executor.submit(self.get_dv_by_event, event_type=event_type, query_id=query_id))

            for future in concurrent.futures.as_completed(futures):
                future.result()

    def get_dv_by_event(self, event_type, query_id):
        url = f"https://{self.console_url}/web/api/v2.1/dv/events/{event_type}?limit=1000&queryId={query_id}&" \
              f"apiToken={self.api_token}"

        response = requests.request("GET", url)
        output = response.json()

        print(f'S1 SuperTimeline:: Downloading {event_type} Data')

        for record in output['data']:
            self.add_to_dataset(event_type, record)

        # Estimate how long the script will take to run
        total_items = output['pagination']['totalItems']
        print("S1 SuperTimeline:: Record Count: " + str(total_items))
        total_run_time = (int(total_items) / 42) / 60
        print("S1 SuperTimeline:: Estimated Run Time: " + str(round(total_run_time) + 1) + " Minute(s)\n")

        # Create pagination variable to go to next page
        pagination = output['pagination']['nextCursor']

        while True:
            if pagination:
                url = f"https://{self.console_url}/web/api/v2.1/dv/events/{event_type}?limit=1000&queryId={query_id}&" \
                        f"apiToken={self.api_token}&cursor={pagination}"

                response = requests.request("GET", url)
                output = response.json()

                try:
                    pagination = output['pagination']['nextCursor']
                    # Print Remaining Pages
                    for record in output['data']:
                        self.add_to_dataset(event_type, record)
                except:
                    pagination = None
            else:
                break

    def add_to_dataset(self, event_type, record):
        if event_type == 'Process':
            self.process_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['user'],
                 record['parentProcessStartTime'], record['processStartTime'], record['parentProcessName'],
                 record['parentPid'], record['processName'], record['pid'],
                 record['processCmd'], record['fileMd5'], record['processImageSha1Hash'],
                 record['fileSha256']])
            self.super_ts_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['processStartTime'], record['user'], record['processCmd'], record['processName'],
                 record['pid']])

        if event_type == 'File':
            self.file_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['user'],
                 record['createdAt'], record['fileModifyAt'], record['fileFullName'], record['fileMd5'],
                 record['fileSha1'],
                 record['pid'], record['processName'], record['oldFileName'], record['oldFileMd5'],
                 record['oldFileSha1']])
            self.super_ts_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['createdAt'], record['user'],
                 record['fileFullName'], record['processName'], record['pid']])

        if event_type == 'IP':
            self.netflow_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['createdAt'],
                 record['connectionStatus'], record['direction'], record['srcIp'], record['srcPort'],
                 record['dstIp'],
                 record['dstPort'], record['user'], record['processStartTime'], record['processName'],
                 record['pid']
                 ])
            self.super_ts_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['createdAt'], record['user'],
                 (record['connectionStatus'], record['direction'], record['srcIp'], record['srcPort'],
                  record['dstIp'],
                  record['dstPort']), record['processName'], record['pid']])

        if event_type == 'URL':
            self.url_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['createdAt'],
                 record['networkSource'], record['networkUrl'], record['user'],
                 record['processStartTime'], record['processName'],
                 record['pid']
                 ])
            self.super_ts_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['createdAt'], record['user'],
                 (record['networkSource'], record['networkUrl']), record['processName'], record['pid']])

        if event_type == 'scheduled_task':
            self.scheduled_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['objectType'], record['user'], record['createdAt'],
                 record['taskName'], record['taskPath'],
                 record['processStartTime'], record['parentPid'], record['processName'], record['pid']
                 ])
            self.super_ts_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['createdAt'], record['user'],
                 (record['taskName'], record['taskPath']), record['processName'],
                 record['pid']])

        if event_type == 'DNS':
            self.dns_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['user'], record['eventTime'],
                 record['dnsRequest'], record['dnsResponse'],
                 record['srcProcParentStartTime'], record['srcProcParentImagePath'], record['parentPid'],
                 record['processStartTime'], record['srcProcCmdLine'], record['pid']
                 ])
            self.super_ts_data.append(
                [record['siteName'], record['agentName'], record['trueContext'], record['eventType'],
                 record['eventTime'], record['user'],
                 (record['dnsRequest'], record['dnsResponse']), record['processName'], record['pid']])


class SentinelOne:
    def __init__(self, console_url, api_token):
        self.console_url = console_url
        self.api_token = api_token

    def check_auth(self):

        status = False

        hashed_key = hashlib.sha384(self.api_token.encode()).hexdigest()

        current_time_utc = datetime.now(timezone.utc)

        try:
            url = f"https://{self.console_url}/web/api/v2.1/users/api-token-details?apiToken={self.api_token}"

            payload = '{"data":{"apiToken":"' + self.api_token + '"}}'
            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.request("POST", url, headers=headers, data=payload)

            binary = response.content
            output = json.loads(binary)

            created_date = output['data']['createdAt']
            expire_date = output['data']['expiresAt']

            try:
                expire_date = datetime.strptime(expire_date, '%Y-%m-%dT%H:%M:%S%z')
            except:
                expire_date = datetime.strptime(expire_date, '%Y-%m-%dT%H:%M:%S.%f%z')

            if current_time_utc >= expire_date:
                message = f"SentinelOneV21 | check_auth | Authentication Failed | Token Expired | " \
                          f"{self.api_token[:5]}:{hashed_key}"
                print(message)
            else:
                message = f"SentinelOneV21 | check_auth | Authenticated Successfully | {hashed_key} | " \
                          f"created_date = {created_date} | expire_date = {expire_date}"
                print(message)

                status = True

        except:
            message = f"SentinelOneV21 | check_auth | Authentication Failed | {hashed_key}"
            print(message)

        return status

    def get_query_id(self, query, time_from, time_to):
        # Escape special characters in json string
        query = query.replace('\\', '\\\\')
        query = query.replace('"', '\\"')

        url = f"https://{self.console_url}/web/api/v2.1/dv/init-query?apiToken={self.api_token}"

        payload = '{"fromDate":"' + time_from + '","limit":20000,"query":"' + query + '","toDate":"' + time_to + '"}'
        headers = {
            'Content-Type': 'application/json'
        }

        # Fix timeout issue
        output = False
        while True:
            try:
                response = requests.request("POST", url, headers=headers, data=payload)
                output = response.json()
            except:
                time.sleep(1)

            if output:
                try:
                    query_id = (output['data']['queryId'])
                    break
                except:
                    pass

        print('S1 SuperTimeline:: Query ID: ' + query_id)

        # Don't return until Query Completes
        while True:
            url = f"https://{self.console_url}/web/api/v2.1/dv/query-status?queryId={query_id}&apiToken={self.api_token}"

            response = requests.request("GET", url, headers=headers, data=payload)

            output = response.json()

            try:
                if output['data']['responseState'] == 'FINISHED':
                    break
                if output['data']['responseState'] != 'FINISHED':
                    print("S1 SuperTimeline:: INFO | Query Status: " + output['data']['responseState'] + " Progress: " + str(
                        output['data']['progressStatus']))
            except:
                print(
                    "S1 SuperTimeline:: ERROR | Query timed out. This should not happen. Please contact SentinelOne Support "
                    "<support@sentinelone.com>. Dumping raw error and exiting...\n")
                print(output)
                raise SystemExit

        # Check result count
        url = f"https://{self.console_url}/web/api/v2.1/dv/events?limit=1&queryId={query_id}&apiToken={self.api_token}"

        response = requests.request("GET", url)
        output = response.json()

        # Warn the user if the record size is near the limit
        total_items = output['pagination']['totalItems']
        print('S1 SuperTimeline:: Total Record Count: ' + str(total_items))
        if total_items >= 19000:
            print(
                "S1 SuperTimeline:: Warning: Record count is higher than 19000, you may be missing some data. "
                "Try reducing your search scope\n")

        return query_id


class TimeTools:
    def time_convert(self, date_time_str, utc):
        #Allowed time formats are: yyyy-mm-ddThh:ss, yyyy-mm-dd hh:ss, yyyymmddThhss, yyyymmdd. If not exit
        if self.is_date(date_time_str) == False:
            print("S1 SuperTimeline:: Error | incorrect date and time format. Please use the following syntax:\n\n"
                  "yyyy-mm-ddThh:ss, yyyy-mm-dd hh:ss, yyyymmddThhss, or yyyymmdd")
            sys.exit()

        # Remove characters
        date_time_str = date_time_str.replace(':','').replace('-','').replace(' ','T').replace('/', '')

        # Sort out the format
        if ('T' or 't') in date_time_str:
            date = date_time_str[0:4]
            month = date_time_str[4:6]
            day = date_time_str[6:8]
            hour = date_time_str[9:11]
            minute = date_time_str[11:14]
            date_time = (date + '-' + month + '-' + day + 'T' + hour + ":" + minute + ":00.000000")

        if ('T' or 't') not in date_time_str:
            date = date_time_str[0:4]
            month = date_time_str[4:6]
            day = date_time_str[6:8]
            hour = '00'
            minute = '00'
            date_time = (date + '-' + month + '-' + day + 'T' + hour + ":" + minute + ":00.000000")

        if utc is True:
            # Change the time from local to utc
            # Auto-detect zones:
            utc_zone = tz.tzutc()
            local_zone = tz.tzlocal()

            # Convert time string to datetime
            local_time = datetime.strptime(date_time, '%Y-%m-%dT%H:%M:%S.%f')

            # Tell the datetime object that it's in local time zone since
            # datetime objects are 'naive' by default
            local_time = local_time.replace(tzinfo=local_zone)
            # Convert time to UTC
            utc_time = local_time.astimezone(utc_zone)
            # Generate UTC time string
            utc_string = utc_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

        if utc is False:
            utc_string = date_time + "Z"

        return utc_string

    def datetime_range(self, start, end, delta):
        current = start
        while current < end:
            yield current
            current += delta

    def is_date(self, string, fuzzy=False):
        """
        Return whether the string can be interpreted as a date.

        :param string: str, string to check for date
        :param fuzzy: bool, ignore unknown tokens in string if True
        """
        try:
            parse(string, fuzzy=fuzzy)
            return True

        except ValueError:
            return False


if __name__ == "__main__":
    # Take input from user
    parser = argparse.ArgumentParser(description='SentinelOne SuperTimeline :: By Juan Ortega '
                                                 '<falseflag00@protonmail.com>')
    required = parser.add_argument_group('Required Arguments')
    required.add_argument('-t', '--s1_api_token', help='SentinelOne API Token', required=True)
    required.add_argument('-url', '--s1_url', help='SentinelOne Console Url', required=True)

    required.add_argument('-from', '--from_date', help="From Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD",
                          required=True)
    required.add_argument('-to', '--to_date', help="To Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD", required=True)
    required.add_argument('-min', '--min_increments', help="Minute increments to split time date range by",
                          required=True)
    required.add_argument('-u', '--utc', help="Accepts --date_from/--date_to as UTC, Default is local time",
                          action='store_false')

    args = parser.parse_args()
    # Start program and pass user options
    main(args)
