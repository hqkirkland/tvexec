import json
import os

from M3UBuilder import M3UBuilder
from M3UReader import M3UReader
from datetime import datetime, timedelta

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'

class LineupPlanner(object):
    def __init__(self, min_entries=3, pop_entries=False, schedule_start_datetime=None, schedule_end_datetime=None):
        try: 
            with open("lineup.json", "r") as lineup_file:
                self.lineup_strdict = json.load(lineup_file)
            with open("series_config.json", "r") as series_config_file:
                self.series_list = json.load(series_config_file)

        except Exception:
            self.log_message("Unable to locate required lineup or series configuration files: lineup.json, series_config.json", "error")

        self.set_datetimes(schedule_start_datetime, schedule_end_datetime)

        self.min_entries = min_entries
        self.pop_entries = pop_entries
        self.day_of_week = self.schedule_date.strftime('%A')
        self.lineup = { }
        self.series_counts = { }

        self.broadcast_lineup_path = ""
        
    def set_datetimes(self, schedule_start_datetime=None, schedule_end_datetime=None):
        if schedule_start_datetime is not None and schedule_start_datetime > datetime.now():
            self.log_message("Setting startup time to: {0}".format(schedule_start_datetime.strftime("%I:%M:%S %p")))
            self.schedule_date = schedule_start_datetime.date()
            self.schedule_start_datetime = schedule_start_datetime
            self.schedule_end_datetime =  schedule_start_datetime.replace(hour=23, minute=59, second=59)
            return

        else:
            self.schedule_date = datetime.now().date()
            self.schedule_start_datetime = datetime.now()
            self.schedule_end_datetime = datetime.now().replace(hour=23, minute=59, second=59)
        
        if schedule_end_datetime is not None:
            if schedule_end_datetime > self.schedule_start_datetime:
                self.schedule_end_datetime = schedule_end_datetime

    def planhours(self):
        self.log_message("Generating schedule for {0}".format(self.schedule_start_datetime.strftime("%c")))
        slot_hour = self.schedule_start_datetime
        slot_hour = slot_hour.replace(hour=0, minute=0, second=0)
        
        for hour in range(0, 24):
            slot_hour = slot_hour.replace(hour=hour)
            hour_key = datetime.strftime(slot_hour, "%I:00 %p")

            if hour_key not in self.lineup_strdict[self.day_of_week]:
                slot_hour = slot_hour.replace(hour=hour - 1)
                prev_hour_key = datetime.strftime(slot_hour, "%I:00 %p")
                blocks = self.lineup_strdict[self.day_of_week][prev_hour_key]

            else:
                blocks = self.lineup_strdict[self.day_of_week][hour_key]
                for n in range(0, len(blocks)):
                    if blocks[n] == "":
                        if n == 0 and hour != 0:
                            prev_hour_key = datetime.strftime(slot_hour.replace(hour=hour - 1), "%I:00 %p")
                            blocks[n] = self.lineup_strdict[self.day_of_week][prev_hour_key][n]
                        elif n == 0 and hour == 0:
                            exit()
                        elif n != 0:
                            blocks[n] = self.lineup_strdict[self.day_of_week][hour_key][n - 1]

            self.lineup_strdict[self.day_of_week][hour_key] = blocks

        return None

    def planlineup(self):
        hour_scan_time = self.schedule_start_datetime
        m3u_reader_collection = { }
        self.series_counts = {}

        lineup_info_path = "plan_latest.txt"
        lineup_info_path = os.path.join(os.curdir, lineup_info_path)
       
        # Enter each hour for this day.
        for hour_key in self.lineup_strdict[self.day_of_week].keys():
            block = self.lineup_strdict[self.day_of_week][hour_key]

            for n in range(0, len(block)):
                series_key = block[n]
                series = self.series_list[series_key]
                path_to_series = os.path.normpath(series["rootDirectory"])

                if series_key in self.series_counts.keys():
                    self.series_counts[series_key] = self.series_counts[series_key] + 1
                else:
                    self.series_counts.update({ series_key: 1 })

        for series_key in self.series_counts.keys():
            if series_key in m3u_reader_collection.keys():
                continue

            series = self.series_list[series_key]

            path_to_series = os.path.normpath(series["rootDirectory"])

            m3u_safe_series_key = series_key.replace(':', '')
            path_to_m3u = os.path.join(path_to_series, "{0}{1}".format(m3u_safe_series_key, ".m3u"))

            new_m3u_reader = M3UReader ( path_to_m3u, series_key )
            m3u_reader_collection.update({ series_key: new_m3u_reader })

        if os.path.exists(lineup_info_path):
            os.remove(lineup_info_path)

        with open(lineup_info_path, "x") as broadcast_lineup_outfile:
            entry_num = self.min_entries
            while len(self.lineup) < entry_num:
                hour_key = hour_scan_time.strftime("%I:00 %p")
                self.day_of_week = hour_scan_time.strftime("%A")
                # HH:??
                hour_start_time = hour_scan_time
                # HH:59
                hour_end_time = hour_start_time
                hour_end_time = hour_end_time.replace(minute=59, second=59)
                # Current iteration time.
                # Enter each entry for this hour block.
                hour_block = self.lineup_strdict[self.day_of_week][hour_key]

                n = 0
                while hour_scan_time < hour_end_time:
                    if len(self.lineup) >= entry_num:
                        if hour_scan_time > self.schedule_end_datetime:
                            break
                        else:
                            # This will allow previous loop to continue advancing.
                            entry_num += 1
                    
                    scan_series = hour_block[n]
                    scan_entry = m3u_reader_collection[scan_series].read_next_playlist_entry(pop=self.pop_entries)
                    
                    scan_entry_title = scan_entry["entry_title"]
                    scan_entry_length = timedelta(seconds=int(scan_entry["m3u_duration"]))
                    scan_entry_file = scan_entry["file_path"]

                    entry_end_time = hour_scan_time + scan_entry_length

                    lineup_line_entry = "{0}-{1}: {2}{3}".format(hour_scan_time.strftime("%I:%M:%S %p"), entry_end_time.strftime("%I:%M:%S %p"), scan_entry_title, SHELL_NEWLINE)
                    broadcast_lineup_outfile.writelines([lineup_line_entry,])
                    
                    self.lineup[hour_scan_time.strftime("%A %I:%M:%S %p")] = { 
                        "block_entry": scan_series,
                        "file_path": scan_entry_file,
                        "end_time": entry_end_time.strftime("%A %I:%M:%S %p")
                    }

                    hour_scan_time = entry_end_time
                    
                    # Advance the block index.
                    if n < len(hour_block) - 1:
                        n += 1
            
            self.schedule_end_datetime = hour_scan_time
            self.broadcast_lineup_path = lineup_info_path

        self.log_message("{0} created for: {1} ".format(self.broadcast_lineup_path, self.schedule_date.strftime("%A %m/%d/%Y") ) )
        self.log_message("{0}'s lineup will terminate @ {1}".format(self.day_of_week, self.schedule_end_datetime))

        for series_key in self.series_counts.keys():
            if self.pop_entries:
                self.log_message("Saving popped playlist for {0}".format(series_key))
                m3u_reader_collection[series_key].save_popped_playlist()

    def log_message(self, message="Hello, developer!", level="info"):
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()

        print("[{0}] {1}".format(level.upper(), message))