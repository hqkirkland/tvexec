import os
import subprocess
import time

from datetime import datetime

from schedule2 import HourSchedule

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'

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

if broadcast_option == "n":
    pop_playlist_entries = False
else:
    pop_playlist_entries = True

startup_datetime_in = input(">> Enter today's startup time (HH:MM:SS AM/PM): ")

try:
    begin_time = datetime.strptime(startup_datetime_in, "%I:%M:%S %p").time()
except:
    print(">> Empty/invalid time (HH:MM:SS AM/PM)")
    begin_time = datetime.now().time()

schedule_startup_time = datetime.combine(datetime.now().date(), begin_time)

while True:
    schedule = HourSchedule(schedule_startup_time, pop_entries=pop_playlist_entries)
    schedule.genhour()
    schedule.validhour()

    if schedule_startup_time > datetime.now():
        sleepdelta = schedule_startup_time - datetime.now()
        schedule.log_message("Sleeping until: {0} for {1}s ".format(schedule_startup_time.strftime("%A, %I:%M:%S %p"), sleepdelta.seconds), "INFO")
        time.sleep(sleepdelta.seconds)

    if os.path.exists(schedule.broadcast_lineup_path):
        schedule.log_message("Starting lineup: {0}".format(schedule.broadcast_lineup_path ) )

    if broadcast_option == "y":
        for entry in schedule.lineup.keys():
            ffmpeg_subprocess = subprocess.Popen(schedule.lineup[entry]["ffmpeg_command"], shell=True, cwd=os.curdir)
            stdout, stderr = ffmpeg_subprocess.communicate()
            schedule.savehour()
        
        schedule_startup_time = schedule.schedule_end_datetime

    else:
        exit()