import os

class M3UReader:
    def __init__(self, m3u_file_path, series_key=None):
        self.playlist_entries = []
        self.m3u_file_path = m3u_file_path
        self.m3u_cursor = 0

        if not os.path.isfile(self.m3u_file_path):
            return
        
        with open(self.m3u_file_path, "r+") as series_m3u:
            m3u_lines = series_m3u.readlines()                    
            for i in range(0, len(m3u_lines)):
                m3u_line = m3u_lines[i].strip()

                if m3u_line == "#EXTM3U":
                    continue
                    # m3u_line = series_m3u.readline().strip()
                    # Start M3U Entry Cursor @ 1
                
                if m3u_line.startswith("#EXTINF"):
                    m3u_segments = m3u_line.split(':', 1)[1].split(',')
                    length_segment = m3u_segments[0]
                    
                    episode_len = int(length_segment)
                    episode_file_path = m3u_lines[i + 1].strip()
                    episode_title = m3u_segments[1]

                    if os.path.isfile(episode_file_path):
                        self.playlist_entries.append({
                            "entry_title": episode_title,
                            "m3u_duration": episode_len,
                            "file_path": os.path.normpath(episode_file_path),
                        })
    
    def read_next_playlist_entry(self, pop=True):
        if pop:
            next_playlist_entry = self.playlist_entries.pop(0)
            self.playlist_entries.append(next_playlist_entry)
        elif self.m3u_cursor < len(self.playlist_entries):
            next_playlist_entry = self.playlist_entries[self.m3u_cursor]
            self.m3u_cursor += 1
        else:
            self.m3u_cursor = 0
            next_playlist_entry = self.playlist_entries[self.m3u_cursor]
        return next_playlist_entry

    def save_popped_playlist(self):
        if os.path.isfile(self.m3u_file_path):
            os.remove(self.m3u_file_path)
        
        with open(self.m3u_file_path, "x") as series_m3u:
            series_m3u.writelines(("#EXTM3U" + '\n',))
            # Reset the cursor.
            # If we've been poppin', 
            # then the cursor will start at the *next* unaired episode of series.
            # Else, cursor will start at today's first episode of series.
            self.m3u_cursor = 0
            for entry in self.playlist_entries:
                episode_title = entry["entry_title"]
                episode_title = "#EXTINF:{0},{1}\n".format(str(int(entry["m3u_duration"])), episode_title)
                
                series_m3u.writelines((episode_title, entry["file_path"] + '\n\n'))
                self.m3u_cursor += 1
