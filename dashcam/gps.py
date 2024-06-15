import datetime
import re
import struct
import subprocess
import sys

from dataclasses import dataclass
from typing import Generator, Optional


@dataclass
class LogEntry:
    latitude: float
    longitude: float
    speed: float


def read_offset_novatek(filename: str):
    offset: int = 0
    size: int = 0
    read_offset = False

    output = subprocess.check_output(['exiftool', '-v3', filename]).decode('utf-8').split('\n')

    for line in output:
        if read_offset:
            matches = re.search(r'([0-9a-f]+):.*', line)

            if matches:
                offset = int(matches.group(1), 16)

            read_offset = False

        matches = re.search(r"Tag 'gps '.*\(([0-9]+) bytes", line)

        if matches:
            size = int(matches.group(1))
            read_offset = True

    return offset, size


def read_offset_vantop(filename: str):
    offset: int = 0
    size: int = 0

    output = subprocess.check_output(['exiftool', '-v3', filename]).decode('utf-8').split('\n')

    for line in output:
        matches = re.search(r'([0-9a-f]*):.*LIGOGPSINFO', line)

        if matches:
            offset = int(matches.group(1), 16)

        matches = re.search(r'Tag.*skip.*\(([0-9]*) bytes', line)

        if matches:
            size = int(matches.group(1))

    return offset, size


def convert_coordinate(coordinate: float):
    minutes = coordinate % 100
    degrees = (coordinate - minutes) / 100

    return degrees + (minutes / 60)


def decode_block_novatek(block: bytes):
    hour, minute, second, year, month, day = struct.unpack_from('<IIIIII', block, 0)
    year += 2000

    ns = chr(block[25])
    ew = chr(block[26])

    latitude, longitude, speed, = struct.unpack_from('<fff', block, 28)

    latitude = convert_coordinate(latitude)
    longitude = convert_coordinate(longitude)

    timestamp = f'{year:04}/{month:02}/{day:02} {hour:02}:{minute:02}:{second:02}'
    coordinates = f'{ns}:{latitude} {ew}:{longitude} {speed} km/h'

    return f'{timestamp} {coordinates}'


def decode_block_vantop(block: bytes):
    output: list[int] = []

    index = 0
    while index < 120:
        byte = block[index]
        test_byte = byte & 0xE0

        if test_byte == 0:
            output.append((byte & 0x13) | block[index + 1])
            index += 2
        elif test_byte == 0x40:
            output.append(0x20)
            output.append(((byte & 0x01) | block[index + 1]) ^ 0x20)
            output.append(((byte & 0x06) | block[index + 2]) ^ 0x20)
            output.append(((byte & 0x18) | block[index + 3]) ^ 0x20)
            index += 4
        elif test_byte == 0x60:
            output.append(((byte & 0x03) | block[index + 1]) ^ 0x20)
            output.append(0x20)
            output.append(((byte & 0x04) | block[index + 2]) ^ 0x20)
            output.append(((byte & 0x18) | block[index + 3]) ^ 0x20)
            index += 4
        elif test_byte == 0x80:
            output.append(((byte & 0x03) | block[index + 1]) ^ 0x20)
            output.append(((byte & 0x0C) | block[index + 2]) ^ 0x20)
            output.append(0x20)
            output.append(((byte & 0x10) | block[index + 3]) ^ 0x20)
            index += 4
        elif test_byte == 0xA0:
            output.append(((byte & 0x01) | block[index + 1]) ^ 0x20)
            output.append(((byte & 0x06) | block[index + 2]) ^ 0x20)
            output.append(((byte & 0x18) | block[index + 3]) ^ 0x20)
            output.append(0x20)
            index += 4
        else:
            if byte & 0xC0 == 0:
                print(f'WARNING: Unknown byte {byte:02X} and test_byte {test_byte:02X}')
                sys.exit(1)
            else:
                output.append(((byte & 0x01) | block[index + 1]) ^ 0x20)
                output.append(((byte & 0x02) | block[index + 2]) ^ 0x20)
                output.append(((byte & 0x0C) | block[index + 3]) ^ 0x20)
                output.append(((byte | (~block[index + 4] & 0xEF)) & 0x30) | block[index + 4] & 0xDF)
                index += 5

    return ''.join([chr(x) for x in output[4:]])


