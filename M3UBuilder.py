import os
import random
import natsort
import subprocess

EXTENSIONS_ALLOWED = ("mkv", "avi", "mp4", "m4a", "m4v", "wav", "mp3", "mpg", "")

class M3UBuilder:
    def __init__(self, series_root_directory, series_key):
        self.series_key = series_key
        self.series_path = os.path.normpath(series_root_directory)
        
        m3u_safe_series_key = self.series_key.replace(':', '')
        self.m3u_path = os.path.join(self.series_path, "{0}{1}".format(m3u_safe_series_key, ".m3u"))

    def build(self, series_playlist_type=""):
        if os.path.exists(self.m3u_path):
            return
        
        with open(self.m3u_path, "x") as series_m3u:
            series_m3u.writelines(("#EXTM3U" + '\n',))

            dirs_in_seriespath = [os.path.normpath(d) for d in os.listdir(self.series_path) if os.path.isdir(os.path.join(self.series_path, d))]
            files_in_seriespath = [os.path.normpath(f) for f in os.listdir(self.series_path) if os.path.isfile(os.path.join(self.series_path, f))]

            # This next condition likely means that the directory is split by season.
            if len(dirs_in_seriespath) > len(files_in_seriespath):
                files_in_series = ()
                for subdir in dirs_in_seriespath:
                    subdir_season_path = os.path.normpath(os.path.join(self.series_path, subdir))
                    # print("> Navigating into: {0}".format(subdir_season_path))
                    for season_episode in os.listdir(subdir_season_path):
                        # print("> Adding {0}".format(season_episode))
                        path_to_episode_file = os.path.join(subdir_season_path, season_episode)
                        if os.path.isfile(path_to_episode_file):
                            files_in_series = files_in_series + (path_to_episode_file,)

            else:
                subdir_season_path = self.series_path
                files_in_series = files_in_seriespath
            
            files_in_series = natsort.natsorted(files_in_series)

            if series_playlist_type == "shuffle":
                # print("> Shuffling playlist for: {0}".format(series_key))
                random.shuffle(files_in_series)

            for episode_file in files_in_series:
                series_m3u.writelines('\n\n')
                path_to_episode_file = os.path.normpath(os.path.join(subdir_season_path, episode_file))
                # print("Episode path: {0}".format(path_to_episode_file))

                episode_file_name = os.path.basename(path_to_episode_file)
                episode_file_extension = episode_file_name.split('.')[-1]

                # Remove file extension + extra chars.
                episode_title = episode_file_name.replace(".{0}".format(episode_file_extension), "")
                episode_title = episode_title.replace("_", " ").replace(".", " ").replace(":", "")

                if episode_file_extension not in EXTENSIONS_ALLOWED:
                    continue
                
                result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
                                        path_to_episode_file], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                clean_result = result.stdout.strip().split(b'\r')[0]
                # print("Result: {0}".format(clean_result))

                try:
                    episode_len = float(clean_result)
                except ValueError:
                    episode_len = 0.0

                episode_title_line = "#EXTINF:{0},{1}".format(str(int(episode_len)), episode_title)
                print(">> {0}".format(episode_title_line))
                series_m3u.writelines((episode_title_line + '\n', path_to_episode_file))
