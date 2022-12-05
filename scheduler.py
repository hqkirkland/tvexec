import json
import os

from M3UReader import M3UReader
from lineup import LineupCalendar

from datetime import datetime, timedelta

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'

class StreamScheduler(object):
    def __init__(self, lineup_calendar: LineupCalendar):
        self.lineup_calendar = lineup_calendar

    def query_calendar(self, query_datetime, slot_number):
        block = self.lineup_calendar.read_block_by_datetime(query_datetime)
        
        if slot_number >= len(block):
            return str(block[-1])
        elif slot_number > -1:
            return str(block[slot_number])
        else:
            return None
    
    def read_day_span(self, day_datetime, hour_span_length=6, slot_key=0):
        plan_datetime = day_datetime
        scan_hour = plan_datetime.hour
        day_queue = []

        while plan_datetime < day_datetime + timedelta(hours=hour_span_length):
            if scan_hour != plan_datetime.hour:
                # Reset the slot key once we leave the hour.
                slot_key = 0
                scan_hour = plan_datetime.hour
            self.log_message("Planning {0} ".format(plan_datetime.strftime("%A @ %I:%M:%S %p")))
            
            slot_entry = self.query_calendar(plan_datetime, slot_key)
            
            plan_entry = self.lineup_calendar.m3u_reader_collection[slot_entry].read_next_playlist_entry(False)
            plan_entry_length = timedelta(seconds=int(plan_entry["m3u_duration"]))
            plan_entry_file = plan_entry["file_path"]

            if "staticDurationOverride" in self.lineup_calendar.series_list[slot_entry]:
                static_duration_override = self.lineup_calendar.series_list[slot_entry]["staticDurationOverride"]
                plan_entry_length = timedelta(seconds=int(static_duration_override))
            
            day_queue.append (
                {
                    "slot_entry": slot_entry,
                    "episode_title": plan_entry["entry_title"],
                    "start_datetime": plan_datetime, 
                    "end_datetime": plan_datetime + plan_entry_length,
                    "file_path": plan_entry_file
                },
            )
            
            slot_key += 1
            plan_datetime = plan_datetime + plan_entry_length
        
        # Reset the M3UReader cursors.
        for series_key in self.lineup_calendar.m3u_reader_collection.keys():
            self.lineup_calendar.m3u_reader_collection[series_key].m3u_cursor = 0

        return day_queue

    def log_message(self, message="Hello, developer!", level="info"):
        src_obj = "StreamScheduler"
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()
        print("[{0}][{1}] {2}".format(src_obj, level.upper(), message))
