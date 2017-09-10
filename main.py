#!/usr/bin/env python3
"""Main file"""
# Kraftver is a simple Flask webserver to which you can upload an Warcraft III
# map (in .w3c and .w3x formats) and get the map data back as a JSON response.

import uuid
import os
import json
import config

from flask import Flask, request
from werkzeug.utils import secure_filename

KRAFTVER = Flask(__name__)
KRAFTVER.config['MAX_CONTENT_LENGTH'] = config.MAX_MAP_SIZE * 1024 * 1024

def read_map(file_name):
    """Reads the map name from the supplied file and returns data about it."""
    map_name = ""
    map_flags = ""

    with open(file_name, "rb") as map_file:
        # Read the map name, map name is stored from 9th byte until the \x00.
        map_file.seek(8)

        # while our byte isn't zero, read the bytes and convert them to text
        byte = map_file.read(1)
        while byte != b'\x00':
            try:
                map_name += byte.decode('utf-8')
            except UnicodeDecodeError:  # probably utf8 char so we need 1 more byte
                byte += map_file.read(1)
                map_name += byte.decode('utf-8')

            byte = map_file.read(1)

        # Read the flags from the w3x header and transform them to a string
        # of ones and zeros
        for i in range(4):
            byte = map_file.read(1)
            byte = ord(byte)
            byte = bin(byte)[2:].rjust(8, '0')
            for bit in byte:
                map_flags += str(bit)

        # read the max players number
        max_player_num = map_file.read(4)
        max_player_num = int.from_bytes(max_player_num, byteorder='little')


    map_data = {
        "map_name": map_name,
        "map_flags": map_flags,
        "max_players": max_player_num
    }

    return map_data


def valid_map(file_name):
    """
    Checks if the magic numbers of a given file correspond to a
    Warcraft III map file
    """
    with open(file_name, "rb") as f:
        map_name_bytes = f.read(4)

    try:
        map_name_bytes = str(map_name_bytes.decode('utf-8'))
    except UnicodeDecodeError:
        return False

    if map_name_bytes == "HM3W":
        return True

    return False


@KRAFTVER.route('/', methods=['POST'])
def route():
    """Accepts map, reads it and returns found data."""
    file_name = "/tmp/kraftver-" + str(uuid.uuid1())
    f = request.files['map']
    f.save(file_name)

    # Check if we didn't receive an empty file
    if os.stat(file_name).st_size == 0:
        response = {
            "success": False,
            "map_name": "error reading map: empty file",
            "map_flags": None,
            "max_players": None,
            "file_name": secure_filename(f.filename)
        }
        os.remove(file_name)
        return json.dumps(response, sort_keys=True, indent=4) + '\n'

    # Check if the uploaded file is a valid wc3 map
    if not valid_map(file_name):
        response = {
            "success": False,
            "map_name": "error reading map: invalid file",
            "map_flags": None,
            "max_players": None,
            "file_name": secure_filename(f.filename)
        }
        os.remove(file_name)
        return json.dumps(response, sort_keys=True, indent=4) + '\n'

    # Try to read the map
    try:
        map_data = read_map(file_name)
    except:
        response = {
            "success": False,
            "map_name": "error reading map",
            "map_flags": None,
            "max_players": None,
            "file_name": secure_filename(f.filename)
        }
        os.remove(file_name)
        return json.dumps(response, sort_keys=True, indent=4) + '\n'

    os.remove(file_name)

    # Return the data
    response = {
        "success": True,
        "map_name": map_data['map_name'],
        "map_flags": map_data['map_flags'],
        "max_players": map_data['max_players'],
        "file_name": secure_filename(f.filename)
    }
    return json.dumps(response, sort_keys=True, indent=4) + '\n'

if __name__ == "__main__":
    KRAFTVER.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
