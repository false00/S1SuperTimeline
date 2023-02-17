"""
Copyright (c) 2023 Juan Ortega. All rights reserved.

This software is provided 'as-is', without any express or implied warranty. In no event will the authors be held liable for any damages arising from the use of this software.

Permission is granted for personal use only. Commercial use of this software is strictly prohibited.
"""

import hashlib
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
from timeliner import EventCombiner
from tqdm import tqdm


def main(args):
    if args.seconds:
        increment_type = 'second'
    elif args.minutes:
        increment_type = 'minute'
    elif args.hours:
        increment_type = 'hour'
    elif args.days:
        increment_type = 'day'
    else:
        print('S1 SuperTimeline:: ERROR | No increment selected')
        sys.exit()

    s1_api = SentinelOne(args.s1_url, args.s1_api_token)
    should_continue = s1_api.check_auth()

    if should_continue:
        deep_viz_query = input('S1 SuperTimeline:: Input Deep Visibility Query \n')
        filename = input('S1 SuperTimeline:: Input a filename for the output file \n')

        super_timeline = SuperTimeline(args.s1_url, args.s1_api_token)
        super_timeline.sentinelone_deepviz(increment_type, deep_viz_query, args.from_date, args.to_date, args.utc,
                                           filename, args.account_ids)


class SuperTimeline:

    def __init__(self, console_url, api_token):
        self.console_url = console_url
        self.api_token = api_token
        self.supertimeline = []
        self.missing_data = []

    def sentinelone_deepviz(self, increment_type, query, time_from, time_to, utc, filename, account_ids=None):
        # Convert time to query format
        time_tools = TimeTools()
        time_from = time_tools.time_convert(time_from, utc)
        time_to = time_tools.time_convert(time_to, utc)

        date_ranges = time_tools.get_time_ranges(time_from, time_to, increment_type)
        for _ in date_ranges:
            self.get_dv_full(query=query, date_from=_['start'], date_to=_['end'], account_ids=account_ids)

        exceptions_sort_order = ['createdAt', 'accountId', 'agentDomain', 'agentName', 'agentId', 'agentIp',
                                 'agentMachineType', 'user', 'trueContext', 'eventType', 'dnsRequest', 'dstIp',
                                 'dstPort',
                                 'connectionStatus', 'EventMessage']
        combiner = EventCombiner(self.supertimeline, exceptions=exceptions_sort_order)
        combined_data = combiner.combine_events()

        output_file = filename + '_' + query[:100]
        try:
            if output_file.endswith('xlsx'):
                filename = output_file
            else:
                filename = output_file + '.xlsx'

            combiner.write_to_xlsx(combined_data, filename, sort_order=exceptions_sort_order)
        except:
            try:
                if output_file.endswith('json'):
                    filename = output_file
                else:
                    filename = output_file + '.json'

                combiner.write_to_json(combined_data, filename)
            except:
                if output_file.endswith('csv'):
                    filename = output_file
                else:
                    filename = output_file + '.csv'

                combiner.write_to_csv(combined_data, filename)

    def get_dv_full(self, query, date_from, date_to, account_ids=None):
        s1_api = SentinelOne(self.console_url, self.api_token)

        query_id = s1_api.get_query_id(query, date_from, date_to, account_ids)

        while True:
            print(f'S1 SuperTimeline:: Downloading | query: {query}, time_from:{date_from}, time_to:{date_to}')
            url = f"https://{self.console_url}/web/api/v2.1/dv/events?limit=1000&queryId={query_id}&" \
                  f"apiToken={self.api_token}"

            response = requests.request("GET", url)

            if response.status_code == 200:
                output = response.json()

                # merge list O(n)
                self.supertimeline.extend(output['data'])
                print(f'S1 SuperTimeline:: Downloaded {len(self.supertimeline)} records(s)')

                # Create pagination variable to go to next page
                pagination = output['pagination']['nextCursor']
                break

        while True:
            if pagination:
                url = f"https://{self.console_url}/web/api/v2.1/dv/events?limit=1000&queryId={query_id}&" \
                      f"apiToken={self.api_token}&cursor={pagination}"

                response = requests.request("GET", url)
                output = response.json()

                if response.status_code == 200:
                    pagination = output['pagination']['nextCursor']
                    self.supertimeline.extend(output['data'])
                    print(f'S1 SuperTimeline:: Downloaded {len(self.supertimeline)} record(s)')

            else:
                print(
                    f'S1 SuperTimeline:: Download Complete | query: {query}, time_from:{date_from}, time_to:{date_to}')
                break


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
            headers = {'Content-Type': 'application/json'}

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

    def get_query_id(self, query, time_from, time_to, account_id=None):
        headers = {'Content-Type': 'application/json', 'User-Agent': 'https://github.com/false00/S1SuperTimeline'}

        # Keep trying until response
        while True:
            try:
                url = f"https://{self.console_url}/web/api/v2.1/dv/init-query?apiToken={self.api_token}"
                payload = {"fromDate": time_from, "toDate": time_to, "limit": 20000,
                           "query": query}

                if account_id:
                    account_ids = {"accountIds": account_id.split(',')}
                    payload = payload | account_ids

                response = requests.request("POST", url, headers=headers, data=json.dumps(payload, default=str))
                output = response.json()

                if response.status_code == 200:
                    query_id = output['data']['queryId']
                    print(
                        f'S1 SuperTimeline:: Query sent successfully. query: {query}, time_from:{time_from}, time_to:{time_to}')
                elif 400 <= response.status_code <= 499:
                    print(
                        f'S1 SuperTimeline:: ERROR | Invalid S1QL query or Auth error. Exiting... | {response.content}')
                    sys.exit()
                else:
                    print(f'S1 SuperTimeline:: ERROR | S1 API did not respond. Retrying... | {response.content}')
                    time.sleep(10)

                break
            except Exception as error:
                sleep = 10
                print(
                    f'S1 SuperTimeline:: Query failed, trying again in {str(sleep)} second(s). | http_response: '
                    f'{response.status_code} | {error} | query: {query}, time_from:{time_from}, time_to:{time_to}')
                time.sleep(sleep)

        # Wait for query to complete
        while True:
            url = f"https://{self.console_url}/web/api/v2.1/dv/query-status?queryId={query_id}&apiToken={self.api_token}"

            response = requests.request("GET", url, headers=headers, data=payload)

            output = response.json()

            try:
                if output['data']['responseState'] == 'FINISHED':
                    # Check result count
                    url = f"https://{self.console_url}/web/api/v2.1/dv/events?limit=1&queryId={query_id}&apiToken={self.api_token}"

                    response = requests.request("GET", url)
                    output = response.json()

                    # Warn the user if the record size is near the limit
                    total_items = output['pagination']['totalItems']
                    print('S1 SuperTimeline:: Total Record Count: ' + str(total_items))
                    if total_items >= 100000:
                        print(
                            f"S1 SuperTimeline:: WARN | query:{query}, time_from:{time_from}, time_to:{time_to} | Record count is higher than 19000")
                    break

                if output['data']['responseState'] != 'FINISHED':
                    time.sleep(10)
                    print(
                        f"S1 SuperTimeline:: INFO | query: {query}, time_from:{time_from}, time_to:{time_to} | Query Status: " +
                        output['data']['responseState'] + " Progress: " + str(output['data']['progressStatus']))

            except Exception as error:
                print(f"S1 SuperTimeline:: ERROR | Query timed out | PythonError: {error} | S1Error: {output} \n")
                break

        return query_id


