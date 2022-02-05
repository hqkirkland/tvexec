import json
import os
import subprocess
import time

from datetime import datetime, timedelta

from lineup import DAY_KEYFMT, DAYS_OF_WEEK, LineupCalendar
from scheduler import StreamScheduler
from M3UReader import M3UReader
from commander import FFMPEGCommander

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
print("░░▓▓▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▒▓▓░░I I░(2.0)░░░░░░░░░░░")
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
    do_broadcast = False
else:
    do_broadcast = True

startup_datetime_in = input(">> Enter today's startup time (HH:MM:SS AM/PM): ")

try:
    begin_time = datetime.strptime(startup_datetime_in, "%I:%M:%S %p").time()
except:
    print(">> Empty/invalid time (HH:MM:SS AM/PM)")
    begin_time = datetime.now().time()

schedule_startup_time = datetime.combine(datetime.now().date(), begin_time)

if schedule_startup_time > datetime.now():
    sleepdelta = schedule_startup_time - datetime.now()
    print(">> Sleeping until: {0} for {1}s ".format(schedule_startup_time.strftime("%A, %I:%M:%S %p"), sleepdelta.seconds))
    time.sleep(sleepdelta.seconds)

lineup = LineupCalendar()
commander = FFMPEGCommander(lineup)
scan_datetime = schedule_startup_time

while True:
    scheduler = StreamScheduler(lineup)
    scan_end_datetime = scan_datetime.replace(minute=59, second=59)

    plan_datetime = scan_datetime
    
    lineup_info_path = "broadcast_debug_{0}.txt".format(scan_datetime.strftime("%Y%m%d"))
    lineup_info_path = os.path.join(os.curdir, lineup_info_path)

    with open(lineup_info_path, "a") as broadcast_lineup_outfile:
        day_of_week = DAYS_OF_WEEK[plan_datetime.weekday()]
        broadcast_lineup_outfile.writelines(["Broadcast Plan for {0} @ {1}{2}".format(day_of_week, plan_datetime.strftime("%I:%M %p"), SHELL_NEWLINE)])
        day_plan = scheduler.read_day(plan_datetime)
        for plan_entry in day_plan: 
            lineup_line_entry = "{0} - {1} | {2}{3}".format(plan_entry["start_datetime"].strftime("%I:%M:%S %p"), plan_entry["end_datetime"].strftime("%I:%M:%S %p"), plan_entry["file_path"], SHELL_NEWLINE)
            broadcast_lineup_outfile.writelines(lineup_line_entry)

    if not do_broadcast:
        exit()
    
    slot_key = 0
    slot_entry = None
    scan_hour = scan_datetime.hour

    while scan_datetime < scan_end_datetime:       
        if scan_hour != scan_datetime.hour:
            scan_hour = scan_datetime.hour
            slot_key = 0
        
        elif slot_key > len(scheduler.lineup_calendar.read_block_by_datetime(scan_datetime)):
            slot_key = 0

        try_entry = scheduler.query_calendar(scan_datetime, slot_key)
        slot_entry = try_entry
        
        scan_entry = M3UReader(scheduler.lineup_calendar.m3u_reader_collection[slot_entry]).read_next_playlist_entry(True)

        scan_entry_title = scan_entry["entry_title"]
        scan_entry_file = scan_entry["file_path"]
        scan_entry_length = timedelta(seconds=int(scan_entry["m3u_duration"]))
        
        ffmpeg_command = commander.build_cmd(slot_entry, scan_entry_file, scan_entry_length)

        ffmpeg_subprocess = subprocess.Popen(ffmpeg_command, shell=True, cwd=os.curdir)
        stdout, stderr = ffmpeg_subprocess.communicate()
        scheduler.lineup_calendar.m3u_reader_collection[slot_entry].save_popped_playlist()

        slot_key += 1
        scan_datetime += scan_entry_length