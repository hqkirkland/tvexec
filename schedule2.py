import json
import os

from M3UBuilder import M3UBuilder
from M3UReader import M3UReader
from datetime import datetime, timedelta

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'

class HourSchedule(object):
    def __init__(self, schedule_start_datetime=None, rtmp_ept="rtmp://127.0.0.1/show/stream", pop_entries=True):
        try: 
            with open("lineup.json", "r") as lineup_file:
                self.lineup_strdict = json.load(lineup_file)
            with open("series_config.json", "r") as series_config_file:
                self.series_list = json.load(series_config_file)

        except Exception:
            self.log_message("Unable to locate required lineup or series configuration files: lineup.json, series_config.json", "error")

        self.gen_series_playlists()
        self.set_datetimes(schedule_start_datetime)

        self.pop_entries = pop_entries
        self.day_of_week = self.schedule_date.strftime('%A')
        self.lineup = { }
        self.series_counts = { }
        self.m3u_reader_collection = { }
        self.rtmp_endpoint = rtmp_ept
        self.broadcast_lineup_path = ""
        self.ffmpeg_commands = []

    def set_datetimes(self, schedule_start_datetime=None):
        if schedule_start_datetime is not None and schedule_start_datetime > datetime.now():
            self.log_message("Setting startup time to: {0}".format(schedule_start_datetime.strftime("%I:%M:%S %p")))
            self.schedule_date = schedule_start_datetime.date()
            self.schedule_start_datetime = schedule_start_datetime
            # self.schedule_end_datetime =  schedule_start_datetime.replace(hour=23, minute=59, second=59)
            self.schedule_end_datetime =  datetime.now().replace(minute=59, second=59)
            return

        else:
            self.log_message("Ready to begin; starting broadcast now..", "INFO")
            self.schedule_date = datetime.now().date()
            self.schedule_start_datetime = datetime.now()
            # self.schedule_end_datetime = datetime.now().replace(hour=23, minute=59, second=59)
            self.schedule_end_datetime =  datetime.now().replace(minute=59, second=59, microsecond=0)

    def gen_series_playlists(self):
        for series_key in self.series_list.keys():
            self.log_message("Checking M3U playlist for {0}".format(series_key))
            series = self.series_list[series_key]
            series_playlist_type = series["playlistType"] if "playlistType" in series else ""
            
            series_m3u_builder = M3UBuilder(os.path.normpath(series["rootDirectory"]), series_key)

            if os.path.exists(series_m3u_builder.series_path):
                series_m3u_builder.build(series_playlist_type)

    def genhour(self):
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
                self.log_message("Hour {0} does not exist for {1}; Repeating: Hour {2}".format(hour_key, self.day_of_week, prev_hour_key), "warn")

            else:
                blocks = self.lineup_strdict[self.day_of_week][hour_key]
                for n in range(0, len(blocks)):
                    if blocks[n] == "":
                        if n == 0 and hour != 0:
                            # prev_hour_key = datetime.strftime(slot_hour, "%I:00 %p")
                            # slot_hour = slot_hour
                            prev_hour_key = datetime.strftime(slot_hour.replace(hour=hour - 1), "%I:00 %p")
                            self.log_message("Hour {0}, Block {1} is empty; Repeating: Hour {2}, Block {3}".format(hour, str(n), prev_hour_key, str(n)), "warn")
                            blocks[n] = self.lineup_strdict[self.day_of_week][prev_hour_key][n]
                        elif n == 0 and hour == 0:
                            self.log_message("Hour 0 is empty; midnight slot *must* be set not-null, for now.", "error")
                            exit()
                        elif n != 0:
                            self.log_message("Hour {0}, Block {1} is empty; Repeating: Hour {2}, Block {3}".format(hour, str(n), hour_key, str(n - 1)), "warn")
                            blocks[n] = self.lineup_strdict[self.day_of_week][hour_key][n - 1]

            self.lineup_strdict[self.day_of_week][hour_key] = blocks

        return None

    def validhour(self):
        # Enter each hour for this day.
        hour_scan_time = self.schedule_start_datetime
        lineup_info_path = "broadcast_{0}.txt".format(self.schedule_date.strftime("%Y%m%d"))
        lineup_info_path = os.path.join(os.curdir, lineup_info_path)

        self.log_message("Finalizing schedule for {0}".format(self.schedule_start_datetime.strftime("%c")))

        self.series_counts = {}

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
            if series_key in self.m3u_reader_collection.keys():
                continue

            series = self.series_list[series_key]

            path_to_series = os.path.normpath(series["rootDirectory"])

            m3u_safe_series_key = series_key.replace(':', '')
            path_to_m3u = os.path.join(path_to_series, "{0}{1}".format(m3u_safe_series_key, ".m3u"))

            new_m3u_reader = M3UReader ( path_to_m3u, series_key )
            self.m3u_reader_collection.update({ series_key: new_m3u_reader })

        if os.path.exists(lineup_info_path):
            os.remove(lineup_info_path)

        with open(lineup_info_path, "a") as broadcast_lineup_outfile:
            while hour_scan_time < self.schedule_end_datetime:
                hour_key = hour_scan_time.strftime("%I:00 %p")
                # HH:??
                hour_start_time = hour_scan_time
                # HH:59
                hour_end_time = hour_start_time
                hour_end_time = hour_end_time.replace(minute=59, second=59)
                # Current iteration time.
                # Enter each entry for this hour block.
                hour_block = self.lineup_strdict[self.day_of_week][hour_key]

                n = 0

                broadcast_lineup_outfile.writelines(["Broadcast Plan for {0} @ {1}{2}".format(self.day_of_week, datetime.now().strftime("%I:%M %p"), SHELL_NEWLINE)])
                while hour_scan_time < hour_end_time:
                    if hour_scan_time > self.schedule_end_datetime:
                        break

                    scan_series = hour_block[n]
                    scan_series_data = self.series_list[scan_series]
                    scan_entry = self.m3u_reader_collection[scan_series].read_next_playlist_entry(pop=self.pop_entries)

                    scan_entry_title = scan_entry["entry_title"]
                    scan_entry_length =  timedelta(seconds=int(scan_entry["m3u_duration"]))
                    scan_entry_file = scan_entry["file_path"]

                    entry_end_time = hour_scan_time + scan_entry_length
                    
                    lineup_line_entry = "{0} - {1} | {2} : {3}{4}".format(hour_scan_time.strftime("%I:%M:%S %p"), entry_end_time.strftime("%I:%M:%S %p"), hour_key, scan_entry_title, SHELL_NEWLINE)
                    self.log_message(lineup_line_entry.strip())
                    broadcast_lineup_outfile.writelines([lineup_line_entry,])

                    filter_flags = ""
                    realtime_flag = "-re"
                    # -preset veryfast

                    if "outputFlags" in scan_series_data:
                        override_output_flags = scan_series_data["outputFlags"]
                        str(override_output_flags).replace('\r', '')
                        str(override_output_flags).replace('\n', '')
                        output_flags = "{0} -f flv {1}".format(override_output_flags, self.rtmp_endpoint)

                    else:
                        output_flags = "-vcodec libx264 -c:a aac -b:a 400k -channel_layout 5.1 -g 15 -strict experimental -f flv {0}".format(self.rtmp_endpoint)

                    if "ffmpegFilterFlags" in scan_series_data:
                        filter_flags = scan_series_data["ffmpegFilterFlags"]
                        str(filter_flags).replace('\r', '')
                        str(filter_flags).replace('\n', '')
                        # realtime_flag = ""

                    ffmpeg_command = "ffmpeg {0} -i \"{1}\" {2} {3}".format(realtime_flag, scan_entry_file, filter_flags, output_flags)

                    self.lineup[hour_scan_time.strftime("%A %I:%M:%S %p")] = { 
                        "file_path": scan_entry_file, 
                        "end_time": entry_end_time,
                        "ffmpeg_command": ffmpeg_command
                    }

                    # self.ffmpeg_commands.append(ffmpeg_command)

                    hour_scan_time = entry_end_time

                    if n < len(hour_block) - 1:
                        n += 1

            self.schedule_end_datetime = hour_scan_time
            self.broadcast_lineup_path = lineup_info_path

    def savehour(self):
        for series_key in self.series_counts.keys():
            if self.pop_entries:
                self.log_message("Saving popped playlist for {0}".format(series_key))
                self.m3u_reader_collection[series_key].save_popped_playlist()

    def log_message(self, message="Hello, developer!", level="info"):
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()

        print("[{0}] {1}".format(level.upper(), message))