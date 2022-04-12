import hashlib
import json
import os

from M3UBuilder import M3UBuilder
from M3UReader import M3UReader

from datetime import datetime

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'

DAY_KEYFMT = "%A"
HOUR_KEYFMT = "%I:00 %p"
DATETIME_OUT_FMT = "%A %I:%M:%S %p"
LINEUP_FILENAME = "lineup.json"
# LINEUP_FILENAME = "lineup_debug.json"
SERIES_FILENAME = "series_config.json"

# ISO Week, USA Hours.
DAYS_OF_WEEK = [ "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday" ]
HOURS_OF_DAY = [ datetime.strftime(datetime.now().replace(hour=n), HOUR_KEYFMT) for n in range(0, 24) ]

class LineupCalendar(object):
    def __init__(self):
        self.series_checksum = None
        self.lineup_checksum = None
        
        self.calendar = { k: { h: [] for h in HOURS_OF_DAY } for k in DAYS_OF_WEEK }
        self.m3u_reader_collection = { }
        self.series_list = { }
        
        self.refresh()
    
    def refresh(self):
        lineup_strdict = self.load_lineup_file()

        if lineup_strdict is not None:
            self.commit_lineup(lineup_strdict)
            self.prepare_playlists()
            return True
        return False

    def file_checksum(self, filename):
        h = hashlib.sha1()

        with open(filename, "rb") as file:
            # Loop till the end of the file
            chunk = 0
            while chunk != b'':
                # Read 1024 bytes at a time
                chunk = file.read(1024)
                h.update(chunk)
                # TODO: Could chunks be passed to lineup/series file loader?

        return h.hexdigest()

    def load_lineup_file(self):
        # TODO: Before performing lineup refresh, checksum files for modifications.
        # Hard fail for no series list file.
        try:            
            lineup_load_checksum = self.file_checksum(LINEUP_FILENAME)
            
            if lineup_load_checksum != self.lineup_checksum:
                self.lineup_checksum = lineup_load_checksum
                self.log_message("Checksum performed: lineup has been updated.")
                with open(LINEUP_FILENAME, "r") as lineup_file:
                    lineup_strdict = dict(json.load(lineup_file))
            else:
                return None
            
            series_load_checksum = self.file_checksum(SERIES_FILENAME)

            if series_load_checksum != self.series_checksum:
                self.series_checksum = series_load_checksum
                self.log_message("Checksum performed: series index has been updated.")
                with open(SERIES_FILENAME, "r") as series_config_file:
                    self.series_list = dict(json.load(series_config_file))

        except Exception:
            self.log_message("Unable to locate, open, or parse required lineup or series file!", "error")
            return None

        if not isinstance(lineup_strdict, dict):
            self.log_message("Failed to parse lineup file into dictionary: {0}" \
                .format(type(lineup_strdict)), "error")
            return None
        
        saved_block = None
        for day in range(0, 7):
            d_key = DAYS_OF_WEEK[day]
            # if d_key not in lineup_strdict:
                # lineup_strdict[d_key] = lineup_strdict[DAYS_OF_WEEK[day - 1]]
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

                    slot_entry = lineup_strdict[d_key][h_key][s_key].strip()
                    
                    if slot_entry not in self.series_list.keys():
                        self.log_message("Unable to locate \"{0}\" in lineup for {1} @ {2}, Slot #{3}".format(slot_entry, d_key, h_key, s_key))
                        lineup_strdict[d_key][h_key][s_key] = ""
                        slot_entry = lineup_strdict[d_key][h_key][s_key]

                    if slot_entry == "" or slot_entry not in self.series_list.keys():
                        if s_key == 0:
                            if p_h == 23:
                                lineup_strdict[d_key][h_key][s_key] = lineup_strdict[DAYS_OF_WEEK[p_d]][HOURS_OF_DAY[p_h]][-1].strip()
                            else:
                                lineup_strdict[d_key][h_key][s_key] = lineup_strdict[d_key][HOURS_OF_DAY[p_h]][-1].strip()
                        else:
                            lineup_strdict[d_key][h_key][s_key] = lineup_strdict[d_key][h_key][s_key - 1].strip()
                    slot_entry = None
        return lineup_strdict

    def commit_lineup(self, lineup_strdict):        
        for day in range(0, 7):
            for hour in range(0, 24):
                d_key = DAYS_OF_WEEK[day]
                h_key = HOURS_OF_DAY[hour]

                self.calendar[d_key][h_key] = lineup_strdict[d_key][h_key]
    
    def prepare_playlists(self):
        for series_key in self.series_list.keys():  
            self.log_message("Checking M3U playlist for {0}".format(series_key))
            series = self.series_list[series_key]
            series_playlist_type = series["playlistType"] if "playlistType" in series else ""
            
            series_m3u_builder = M3UBuilder(os.path.normpath(series["rootDirectory"]), series_key)

            if os.path.exists(series_m3u_builder.series_path):
                series_m3u_builder.build(series_playlist_type)
            else:
                self.log_message("Unable to find series path of: {0}".format(series_key), "error")

            path_to_series = os.path.normpath(series["rootDirectory"])

            m3u_safe_series_key = series_key.replace(':', '')
            path_to_m3u = os.path.join(path_to_series, "{0}{1}".format(m3u_safe_series_key, ".m3u"))

            new_m3u_reader = M3UReader ( path_to_m3u, series_key )
            self.m3u_reader_collection.update({ series_key: new_m3u_reader })

    def read_block_by_datetime(self, start_datetime):
        read_weekday = DAYS_OF_WEEK[start_datetime.weekday()]
        read_hour = HOURS_OF_DAY[start_datetime.hour]
        
        try:
            return self.calendar[read_weekday][read_hour]
        except KeyError:
            self.log_message("Read error for {0} @ {1}".format(read_weekday, read_hour), "error")
            return None

    def log_message(self, message="Hello, developer!", level="info"):
        src_obj = "LineupCalendar"
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()
        print("[{0}][{1}] {2}".format(src_obj, level.upper(), message))
