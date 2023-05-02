# TVExec
An experiment in channel programming, networking, and streaming.

Requirements:
* Python3
* FFMPEG Suite (ffmpeg, ffprobe)

Usage:
1. Configure `series_config.json` file to point to media directories.
2. On startup, M3Us are generated for each episode in media; `ffprobe` required, in order to get length.
3. Configure `lineup.json` file to create an ordered schedule of series as defined from `series_config.json`
4. Lineup keys work by the loop "landing" on the current day & hour-block, and playing 1-2-3 etc. until show lapses and current time rolls into next hour.
5. `ffmpeg` command-builder automates the schedule based on the lineup file.
6. Special "Lineup" key can be used to generate & output listings file.
