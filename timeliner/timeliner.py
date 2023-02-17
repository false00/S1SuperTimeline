"""
Copyright (c) 2023 Juan Ortega. All rights reserved.

This software is provided 'as-is', without any express or implied warranty. In no event will the authors be held liable for any damages arising from the use of this software.

Permission is granted for personal use only. Commercial use of this software is strictly prohibited.
"""

import csv
import json
from dateutil import parser
import pandas as pd


class EventCombiner:
    def __init__(self, data_list, exceptions=[]):
        self.processed_data = []
        self.exceptions = exceptions
        self.data_list = data_list

    def combine_events(self):
        """Compares all dictionaries in the list and finds common keys.
        Merges unique keys into one key called "EventMessage" and appends to the respective dictionary.
        """
        key_set = set(self.data_list[0].keys())
        empty_key_set = []
        for i in range(1, len(self.data_list)):
            for key, value in self.data_list[i].items():
                if value in ["", None]:
                    empty_key_set.append(key)
            key_set.intersection_update(self.data_list[i].keys())

        empty_key_set = set(empty_key_set)
        for d in self.data_list:
            event_message = {}
            # Add exception fields
            for key in self.exceptions:
                if key not in d:
                    d[key] = None

            # Move unique keys to event message
            unique_keys = set(d.keys()).difference(key_set)
            for key in unique_keys:
                if key not in self.exceptions:
                    event_message[key] = d.pop(key)

            # Move empty keys to event message
            empty_keys = set(empty_key_set).intersection(d.keys())
            empty_keys.difference_update(self.exceptions)
            for key in empty_keys:
                event_message[key] = d.pop(key)
            d["EventMessage"] = event_message

        self.processed_data = self.data_list
        return self.processed_data

    @staticmethod
    def write_to_xlsx(data_list, file_path, sort_order=None):
        pandas_writer = pd.ExcelWriter(file_path, engine='xlsxwriter')

        if sort_order:
            df = pd.DataFrame(data_list).reindex(columns=sort_order)
            worksheet_title = 'Super Timeline'
        else:
            df = pd.DataFrame(data_list)
            worksheet_title = 'Timeline'

        df.to_excel(pandas_writer, sheet_name=worksheet_title, startrow=1, header=False, index=False)
        worksheet = pandas_writer.sheets[worksheet_title]
        # Get the dimensions of the dataframe.
        (max_row, max_col) = df.shape
        # Create a list of column headers, to use in add_table().
        column_settings = [{'header': column} for column in df.columns]
        # Add the Excel table structure. Pandas will add the data.
        worksheet.add_table(0, 0, max_row, max_col - 1, {'columns': column_settings})
        # Make the columns wider for clarity.
        worksheet.set_column(0, max_col - 1, 12)
        pandas_writer.close()

    @staticmethod
    def write_to_csv(data_list, file_path):
        keys = data_list[0].keys()
        with open(file_path, 'w', newline='', encoding='utf-8') as output_file:
            dict_writer = csv.DictWriter(output_file, keys)
            dict_writer.writeheader()
            dict_writer.writerows(data_list)

    @staticmethod
    def write_to_json(data_list, file_path):
        with open(file_path, 'w') as output_file:
            json.dump(data_list, output_file, indent=4, default=str)
