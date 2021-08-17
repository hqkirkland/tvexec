import json
import os
import random
import stat
import subprocess

import natsort

from M3UReader import M3UReader
from datetime import datetime, timedelta
from optparse import OptionParser

if os.name == "nt":
    SHELL_EXTENSION = "bat"
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_EXTENSION = "sh"
    SHELL_NEWLINE = '\n'


class DaySchedule(object):
    def __init__(self, schedule_start_datetime=None, rtmp_ept="rtmp://127.0.0.1/show/stream"):
        self.set_datetimes(schedule_start_datetime)
        self.day_of_week = self.schedule_date.strftime('%A')
        self.lineup = { }
        self.rtmp_endpoint = rtmp_ept
        self.shell_broadcast_path = ""
        self.ffmpeg_commands = []

        try: 
            with open("lineup.json", "r") as lineup_file:
                self.lineup_strdict = json.load(lineup_file)
            with open("series_config.json", "r") as series_config_file:
                self.series_list = json.load(series_config_file)

        except Exception:
            self.log_message("Unable to locate required lineup or series configuration files.", "error")

    def set_datetimes(self, schedule_start_datetime=None):
        if schedule_start_datetime is None:
            self.schedule_date = datetime.today().date()
            self.schedule_start_datetime = datetime.today()
            self.schedule_end_datetime = datetime.today().replace(hour=23, minute=59, second=59)
        else:
            self.schedule_date = schedule_start_datetime.date()
            # self.schedule_start_datetime = schedule_start_datetime.replace(hour=0, minute=0, second=0)
            self.schedule_start_datetime = schedule_start_datetime
            self.schedule_end_datetime =  schedule_start_datetime.replace(hour=23, minute=59, second=59)

    def gen_series_playlists(self):
        for series_key in self.series_list.keys():
            self.log_message("Generating M3U playlist for {0}".format(series_key))
            extensions_allowed = ("mkv", "avi", "mp4", "m4a", "wav", "mp3", "")
            series = self.series_list[series_key]
            path_to_series = os.path.normpath(series["rootDirectory"])
            if os.path.exists(path_to_series):
                m3u_safe_series_key = series_key.replace(':', ' ')
                path_to_m3u = os.path.join(path_to_series, "{0}{1}".format(m3u_safe_series_key, ".m3u"))
                if (os.path.exists(path_to_m3u)):
                    continue
                
                with open(path_to_m3u, "x") as series_m3u:
                    series_m3u.writelines(("#EXTM3U" + '\n',))
                    
                    dirs_in_seriespath = [os.path.normpath(d) for d in os.listdir(path_to_series) if os.path.isdir(os.path.join(path_to_series, d))]
                    files_in_seriespath = [os.path.normpath(f) for f in os.listdir(path_to_series) if os.path.isfile(os.path.join(path_to_series, f))]
                    
                    # Is dir sort necessary if all files get natsorted by end?
                    # dirs_in_seriespath = natsort.natsorted(dirs_in_seriespath)

                    # This next condition likely means that the directory is split by season.
                    if len(dirs_in_seriespath) > len(files_in_seriespath):
                        files_in_series = ()
                        for subdir in dirs_in_seriespath:
                            subdir_season_path = os.path.normpath(os.path.join(path_to_series, subdir))
                            self.log_message("> Navigating into: {0}".format(subdir_season_path))
                            for season_episode in os.listdir(subdir_season_path):
                                self.log_message("> Adding {0}".format(season_episode))
                                path_to_episode_file = os.path.join(subdir_season_path, season_episode)
                                if os.path.isfile(path_to_episode_file):
                                    files_in_series = files_in_series + (path_to_episode_file,)
                    else:
                        subdir_season_path = path_to_series
                        files_in_series = files_in_seriespath
                    
                    # Sort files last.
                    files_in_series = natsort.natsorted(files_in_seriespath)

                    if "playlistType" in series:
                        if series["playlistType"] == "shuffle":
                            print("> Shuffling playlist for: {0}".format(series_key))
                            random.shuffle(files_in_series)
                            
                    for episode_file in files_in_series:                        
                        path_to_episode_file = os.path.normpath(os.path.join(subdir_season_path, episode_file))
                        self.log_message("Episode path: {0}".format(path_to_episode_file))

                        episode_file_name = os.path.basename(path_to_episode_file).split('.')

                        if len(episode_file_name) > 2:
                            episode_file_extension = episode_file_name[len(episode_file_name) - 1]
                        else:
                            episode_file_extension = episode_file_name[1]

                        if episode_file_extension not in extensions_allowed:
                            self.log_message("> Skipping: {0}".format(path_to_episode_file))
                            continue

                        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                                "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                                                path_to_episode_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                        clean_result = result.stdout.strip().split(b'\r')[0]
                        self.log_message("Result: {0}".format(clean_result))
                        
                        try:
                            episode_len = float(clean_result)
                        except ValueError:
                            episode_len = 0.0

                        self.log_message("> {0} duration is {1}s".format(episode_file_name[0], str(int(episode_len))))
                        episode_title = episode_file_name[0].replace("_", " ")
                        episode_title_line = "#EXTINF:{0},{1} - {2}".format(str(int(episode_len)), series_key, episode_title)
                        
                        series_m3u.writelines((episode_title_line + '\n', path_to_episode_file + '\n\n'))

    def genday(self):
        slot_hour = self.schedule_start_datetime
        slot_hour = slot_hour.replace(hour=0, minute=0, second=0)
        for hour in range(0, 24):
            slot_hour = slot_hour.replace(hour=hour)
            hour_key = datetime.strftime(slot_hour, "%I:00 %p")
            
            if hour_key not in self.lineup_strdict[self.day_of_week]:
                slot_hour = slot_hour.replace(hour=hour - 1)
                prev_hour_key = datetime.strftime(slot_hour, "%I:00 %p")
                blocks = self.lineup_strdict[self.day_of_week][prev_hour_key]
                self.log_message("Hour {0} does not exist for {1} Repeating: Hour {2}".format(hour_key, self.day_of_week, prev_hour_key), "warn")

            else:
                blocks = self.lineup_strdict[self.day_of_week][hour_key]
                for n in range(0, len(blocks)):
                    if blocks[n] == "":
                        prev_hour_key = datetime.strftime(slot_hour, "%I:00 %p")
                        if n == 0 and hour != "0":
                            slot_hour = slot_hour.replace(hour=hour - 1)
                            prev_hour_key = datetime.strftime(slot_hour, "%I:00 %p")

                            self.log_message("Hour {0}, Block {1} is empty; Repeating: Hour {2}, Block {3}".format(hour, str(n), prev_hour_key, str(n)), "warn")
                            blocks[n] = self.lineup_strdict[self.day_of_week][prev_hour_key][n]
                        else:
                            self.log_message("Hour {0}, Block {1} is empty; Repeating: Hour {2}, Block {3}".format(hour, str(n), prev_hour_key, str(n)), "warn")
                            blocks[n] = self.lineup_strdict[self.day_of_week][prev_hour_key][n]

                self.lineup_strdict[self.day_of_week][hour_key] = blocks

        return None

    def validday(self):
        # Enter each hour for this day.
        hour_scan_time = self.schedule_start_datetime
        batch_path = "broadcast_{0}.{1}".format(schedule.schedule_date.strftime("%Y%m%d"), SHELL_EXTENSION )
        batch_path = os.path.join(os.curdir, batch_path)

        self.log_message("Generating schedule for {0}".format(self.schedule_start_datetime.strftime("%c")))

        m3u_reader_collection = { }
        series_counts = {}

        for hour_key in self.lineup_strdict[self.day_of_week].keys():
            block = self.lineup_strdict[self.day_of_week][hour_key]

            for n in range(0, len(block)): 
                series_key = block[n]
                series = self.series_list[series_key]
                path_to_series = os.path.normpath(series["rootDirectory"])

                if series_key in series_counts.keys():
                    series_counts[series_key] = series_counts[series_key] + 1
                else:
                    series_counts.update({ series_key: 1 })
            
        for series_key in series_counts.keys():
            if series_key in m3u_reader_collection.keys():
                continue

            series = self.series_list[series_key]
            
            path_to_series = os.path.normpath(series["rootDirectory"])
            
            m3u_safe_series_key = series_key.replace(':', ' ')
            path_to_m3u = os.path.join(path_to_series, "{0}{1}".format(m3u_safe_series_key, ".m3u"))

            new_m3u_reader = M3UReader ( path_to_m3u, series_key )
            m3u_reader_collection.update({ series_key: new_m3u_reader })

        if os.path.exists(batch_path):
            os.remove(batch_path)
        with open(batch_path, "x") as broadcast_batch_file:
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
                while hour_scan_time < hour_end_time:
                    if hour_scan_time > self.schedule_end_datetime:
                        break
                    
                    scan_series = hour_block[n]
                    scan_series_data = self.series_list[scan_series]
                    scan_entry = m3u_reader_collection[scan_series].pop_next_playlist_entry()

                    scan_entry_length =  timedelta(seconds=int(scan_entry["m3u_duration"]))
                    scan_entry_file = scan_entry["file_path"]

                    entry_end_time = hour_scan_time + scan_entry_length

                    self.log_message("{0} - {1} | {2} : {3}".format(hour_scan_time.strftime("%I:%M:%S %p"), entry_end_time.strftime("%I:%M:%S %p"), hour_key, scan_entry_file))
                    self.lineup[hour_scan_time.strftime("%A %I:%M:%S %p")] = { "file_path": scan_entry_file, "end_time": entry_end_time }

                    filter_flags = ""
                    realtime_flag = "-re"
                    # -preset veryfast
                    output_flags = "-vcodec libx264 -acodec ac3 -g 15 -strict -2 -f flv {0}".format(self.rtmp_endpoint)

                    if "ffmpegFilterFlags" in scan_series_data:
                        filter_flags = scan_series_data["ffmpegFilterFlags"]
                        output_flags = "-crf 28 {0}".format(output_flags)
                        realtime_flag = ""
                    
                    ffmpeg_command = "ffmpeg {0} -i \"{1}\" {2} {3}".format(realtime_flag, scan_entry_file, filter_flags, output_flags)
                    self.ffmpeg_commands.append(ffmpeg_command)                    
                    ffmpeg_command = "{0}{1}".format(ffmpeg_command, SHELL_NEWLINE)

                    # broadcast_batch_file.writelines(ffmpeg_command)
                    hour_scan_time = entry_end_time

                    if n < len(hour_block) - 1:
                        n += 1
            
            self.schedule_end_datetime = hour_scan_time
            self.shell_broadcast_path = batch_path
        
        st = os.stat(self.shell_broadcast_path)
        os.chmod(self.shell_broadcast_path, st.st_mode | stat.S_IEXEC)

        self.log_message("{0} created for: {1} ".format(self.shell_broadcast_path, schedule.schedule_date.strftime("%A %m/%d/%Y") ) )
        self.log_message("{0}'s lineup will terminate @ {1}".format(self.day_of_week, self.schedule_end_datetime))
        
        for series_key in series_counts.keys():
            self.log_message("Saving popped playlist for {0}".format(series_key))
            m3u_reader_collection[series_key].save_popped_playlist()       
                
    def log_message(self, message="Hello, developer!", level="info"):
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()

        print("[{0}] {1}".format(level.upper(), message))

