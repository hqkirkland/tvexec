import json
import os
import subprocess
import time

from datetime import datetime, timedelta

from lineup import DAYS_OF_WEEK, LineupCalendar
from scheduler import StreamScheduler
from commander import FFMPEGCommander

if os.name == "nt":
    SHELL_NEWLINE = '\r\n'
else:
    SHELL_NEWLINE = '\n'

LISTINGS_EXCLUSIONS = ["Bumps", "Lineup"]

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

do_broadcast = broadcast_option == "y"
startup_datetime_in = input(">> Enter today's startup time (HH:MM:SS AM/PM): ")

try:
    begin_time = datetime.strptime(startup_datetime_in, "%I:%M:%S %p").time()
except:
    print(">> Empty/invalid time (HH:MM:SS AM/PM), using datetime.now().time()")
    begin_time = datetime.now().time()

startup_slot = 0
startup_slot_input = input(">> Startup slot number: ").strip()

if startup_slot_input.isdigit():
    startup_slot = int(startup_slot_input)

schedule_startup_time = datetime.combine(datetime.now().date(), begin_time)

if schedule_startup_time > datetime.now():
    sleepdelta = schedule_startup_time - datetime.now()
    print(">> Sleeping until: {0} for {1}s ".format(schedule_startup_time.strftime("%A, %I:%M:%S %p"), sleepdelta.seconds))
    time.sleep(sleepdelta.seconds)

scan_datetime = schedule_startup_time

lineup = LineupCalendar()
commander = FFMPEGCommander(lineup)
scheduler = StreamScheduler(lineup)

while True:
    if lineup.refresh():
        commander.lineup_calendar = lineup
        scheduler.lineup_calendar = lineup
    
    slot_key = startup_slot
    slot_entry = None
    
    scan_datetime = datetime.now()
    scan_end_datetime = scan_datetime.replace(minute=59, second=59)

    while scan_datetime < scan_end_datetime:
        day_plan = scheduler.read_day_span(scan_datetime, 12, slot_key)
        lineup_info_path = "listings.txt"
        # .format(scan_datetime.strftime("%Y%m%d@%H_%M"))
        lineup_info_path = os.path.join(os.curdir, lineup_info_path)

        with open(lineup_info_path, "w+t") as broadcast_lineup_outfile:
            broadcast_lineup_outfile.writelines(
                [
                    "{0} @ {1}{2}".format(
                        DAYS_OF_WEEK[scan_datetime.weekday()], 
                        scan_datetime.strftime("%I:%M %p"), 
                        SHELL_NEWLINE
                    )
                ]
            )
        
            for plan_entry in day_plan:
                # Do listing exclusions.
                if plan_entry["slot_entry"] in LISTINGS_EXCLUSIONS:
                    continue
                
                lineup_line_entry = "{0}: {1}{2}".format(
                    plan_entry["start_datetime"].strftime("%I:%M %p"), 
                    plan_entry["slot_entry"], 
                    SHELL_NEWLINE
                )
                broadcast_lineup_outfile.writelines(lineup_line_entry)
        
        if os.path.exists("schedule.json"):
            os.remove("schedule.json")
        
        with open("schedule.json", "x") as now_next_later_file:
            now_next_later = [ day_plan[0]["slot_entry"], day_plan[1]["slot_entry"], day_plan[2]["slot_entry"] ]
            now_next_later_file.writelines("{0}{1}".format(json.dumps(now_next_later), SHELL_NEWLINE))

        if not do_broadcast:
            exit()
             
        # Try to get new entry.
        try_entry = scheduler.query_calendar(scan_datetime, slot_key)

        if try_entry is not None:
            slot_entry = try_entry
        
        scan_entry = scheduler.lineup_calendar.m3u_reader_collection[slot_entry].read_next_playlist_entry(True)

        scan_entry_file = scan_entry["file_path"]
        scan_entry_length = timedelta(seconds=int(scan_entry["m3u_duration"]))

        if "staticDurationOverride" in lineup.series_list[slot_entry]:
            static_duration_override = lineup.series_list[slot_entry]["staticDurationOverride"]
            scan_entry_length = timedelta(seconds=int(static_duration_override))

        ffmpeg_command = commander.build_cmd(slot_entry, scan_entry_file, scan_entry_length)
        
        print("### Now Playing ###")
        print("# {0}".format(ffmpeg_command))
        print("###################")
        command_end_time = datetime.now() + scan_entry_length

        ffmpeg_subprocess = subprocess.Popen(ffmpeg_command, shell=True, cwd=os.curdir)
        stdout, stderr = ffmpeg_subprocess.communicate()\
        
        if  command_end_time - datetime.now() > timedelta(minutes=1):
            print("Warning! Command completed far ahead of schedule; pausing. Press any key to continue.")
            input()
        
        scheduler.lineup_calendar.m3u_reader_collection[slot_entry].save_popped_playlist()
        day_plan.pop(0)
        slot_key += 1
        scan_datetime += scan_entry_length

        startup_slot = 0