import argparse
import glob
import json
import os
import subprocess
import sys

from . import gps
from . import map as dashcam_map


def get_source_videos(args: argparse.Namespace):
    return sorted(glob.glob(os.path.join(args.directory, '*.MP4')))


def get_source_list_filename(args: argparse.Namespace):
    return os.path.join(args.directory, 'dashcam-tmp-src-list.txt')


def get_source_mkv_filename(args: argparse.Namespace):
    return os.path.join(args.directory, 'dashcam-tmp-src.mkv')


def get_source_cache_filename(args: argparse.Namespace):
    return os.path.join(args.directory, 'dashcam-tmp-src.json')


def get_frame_count(args: argparse.Namespace):
    cache_filename = get_source_cache_filename(args)

    if os.path.exists(cache_filename):
        with open(cache_filename, encoding='utf-8') as f:
            data = json.load(f)
            return data['frame_count']

    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_packets', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', get_source_mkv_filename(args)], capture_output=True, check=True)
    frame_count = int(result.stdout.strip()) // 4

    with open(cache_filename, 'w', encoding='utf-8') as f:
        json.dump({'frame_count': frame_count}, f)

    return frame_count


def generate_source_list(args: argparse.Namespace):
    output_filename = get_source_list_filename(args)

    if not os.path.exists(output_filename):
        with open(output_filename, 'w', encoding='utf-8') as f:
            for source_filename in get_source_videos(args):
                f.write(f"file '{os.path.basename(source_filename)}'\n")


def generate_decimated_video(args: argparse.Namespace, map_overlay: bool):
    source_mkv_filename = get_source_mkv_filename(args)
    map_mkv_filename = os.path.join(args.directory, 'dashcam-tmp-map.mkv') if map_overlay else 'None'
    output_filename = os.path.join(args.directory, 'dashcam-encoded-decimate.mkv')

    if not os.path.exists(output_filename):
        subprocess.run([f'vspipe vapoursynth/decimate.vpy - -c y4m -a "source={source_mkv_filename}" -a "map_source={map_mkv_filename}" | ffmpeg -i pipe: -c:v libx265 -preset slow -crf 18 {output_filename}'], shell=True, check=True)


def generate_motion_blur_video(args: argparse.Namespace, map_overlay: bool):
    source_mkv_filename = get_source_mkv_filename(args)
    map_mkv_filename = os.path.join(args.directory, 'dashcam-tmp-map.mkv') if map_overlay else 'None'
    output_filename = os.path.join(args.directory, 'dashcam-encoded-blur.mkv')

    if not os.path.exists(output_filename):
        subprocess.run([f'vspipe vapoursynth/blur.vpy - -c y4m -a "source={source_mkv_filename}" -a "map_source={map_mkv_filename}" | ffmpeg -i pipe: -c:v libx265 -preset slow -crf 18 {output_filename}'], shell=True, check=True)


def generate_source_video(args: argparse.Namespace):
    source_list_filename = get_source_list_filename(args)
    tmp_extension = 'h265' if args.camera == 'vantop' else 'h264'
    source_tmp_filename = os.path.join(args.directory, f'dashcam-tmp-src.{tmp_extension}')
    source_mkv_filename = get_source_mkv_filename(args)

    if not os.path.exists(source_mkv_filename):
        if not os.path.exists(source_tmp_filename):
            codec = 'hevc_mp4toannexb' if args.camera == 'vantop' else 'h264_mp4toannexb'
            subprocess.run(['ffmpeg', '-f', 'concat', '-i', source_list_filename, '-map', '0:v', '-c:v', 'copy', '-bsf:v', codec, source_tmp_filename], cwd=args.directory, check=True)

        subprocess.run(['ffmpeg', '-fflags', '+genpts', '-r', '25', '-i', source_tmp_filename, '-c:v', 'copy', source_mkv_filename], cwd=args.directory, check=True)
        os.remove(source_tmp_filename)


def generate_map_video(args: argparse.Namespace, frames: int):
    map_mkv_filename = os.path.join(args.directory, 'dashcam-tmp-map.mkv')

    if not os.path.exists(map_mkv_filename):
        entries: list[gps.LogEntry] = list(gps.extract_logs(get_source_videos(args), args.camera))

        if len(entries) == 0:
            return False

        adjustment = frames / len(entries)

        previous = 0
        encoder = subprocess.Popen(['ffmpeg', '-r', '60', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{dashcam_map.WIDTH}x{dashcam_map.HEIGHT}', '-i', '-', '-c:v', 'ffv1', map_mkv_filename], stdin=subprocess.PIPE)

        assert encoder.stdin is not None

        for index in range(len(entries)):
            target = int(adjustment * (index + 1) + 0.5)
            frames = target - previous

            assert entries[index] is not None

            current_entry = entries[index]
            next_entry = entries[index + 1] if index < len(entries) - 1 else current_entry

            dy = (next_entry.latitude - current_entry.latitude) / frames
            dx = (next_entry.longitude - current_entry.longitude) / frames
            dv = (next_entry.speed - current_entry.speed) / frames

            latitude = current_entry.latitude
            longitude = current_entry.longitude
            speed = current_entry.speed

            for _ in range(frames):
                image = dashcam_map.draw_frame(args.map_url, latitude, longitude, speed)
                encoder.stdin.write(image.tobytes())
                encoder.stdin.flush()

                latitude += dy
                longitude += dx
                speed += dv

            previous = target

        encoder.communicate()

    return True


def main():
    parser = argparse.ArgumentParser(description='Generate a timelapse video from dashcam videos')
    parser.add_argument('-c', '--camera', type=str, choices=['vantop', 'novatek'], default='novatek')
    parser.add_argument('directory', metavar='DIRECTORY', type=str, help='directory containing the source videos')
    parser.add_argument('map_url', metavar='MAP_URL', type=str, help='URL to the OpenStreetMap tile server')

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
    map_overlay = generate_map_video(args, frame_count)

    if not map_overlay:
        print('WARNING: No GPS data was found. Not generating map overlay.')

    print('Generating decimated video...')
    generate_decimated_video(args, map_overlay)

    print('Generating motion blur video...')
    generate_motion_blur_video(args, map_overlay)


sys.exit(main())