# Main script begin

print("░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░")
print("░░▓▓▒░▒▒░▒▒░▒▒░▒▒░▒▓▓░░░░░░░░░░░░░░")
print("░░▓▓░▒▒░▒▒░▒▒░▒▒░▒▒▓▓░░░░░░░░░░░░░░")
print("░░▓▓▒▒░▒▒░▒▒░▒▒░▒▒░▓▓░░░░░░░░░░░░░░")
print("░░▓▓▒░▒▒░▒▒░▒▒░▒▒░▒▓▓░░░░░░░░░░░░░░")
print("░░▓▓░▒▒░▒▒░▒▒░▒▒░▒▒▓▓░░TV░░░░░░░░░░")
print("░░▓▓▒▒░▒▒░▒▒░▒▒░▒▒░▓▓░░EXECUTIVE░░░")
print("░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░")
print("░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░By Nodebay░░")
print("░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░")

schedule = DaySchedule()
schedule.gen_series_playlists()
schedule.genday()
schedule.validday()

broadcast_start_key = input(">> Start today's broadcast (Y/N)?: ")

if broadcast_start_key == 'y':
    if os.path.exists(schedule.shell_broadcast_path):
        schedule.log_message("Starting {0}".format(schedule.shell_broadcast_path ) )

        for command in schedule.ffmpeg_commands:
            ffmpeg_subprocess = subprocess.Popen(command, shell=True, cwd=os.curdir)
            stdout, stderr = ffmpeg_subprocess.communicate()

while True:
    continue_key = input(">> Continue to next day (Y/N)?: ")
    if continue_key == 'n':
        break
    else:
        print(">> Generating schedule for: {0}".format(schedule.schedule_end_datetime.strftime("%c (%I:%M %p)")))

        schedule = DaySchedule(schedule.schedule_end_datetime)
        schedule.gen_series_playlists()
        schedule.genday()
        schedule.validday()

        if os.path.exists(schedule.shell_broadcast_path):
            schedule.log_message("Starting {0}".format(schedule.shell_broadcast_path ) )

            for command in schedule.ffmpeg_commands:
                ffmpeg_subprocess = subprocess.Popen(command, shell=True, cwd=os.curdir)
                stdout, stderr = ffmpeg_subprocess.communicate()
