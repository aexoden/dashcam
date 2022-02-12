import datetime
import re
import subprocess
import sys

from dataclasses import dataclass
from typing import cast, Optional


@dataclass
class LogEntry:
    latitude: float
    longitude: float
    speed: float


def read_offset(filename: str):
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


def extract_sentences(filename: str):
    offset, size = read_offset(filename)

    with open(filename, 'rb') as f:
        f.seek(offset)
        data = f.read(size)

    for index in range(28, len(data), 132):
        yield(decode_block(data[index:index + 132]))


def decode_block(block: bytes):
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


def extract_log(filename: str):
    log: list[tuple[int, Optional[datetime.datetime], Optional[float], Optional[float], Optional[float]]] = []
    base_ts: int = 0
    base_ts_shift: int = 0

    for block_index, sentence in enumerate(extract_sentences(filename)):
        try:
            matches = re.search('(.*) (N|S):([0-9.]*) (E|W):([0-9.]*) ([0-9.]*) km/h', sentence)

            if matches:
                date = datetime.datetime.strptime(matches.group(1), '%Y/%m/%d %H:%M:%S')
                latitude = float(matches.group(3))
                longitude = float(matches.group(5))
                speed = (float(matches.group(6)) * 1.852) / 1.609344

                real_latitude = (latitude // 10) * 10.0 + (longitude % 10 * 1.524855)
                real_longitude = (longitude // 10) * 10.0 + (latitude % 10 * 1.524855)

                if matches.group(2) == 'S':
                    real_latitude *= -1

                if matches.group(4) == 'W':
                    real_longitude *= -1

                if base_ts == 0:
                    base_ts = int(date.timestamp() - base_ts_shift)

                log.append((block_index, date, real_latitude, real_longitude, speed))
            else:
                print(f'ERROR: Unknown sentence {sentence}')
                sys.exit(1)
        except Exception:
            log.append((block_index, None, None, None, None))

        base_ts_shift += 1

    samples: list[tuple[int, float, float, float]] = []

    for index in range(len(log)):
        if (index > 0 and log[index][1:] == log[index - 1][1:]) or not log[index][1]:
            continue

        date = cast(datetime.datetime, log[index][1])
        latitude = cast(float, log[index][2])
        longitude = cast(float, log[index][3])
        speed = cast(float, log[index][4])

        ts = date.timestamp()

        samples.append((int(ts - base_ts), latitude, longitude, speed))

    for index in range(len(log)):
        exact = None
        next_oldest_2 = None
        next_oldest_1 = None
        next_newest_1 = None
        next_newest_2 = None

        for sample in samples:
            if sample[0] == index:
                exact = sample

            if sample[0] < index:
                next_oldest_2 = next_oldest_1
                next_oldest_1 = sample

            if sample[0] > index:
                if not next_newest_1:
                    next_newest_1 = sample
                elif not next_newest_2:
                    next_newest_2 = sample

        if exact:
            yield(LogEntry(exact[1], exact[2], exact[3]))
        elif next_oldest_1 and next_newest_1:
            dt = next_newest_1[0] - next_oldest_1[0]
            dy = (next_newest_1[1] - next_oldest_1[1]) / dt
            dx = (next_newest_1[2] - next_oldest_1[2]) / dt
            dv = (next_newest_1[3] - next_oldest_1[3]) / dt
            my_dt = index - next_oldest_1[0]
            yield(LogEntry(next_oldest_1[1] + dy * my_dt, next_oldest_1[2] + dx * my_dt, next_oldest_1[3] + dv * my_dt))
        elif next_oldest_1 and next_oldest_2:
            dt = next_oldest_1[0] - next_oldest_2[0]
            dy = (next_oldest_1[1] - next_oldest_2[1]) / dt
            dx = (next_oldest_1[2] - next_oldest_2[2]) / dt
            dv = (next_oldest_1[3] - next_oldest_2[3]) / dt
            my_dt = index - next_oldest_1[0]
            yield(LogEntry(next_oldest_1[1] + dy * my_dt, next_oldest_1[2] + dx * my_dt, next_oldest_1[3] + dv * my_dt))
        elif next_newest_1:
            yield(LogEntry(next_newest_1[1], next_newest_1[2], next_newest_1[3]))
        else:
            print('ERROR: Broken GPS log')
            sys.exit(1)
