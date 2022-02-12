import argparse
import glob
import os
import subprocess
import sys

import progressbar

from . import gps, map


def get_source_videos(args: argparse.Namespace):
    return sorted(glob.glob(os.path.join(args.directory, '*.MP4')))


def get_source_list_filename(args: argparse.Namespace):
    return os.path.join(args.directory, 'dashcam-tmp-src-list.txt')


def get_source_mkv_filename(args: argparse.Namespace):
    return os.path.join(args.directory, 'dashcam-tmp-src.mkv')


def get_frame_count(args: argparse.Namespace):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', get_source_mkv_filename(args)], capture_output=True)
    return int(result.stdout.strip()) // 4


def generate_source_list(args: argparse.Namespace):
    output_filename = get_source_list_filename(args)

    if not os.path.exists(output_filename):
        with open(output_filename, 'w') as f:
            for source_filename in get_source_videos(args):
                f.write(f"file '{os.path.basename(source_filename)}'\n")


def generate_decimated_video(args: argparse.Namespace):
    source_mkv_filename = get_source_mkv_filename(args)
    map_mkv_filename = os.path.join(args.directory, 'dashcam-tmp-map.mkv')
    output_filename = os.path.join(args.directory, 'dashcam-encoded-decimate.mkv')

    if not os.path.exists(output_filename):
        subprocess.run([f'PATH=/usr/bin vspipe vapoursynth/decimate.vpy - -y -a "source={source_mkv_filename}" -a "map_source={map_mkv_filename}" | ffmpeg -i pipe: -c:v libx265 -preset slow -crf 18 {output_filename}'], shell=True, check=True)


def generate_source_video(args: argparse.Namespace):
    source_list_filename = get_source_list_filename(args)
    source_h265_filename = os.path.join(args.directory, 'dashcam-tmp-src.h265')
    source_mkv_filename = get_source_mkv_filename(args)

    if not os.path.exists(source_mkv_filename):
        if not os.path.exists(source_h265_filename):
            subprocess.run(['ffmpeg', '-f', 'concat', '-i', source_list_filename, '-map', '0:v', '-c:v', 'copy', '-bsf:v', 'hevc_mp4toannexb', source_h265_filename], cwd=args.directory, check=True)

        subprocess.run(['ffmpeg', '-fflags', '+genpts', '-r', '25', '-i', source_h265_filename, '-c:v', 'copy', source_mkv_filename], cwd=args.directory, check=True)
        os.remove(source_h265_filename)


def generate_map_video(args: argparse.Namespace, frames: int):
    map_mkv_filename = os.path.join(args.directory, 'dashcam-tmp-map.mkv')
    entries: list[gps.LogEntry] = []

    if not os.path.exists(map_mkv_filename):
        for source_filename in get_source_videos(args):
            for entry in gps.extract_log(source_filename):
                entries.append(entry)

        adjustment = frames / len(entries)

        previous = 0
        file_index = 0
        filenames: list[str] = []

        for index in progressbar.progressbar(range(len(entries))):
            target = int(adjustment * (index + 1) + 0.5)
            frames = target - previous

            assert entries[index] is not None

            current_entry = entries[index]
            next_entry = entries[index + 1] if index < len(entries) - 1 else current_entry

            dy = (next_entry.latitude - current_entry.latitude) / frames
            dx = (next_entry.longitude - current_entry.longitude) / frames

            latitude = current_entry.latitude
            longitude = current_entry.longitude
            speed = current_entry.speed

            for _ in range(frames):
                filename = f'{args.directory}/dashcam-tmp-map-{file_index:08}.png'
                filenames.append(filename)

                if not os.path.exists(filename):
                    image = map.draw_frame(args.map_url, latitude, longitude, speed)
                    image.save(filename)

                latitude += dy
                longitude += dx
                file_index += 1

            previous = target

        subprocess.run(['ffmpeg', '-r', '60', '-f', 'image2', '-i', f'{args.directory}/dashcam-tmp-map-%08d.png', '-c:v', 'ffv1', map_mkv_filename], check=True)

        for filename in filenames:
            os.remove(filename)


def main():
    parser = argparse.ArgumentParser(description='Generate a timelapse video from dashcam videos')
    parser.add_argument('map_url', metavar='MAP_URL', type=str, help='URL to the OpenStreetMap tile server')
    parser.add_argument('directory', metavar='DIRECTORY', type=str, help='directory containing the source videos')

    args = parser.parse_args()

    if not os.path.exists(args.directory):
        print(f'ERROR: {args.directory} does not exist')
        return 1

    print('Generating source file list...')
    generate_source_list(args)

    print('Generating source video...')
    generate_source_video(args)

    print('Calculating target number of frames...', end='')
    frame_count = get_frame_count(args)
    print(f' {frame_count}')

    print('Generating map overlay video...')
    generate_map_video(args, frame_count)

    print('Generating decimated video...')
    generate_decimated_video(args)


sys.exit(main())