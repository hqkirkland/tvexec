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
    def __init__(self, lineup_calendar: LineupCalendar, rtmp_ept="rtmp://127.0.0.1/show/stream"):
        self.rtmp_endpoint = rtmp_ept
        self.lineup_calendar = lineup_calendar

    def refresh_lineup(self):
        # Temporary. Eventually, build & use refresh capabilities of LineupCalendar class.
        self.lineup_calendar = LineupCalendar()

    def query_calendar(self, query_datetime, slot_number):
        block = self.lineup_calendar.read_block_by_datetime(query_datetime)
        
        if -1 < slot_number < len(block):
            return str(block[slot_number])
        else:
            return None
    
    def read_day(self, day_datetime):
        plan_datetime = day_datetime
        current_hour = plan_datetime.hour
        slot_key = 0
        
        day_queue = []

        while plan_datetime < day_datetime.replace(hour=23, minute=59, second=59):
            self.log_message("Entering {0} ".format(plan_datetime.strftime("%A %I:%M:%S %p")))
            
            if plan_datetime.hour != current_hour:
                current_hour = plan_datetime.hour
                slot_key = 0
            
            elif slot_key > len(self.lineup_calendar.read_block_by_datetime(plan_datetime)):
                slot_key = 0

            try_entry = self.query_calendar(plan_datetime, slot_key)
            
            if try_entry is not None:
                slot_entry = try_entry
            
            plan_entry = self.lineup_calendar.m3u_reader_collection[slot_entry].read_next_playlist_entry(False)
            plan_entry_length = timedelta(seconds=int(plan_entry["m3u_duration"]))
            plan_entry_file = plan_entry["file_path"]
            
            day_queue.append (
                {
                    "slot_entry": slot_entry,
                    "start_datetime": plan_datetime, 
                    "end_datetime": plan_datetime + plan_entry_length,
                    "file_path": plan_entry_file
                },
            )
            
            slot_key += 1
            plan_datetime = plan_datetime + plan_entry_length

        return day_queue

    def log_message(self, message="Hello, developer!", level="info"):
        src_obj = "StreamScheduler"
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()
        print("[{0}][{1}] {2}".format(src_obj, level.upper(), message))