class TimeTools:
    def time_convert(self, date_time_str, utc):
        # Allowed time formats are: yyyy-mm-ddThh:ss, yyyy-mm-dd hh:ss, yyyymmddThhss, yyyymmdd. If not exit
        if self.is_date(date_time_str) == False:
            print("S1 SuperTimeline:: Error | incorrect date and time format. Please use the following syntax:\n\n"
                  "yyyy-mm-ddThh:ss, yyyy-mm-dd hh:ss, yyyymmddThhss, or yyyymmdd")
            sys.exit()

        # Remove characters
        date_time_str = date_time_str.replace(':', '').replace('-', '').replace(' ', 'T').replace('/', '')

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

        date_format = "%Y-%m-%dT%H:%M:%S.%fZ"

        # Parse the string into a datetime object
        utc_string = datetime.strptime(utc_string, date_format)

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

    def get_time_ranges(self, start_datetime, end_datetime, interval):
        time_ranges = []
        delta = None
        if interval == 'minute':
            delta = timedelta(minutes=1)
        elif interval == 'hour':
            delta = timedelta(hours=1)
        elif interval == 'day':
            delta = timedelta(days=1)
        elif interval == 'second':
            delta = timedelta(seconds=1)
        else:
            raise ValueError('Invalid interval: {}'.format(interval))
        current_datetime = start_datetime
        while current_datetime < end_datetime:
            next_datetime = current_datetime + delta
            if next_datetime > end_datetime:
                next_datetime = end_datetime
            time_range = {
                'start': current_datetime,
                'end': next_datetime
            }
            time_ranges.append(time_range)
            current_datetime = next_datetime
        return time_ranges


if __name__ == "__main__":
    # Take input from user
    parser = argparse.ArgumentParser(description='SentinelOne SuperTimeline | Deep Viz Downloader | 2.0')
    required = parser.add_argument_group('Required Arguments')
    required.add_argument('-t', '--s1_api_token', help='SentinelOne API Token', required=True)
    required.add_argument('-url', '--s1_url', help='SentinelOne Console Url', required=True)

    required.add_argument('-from', '--from_date', help="From Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD",
                          required=True)
    required.add_argument('-to', '--to_date', help="To Date. Format YYYY-MM-DDTHH:MM or YYYY-MM-DD", required=True)
    increment = parser.add_mutually_exclusive_group(required=True)
    required.add_argument('-u', '--utc', help="Accepts --date_from/--date_to as UTC, Default is local time",
                          action='store_false')
    required.add_argument('-aid', '--account_ids',
                          help="Account ID filter for deep visibility. This will limit search scope to a specific "
                               "account. Accepts multiple accountids. Input multiple ids with comma seperator")

    # query_slicer
    increment.add_argument('-s', '--seconds',
                           help='Breakup queries by seconds (slow but most likely to return full data)',
                           action='store_true')
    increment.add_argument('-m', '--minutes', help='Breakup queries by minutes', action='store_true')
    increment.add_argument('-hr', '--hours', help='Breakup queries by hours', action='store_true')
    increment.add_argument('-d', '--days', help='Breakup queries by days', action='store_true')

    args = parser.parse_args()
    # Start program and pass user options
    main(args)