def extract_sentences_novatek(filename: str):
    offset, size = read_offset_novatek(filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        data = f.read(size)

    for index in range(8, len(data), 8):
        block_offset = struct.unpack_from('>I', data, index)[0]
        block_size = struct.unpack_from('>I', data, index + 4)[0]

        with open(filename, 'rb') as f:
            f.seek(block_offset)
            block_data = f.read(block_size)

        if block_data[8:12].decode('utf-8') != 'GPS ':
            yield None
            continue

        block_index = 12
        result = None

        while block_index < len(block_data) - 44:
            test_latitude = chr(block_data[block_index + 25])
            test_longitude = chr(block_data[block_index + 26])

            if test_latitude in ['N', 'S'] and test_longitude in ['E', 'W']:
                result = decode_block_novatek(block_data[block_index:block_index + 44])
                break

            block_index += 1

        yield result


def extract_sentences_vantop(filename: str):
    offset, size = read_offset_vantop(filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        data = f.read(size)

    for index in range(28, len(data), 132):
        yield decode_block_vantop(data[index:index + 132])


def extract_log(filename: str, log_type: str) -> Generator[Optional[LogEntry], None, None]:
    last_timestamp: Optional[datetime.datetime] = None
    base_timestamp: Optional[datetime.datetime] = None
    base_timestamp_offset = 0

    entry_count = 0
    sentence_count = 0

    for sentence in extract_sentences_vantop(filename) if log_type == 'vantop' else extract_sentences_novatek(filename):
        sentence_count += 1

        try:
            matches = re.search(r'(.*) (N|S):([0-9.]*) (E|W):([0-9.]*) ([0-9.]*) km/h', sentence)

            if matches:
                timestamp = datetime.datetime.strptime(matches.group(1), '%Y/%m/%d %H:%M:%S')
                latitude = float(matches.group(3))
                longitude = float(matches.group(5))
                speed = (float(matches.group(6)) * 1.852) / 1.609344

                if not base_timestamp:
                    base_timestamp = timestamp
                    base_timestamp_offset = entry_count

                target_index = int((timestamp - base_timestamp).total_seconds()) + base_timestamp_offset

                while entry_count < target_index:
                    entry_count += 1
                    yield None

                if timestamp == last_timestamp:
                    continue

                last_timestamp = timestamp

                if log_type == 'vantop':
                    real_latitude = (latitude // 10) * 10.0 + (longitude % 10 * 1.524855)
                    real_longitude = (longitude // 10) * 10.0 + (latitude % 10 * 1.524855)
                else:
                    real_latitude = latitude
                    real_longitude = longitude

                if matches.group(2) == 'S':
                    real_latitude *= -1

                if matches.group(4) == 'W':
                    real_longitude *= -1

                entry_count += 1

                yield LogEntry(real_latitude, real_longitude, speed)
            else:
                print(f'ERROR: Unknown sentence {sentence}')
                sys.exit(1)
        except Exception:
            entry_count += 1
            yield None

    while entry_count < sentence_count:
        entry_count += 1
        yield None

    if sentence_count == 0:
        print(f'WARNING: {filename} had zero GPS sentences.')


def extract_logs(filenames: list[str], log_type: str) -> Generator[LogEntry, None, None]:
    entries: list[Optional[LogEntry]] = []

    for filename in filenames:
        entries.extend(list(extract_log(filename, log_type)))

    previous_entry: Optional[LogEntry] = None
    previous_index = -1

    interpolation_active = False
    base_index = None
    base_x = None
    base_y = None
    base_v = None
    dx = None
    dy = None
    dv = None

    for index, entry in enumerate(entries):
        if entry:
            previous_entry = entry
            previous_index = index
            interpolation_active = False
            yield entry
        else:
            next_entry: Optional[LogEntry] = None
            next_index = len(entries)

            for sub_index in range(index, len(entries)):
                if entries[sub_index]:
                    next_entry = entries[sub_index]
                    next_index = sub_index
                    break

            if not interpolation_active:
                if previous_entry is not None and next_entry is None:
                    yield previous_entry
                elif previous_entry is None and next_entry is not None:
                    yield next_entry
                elif previous_entry is not None and next_entry is not None:
                    interpolation_active = True
                    dt = next_index - previous_index
                    dx = (next_entry.longitude - previous_entry.longitude) / dt
                    dy = (next_entry.latitude - previous_entry.latitude) / dt
                    dv = (next_entry.speed - previous_entry.speed) / dt
                    base_index = previous_index
                    base_x = previous_entry.longitude
                    base_y = previous_entry.latitude
                    base_v = previous_entry.speed
                else:
                    print('ERROR: No GPS data found')
                    sys.exit(1)

            if interpolation_active:
                assert base_index is not None
                assert base_x is not None
                assert base_y is not None
                assert base_v is not None
                assert dx is not None
                assert dy is not None
                assert dv is not None

                index_delta: int = index - base_index
                yield LogEntry(base_y + index_delta * dy, base_x + index_delta * dx, base_v + index_delta * dv)
