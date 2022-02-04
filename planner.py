import hashlib
import json
import os

from M3UBuilder import M3UBuilder
from M3UReader import M3UReader
from datetime import datetime, timedelta

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'

DAY_KEYFMT = "%A"
HOUR_KEYFMT = "%I:00 %p"

DAYS_OF_WEEK = [ "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday" ]
HOURS_OF_DAY = [ datetime.strftime(datetime.now().replace(hour=n), HOUR_KEYFMT) for n in range(0, 24) ]
# LINEUP_TPL = { k:{ h: [] for h in HOURS_OF_DAY } for k in DAYS_OF_WEEK }

class LineupPlanner(object):
    def __init__(self):
        self.lineup = { k:{ h: [] for h in HOURS_OF_DAY } for k in DAYS_OF_WEEK }
        
        lineup_file_strdict = self.load_lineup_file()
        self.commit_lineup(lineup_file_strdict)
        self.series_keys = self.series_list.keys()
    
    def load_lineup_file(self, refresh=False):
        # TODO: Before performing lineup refresh, checksum file to establish modification made.
        try:
            with open("series_config.json", "r") as series_config_file:
                self.series_list = dict(json.load(series_config_file))
                return None
        except Exception:
            self.log_message("Unable to locate or parseseries configuration file: series_config.json", "error")

        try:
            with open("lineup_debug.json", "r") as lineup_file:
                lineup_strdict = dict(json.load(lineup_file))
        except Exception:
            self.log_message("Unable to locate or parse required lineup file: lineup.json", "error")
            return None

        return self.normalize_lineup(lineup_strdict)

    def normalize_lineup(self, lineup_strdict):
        if not isinstance(lineup_strdict, dict):
            self.log_message("Expected instance of dict in argument, given is: {0}" \
                .format(type(lineup_strdict)), "error")
        
        saved_block = None
        for day in range(0, 7):
            for hour in range(0, 24):
                
                d_key = DAYS_OF_WEEK[day]
                h_key = HOURS_OF_DAY[hour]

                saved_block = None
                saved_hour = hour

                # Attempt block save.
                if h_key not in lineup_strdict[d_key]:
                    lineup_strdict[d_key].update({ h_key: ["",] })
                else: 
                    saved_block = lineup_strdict[d_key][h_key]
                
                # if h_key == "12:00 AM" and d_key == "Thursday":
                    # print("Block")
                # if h_key == "01:00 AM" and d_key == "Wednesday":
                    # print("Block")
                
                # First test of block. 
                # Check existence, verify not all null or blank values. 
                # Pass of any condition results in backsearch, addition of missing hours.
                while saved_block is None or len(saved_block) < 1 or all([entry == "" for entry in saved_block ]):
                    hour -= 1
                    p_h = (hour) % 24
                    p_d = ((day * 24) + hour) // 24

                    d_skey = DAYS_OF_WEEK[p_d]
                    h_skey = HOURS_OF_DAY[p_h]

                    if h_skey not in lineup_strdict[d_skey]:
                        lineup_strdict[d_skey].update({ h_skey: ["",] })
                    else:
                        saved_block = lineup_strdict[d_skey][h_skey]
                
                # Return to main hour loop, save block.
                hour = saved_hour
                
                # Keys go back to pre-loop values.
                d_key = DAYS_OF_WEEK[day]
                h_key = HOURS_OF_DAY[hour]

                p_h = (hour - 1) % 24
                p_d = (day - 1) % 7
                
                lineup_strdict[d_key][h_key] = saved_block
                slot_count = len(lineup_strdict[d_key][h_key])


                for s_key in range(0, slot_count):
                    slot_entry = lineup_strdict[d_key][h_key][s_key]                    
                    if slot_entry not in self.series_keys:
                        self.log_message("Unable to locate \"{0}\" in lineup for {1} @ {2}, Slot #{3}".format(slot_entry, d_key, h_key, s_key))
                        lineup_strdict[d_key][h_key][s_key] = ""
                    if slot_entry == "" or slot_entry not in self.series_keys:
                        if s_key == 0:
                            if p_h == 23:
                                lineup_strdict[d_key][h_key][s_key] = lineup_strdict[DAYS_OF_WEEK[p_d]][HOURS_OF_DAY[p_h]][-1]
                            else:
                                lineup_strdict[d_key][h_key][s_key] = lineup_strdict[d_key][HOURS_OF_DAY[p_h]][-1]
                        else:
                            lineup_strdict[d_key][h_key][s_key] = lineup_strdict[d_key][h_key][s_key - 1]
        return lineup_strdict

    def commit_lineup(self, lineup_strdict):         
        for day in range(0, 7):
            for hour in range(0, 24):
                d_key = DAYS_OF_WEEK[day]
                h_key = HOURS_OF_DAY[hour]

                self.lineup[d_key][h_key] = lineup_strdict[d_key][h_key]
    
    def read_blocks_by_date(self, start_datetime):
        read_weekday = DAYS_OF_WEEK[start_datetime.weekday]
        read_hour = HOURS_OF_DAY[start_datetime.hour]
        
        try:
            return self.lineup[read_weekday][read_hour]
        except KeyError:
            self.log_message("Read error for {0} @ {1}".format(read_weekday, read_hour), "error")
            return None

    def log_message(self, message="Hello, developer!", level="info"):
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()
        print("[{0}] {1}".format(level.upper(), message))
