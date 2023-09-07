import math
import mercantile
import requests

from PIL import Image, ImageDraw, ImageFont

WIDTH = 384
HEIGHT = 224


def fetch_map(osm_url: str, latitude: float, longitude: float, zoom: float):
    full_image = Image.new('RGBA', (256 * 3, 256 * 3))

    int_zoom = round(zoom)
    frac_zoom = zoom - int_zoom

    tiles = [mercantile.tile(longitude, latitude, int_zoom)]
    tiles.extend(mercantile.neighbors(tiles[0]))

    for tile in tiles:
        tile_url = f'{osm_url}{tile.z}/{tile.x}/{tile.y}.png'

        while True:
            try:
                image = Image.open(requests.get(tile_url, stream=True).raw)
                break
            except Exception:
                pass

        if tile.x < tiles[0].x:
            x = 0
        elif tile.x == tiles[0].x:
            x = 1
        else:
            x = 2

        if tile.y < tiles[0].y:
            y = 0
        elif tile.y == tiles[0].y:
            y = 1
        else:
            y = 2

        x = x * 256
        y = y * 256

        full_image.paste(image, (x, y))

    resize_factor = math.pow(2, -frac_zoom)

    bounds = mercantile.bounds(tiles[0])
    center_y = 256 + int(((latitude - bounds.north) / (bounds.south - bounds.north)) * 256 + 0.5)
    center_x = 256 + int(((longitude - bounds.west) / (bounds.east - bounds.west)) * 256 + 0.5)

    width = int(WIDTH * resize_factor)
    height = int(HEIGHT * resize_factor)

    if width % 2 == 1:
        width = width - 1
    if height % 2 == 1:
        height = height - 1

    crop_image = full_image.crop((center_x - width / 2, center_y - height / 2, center_x + width / 2, center_y + height / 2))
    return crop_image.resize((WIDTH, HEIGHT))


def draw_frame(osm_url: str, latitude: float, longitude: float, speed: float):
    font = ImageFont.truetype('/usr/share/fonts/liberation-fonts/LiberationSans-Regular.ttf', layout_engine=ImageFont.LAYOUT_RAQM)
    zoom = 12

    #if speed <= 40:
    #    zoom = 13
    #elif speed >= 60:
    #    zoom = 11
    #else:
    #    zoom = 13 - ((speed - 40) / 10)

    image = fetch_map(osm_url, latitude, longitude, zoom)
    draw = ImageDraw.Draw(image)
    draw.fontmode = 'RGBA'
    draw.ellipse((WIDTH / 2 - 3, HEIGHT / 2 - 3, WIDTH / 2 + 2, HEIGHT / 2 + 2), (0, 0, 0))
    draw.ellipse((WIDTH / 2 - 2, HEIGHT / 2 - 2, WIDTH / 2 + 1, HEIGHT / 2 + 1), (0, 255, 255))
    draw.rectangle((0, 0, WIDTH - 1, 3), (0, 0, 0))
    draw.rectangle((0, 0, 3, HEIGHT - 1), (0, 0, 0))
    draw.rectangle((WIDTH - 4, 0, WIDTH - 1, HEIGHT - 1), (0, 0, 0))
    draw.rectangle((0, HEIGHT - 4, WIDTH - 1, HEIGHT - 1), (0, 0, 0))
    draw.text((240, 207), '© OpenStreetMap contributors', font=font, fill=(0, 0, 0))

    return image


