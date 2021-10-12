import json
import os
import random
import stat
import subprocess
import time

import natsort

from M3UReader import M3UReader
from datetime import datetime, timedelta
from optparse import OptionParser

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'


class DaySchedule(object):
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
        self.rtmp_endpoint = rtmp_ept
        self.broadcast_lineup_path = ""
        self.ffmpeg_commands = []

    def set_datetimes(self, schedule_start_datetime=None):
        if schedule_start_datetime is not None and schedule_start_datetime > datetime.now():
            self.log_message("Setting startup time to: {0}".format(schedule_start_datetime.strftime("%I:%M:%S %p")))
            self.schedule_date = schedule_start_datetime.date()
            # self.schedule_start_datetime = schedule_start_datetime.replace(hour=0, minute=0, second=0)
            self.schedule_start_datetime = schedule_start_datetime
            self.schedule_end_datetime =  schedule_start_datetime.replace(hour=23, minute=59, second=59)
            return
        else:
            self.log_message("Time specified has already lapsed.", "WARN")
            self.schedule_date = datetime.now().date()
            self.schedule_start_datetime = datetime.now()
            self.schedule_end_datetime = datetime.now().replace(hour=23, minute=59, second=59)

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
                    files_in_series = natsort.natsorted(files_in_series)

                    if "playlistType" in series:
                        if series["playlistType"] == "shuffle":
                            self.log_message("> Shuffling playlist for: {0}".format(series_key))
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

    def validday(self):
        # Enter each hour for this day.
        hour_scan_time = self.schedule_start_datetime
        lineup_info_path = "broadcast_{0}.txt".format(schedule.schedule_date.strftime("%Y%m%d"))
        lineup_info_path = os.path.join(os.curdir, lineup_info_path)

        self.log_message("Finalizing schedule for {0}".format(self.schedule_start_datetime.strftime("%c")))

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

        if os.path.exists(lineup_info_path):
            os.remove(lineup_info_path)

        with open(lineup_info_path, "x") as broadcast_lineup_outfile:
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
                    scan_entry = m3u_reader_collection[scan_series].read_next_playlist_entry(pop=self.pop_entries)

                    scan_entry_length =  timedelta(seconds=int(scan_entry["m3u_duration"]))
                    scan_entry_file = scan_entry["file_path"]

                    entry_end_time = hour_scan_time + scan_entry_length

                    lineup_line_entry = "{0} - {1} | {2} : {3}{4}".format(hour_scan_time.strftime("%I:%M:%S %p"), entry_end_time.strftime("%I:%M:%S %p"), hour_key, scan_entry_file, SHELL_NEWLINE)
                    self.log_message(lineup_line_entry.strip())
                    broadcast_lineup_outfile.writelines([lineup_line_entry,])

                    filter_flags = ""
                    realtime_flag = "-re"
                    # -preset veryfast
                    output_flags = "-vcodec libx264 -c:a aac -b:a 400k -channel_layout 5.1 -g 15 -strict experimental -f flv {0}".format(self.rtmp_endpoint)

                    if "ffmpegFilterFlags" in scan_series_data:
                        filter_flags = scan_series_data["ffmpegFilterFlags"]
                        output_flags = "-crf 28 {0}".format(output_flags)
                        realtime_flag = ""

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

        self.log_message("{0} created for: {1} ".format(self.broadcast_lineup_path, schedule.schedule_date.strftime("%A %m/%d/%Y") ) )
        self.log_message("{0}'s lineup will terminate @ {1}".format(self.day_of_week, self.schedule_end_datetime))

        for series_key in series_counts.keys():
            if self.pop_entries:
                self.log_message("Saving popped playlist for {0}".format(series_key))
                m3u_reader_collection[series_key].save_popped_playlist()

    def log_message(self, message="Hello, developer!", level="info"):
        if level not in ("info", "warn", "error"):
            level = datetime.now().strftime("%I:%M %p")
        else:
            level = level.capitalize()

        print("[{0}] {1}".format(level.upper(), message))

# Entrypoint
print("░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▒▒░░▒▒▒▒▒▒▒▒░░▒▒▓▓░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▒▒░░▒▒▒▒▒▒▒▒░░▒▒▓▓░░TELEVISION░░░░░░░░░░")
print("░░▓▓▒▒▒▒░░░░░░░░▒▒▒▒▓▓░░E X E C U T I V E░░░")
print("░░▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░")
print("░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░by Nodebay░░░░░░░░░░")
print("░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░")

begin_time = None
broadcast_option = ''

broadcast_option = input(">> Start broadcast after lineup build? (Y/N): ").strip().lower()

while broadcast_option not in ('y', 'n'):
    print("Invalid selection: {0}".format(broadcast_option))
    broadcast_option = input(">> Start broadcast after lineup build? (Y/N): ").strip().lower()

try:
    startup_datetime_in = input(">> Enter today's startup time (HH:MM:SS AM/PM): ")
    begin_time = datetime.strptime(startup_datetime_in, "%I:%M:%S %p").time()
except:
    print(">> Invalid time (must be HH:MM:SS AM/PM): {0}".format(startup_datetime_in))
    print(">> Using datetime.now() ...")
    begin_time = datetime.now().time()

if broadcast_option == "n":
    pop_playlist_entries = False
else:
    pop_playlist_entries = True
schedule_startup_time = datetime.combine(datetime.now().date(), begin_time)
schedule = DaySchedule(schedule_startup_time, pop_entries=pop_playlist_entries)

schedule.genday()
schedule.validday()

if broadcast_option == "y":
    if schedule_startup_time > datetime.now():
        sleepdelta = schedule_startup_time - datetime.now()
        schedule.log_message("Sleeping until: {0} for {1}s ".format(schedule_startup_time.strftime("%A, %I:%M:%S %p"), sleepdelta.seconds), "INFO")
        time.sleep(sleepdelta.seconds)

    if os.path.exists(schedule.broadcast_lineup_path):
        schedule.log_message("Starting lineup: {0}".format(schedule.broadcast_lineup_path ) )

    # TODO: Assemble commands on-the-fly by reading from schedule.lineup
    for entry in schedule.lineup.keys():
        ffmpeg_subprocess = subprocess.Popen(schedule.lineup[entry]["ffmpeg_command"], shell=True, cwd=os.curdir)
        stdout, stderr = ffmpeg_subprocess.communicate()

    while True:
        schedule_startup_time = schedule.schedule_end_datetime

        schedule = DaySchedule(schedule_startup_time)
        schedule.genday()
        schedule.validday()

        if schedule_startup_time > datetime.now():
            sleepdelta = schedule_startup_time - datetime.now()
            schedule.log_message("Sleeping until: {0} for {1}s ".format(schedule_startup_time.strftime("%A, %I:%M:%S %p"), sleepdelta.seconds), "INFO")
            time.sleep(sleepdelta.seconds)

        if os.path.exists(schedule.broadcast_lineup_path):
            schedule.log_message("Starting lineup: {0}".format(schedule.broadcast_lineup_path ) )

        for entry in schedule.lineup.keys():
            ffmpeg_subprocess = subprocess.Popen(schedule.lineup[entry]["ffmpeg_command"], shell=True, cwd=os.curdir)
            stdout, stderr = ffmpeg_subprocess.communicate()
else:
    exit()
