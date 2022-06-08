from lineup import LineupCalendar

class FFMPEGCommander(object):
    def __init__(self, lineup_calendar: LineupCalendar, rtmp_ept="rtmp://127.0.0.1/show/stream"):
        self.lineup_calendar = lineup_calendar
        self.rtmp_endpoint = rtmp_ept
    
    def build_cmd(self, series_key, file_path, duration):
        scan_series_data = self.lineup_calendar.series_list[series_key]

        filter_flags = ""

        if "formatFlags" in scan_series_data:
            override_format_flags = scan_series_data["formatFlags"]
            str(override_format_flags).replace('\r', '')
            str(override_format_flags).replace('\n', '')
            format_flags = "{0} -f flv {1}".format(override_format_flags, self.rtmp_endpoint)

        else:
            format_flags = "-vcodec libx264 -c:a aac -b:a 400k -channel_layout 5.1 -g 15 -strict experimental -f flv {0}".format(self.rtmp_endpoint)

        if "ffmpegFilterFlags" in scan_series_data:
            filter_flags = scan_series_data["ffmpegFilterFlags"]
            str(filter_flags).replace('\r', '')
            str(filter_flags).replace('\n', '')
        
        else:
            filter_flags = "-filter_complex \"loudnorm=I=-23\""

        return "ffmpeg -re -i \"{0}\" {1} {2}".format(file_path, filter_flags, format_flags)

