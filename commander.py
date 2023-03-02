from lineup import LineupCalendar

class FFMPEGCommander(object):
    def __init__(self, lineup_calendar: LineupCalendar, rtmp_ept="rtmp://127.0.0.1/show/stream"):
        self.lineup_calendar = lineup_calendar
        self.rtmp_endpoint = rtmp_ept
    
    def build_cmd(self, series_key, file_path, duration):
        scan_series_data = self.lineup_calendar.series_list[series_key]

        filter_flags = ""

        if "formatFlags" in scan_series_data:
            override_format_flags = str(scan_series_data["formatFlags"]).strip('\r').strip('\n') 
            format_flags = "{0} -f flv {1}".format(override_format_flags, self.rtmp_endpoint)
        
        # Hack for Frasier, other videos that use super-HQ x265 encoding.
        elif file_path.__contains__("x265"):
            override_format_flags = "-vcodec libx264 -c:a aac -b:a 400k -channel_layout 5.1 -b:v 56k -bufsize 56k -g 25 -strict experimental -crf 31"
            format_flags = "{0} -f flv {1}".format(override_format_flags, self.rtmp_endpoint)

        else:
            format_flags = "-vcodec libx264 -c:a aac -b:a 400k -channel_layout 5.1 -g 15 -strict experimental -f flv {0}".format(self.rtmp_endpoint)

        if "ffmpegFilterFlags" in scan_series_data:
            filter_flags = scan_series_data["ffmpegFilterFlags"]

            if series_key == "Lineup":
                scrolltext = False
                with open(r"listings.txt", 'r') as fp:
                    for count, line in enumerate(fp):
                        pass
                    count += 1
                    if count > 20:
                        # Horrible, but necessary, patch to test scrolling text above certain file length.
                        filter_flags = "-filter_complex \"loudnorm=I=-23;drawtext=fontfile=/home/hunter/NetLibrary/Teletactile-3zavL.ttf:textfile=/home/hunter/tvexec/listings.txt:x=100:y=h-mod(t * 45\, h + th):fontcolor=0xFFFFFF:fontsize=34:line_spacing=2, drawbox=x=0:y=0:w=iw:h=75:color=0x0094FF@1:t=fill,drawtext=fontfile=/home/hunter/NetLibrary/Teletactile-3zavL.ttf:text='* K409 LISTINGS *': x=(w-tw)/2:y=36:fontcolor=white:fontsize=36\""

            str(filter_flags).replace('\r', '')
            str(filter_flags).replace('\n', '')
        
        else:
            filter_flags = "-filter_complex \"loudnorm=I=-23\""

        return "ffmpeg -re -i \"{0}\" {1} {2}".format(file_path, filter_flags, format_flags)

