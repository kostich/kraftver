#!/usr/bin/env python3
"""Main file"""
# Kraftver is a simple Flask webserver to which you can upload an Warcraft III
# map (in .w3c and .w3x formats) and get the map data back as a JSON response.

import uuid
import os
import json
import shutil
import subprocess
import struct
import config

from flask import Flask, request
from werkzeug.utils import secure_filename

KRAFTVER = Flask(__name__)
KRAFTVER.config['MAX_CONTENT_LENGTH'] = config.MAX_MAP_SIZE * 1024 * 1024

def decode_tileset(tile_char):
    """
    Returns the string describing the tileset (ground type) for a given char.
    """

    if tile_char == 'A':
        tile_char = "Ashenvale"
    elif tile_char == 'B':
        tile_char = "Barrens"
    elif tile_char == 'C':
        tile_char = "Felwood"
    elif tile_char == 'D':
        tile_char = "Dungeon"
    elif tile_char == 'F':
        tile_char = "Lordaeron Fall"
    elif tile_char == 'G':
        tile_char = "Underground"
    elif tile_char == 'L':
        tile_char = "Lordaeron Summer"
    elif tile_char == 'N':
        tile_char = "Northend"
    elif tile_char == 'Q':
        tile_char = "Village Fall"
    elif tile_char == 'V':
        tile_char = "Village"
    elif tile_char == 'W':
        tile_char = "Lordaeron Winter"
    elif tile_char == 'X':
        tile_char = "Dalaran"
    elif tile_char == 'Y':
        tile_char = "Cityscape"
    elif tile_char == 'Z':
        tile_char = "Sunken Ruins"
    elif tile_char == 'I':
        tile_char = "Icecrown"
    elif tile_char == 'J':
        tile_char = "Dalaran Ruins"
    elif tile_char == 'O':
        tile_char = "Outland"
    elif tile_char == 'K':
        tile_char = "Black Citadel"
    else:
        tile_char = "Unknown (bug?): " + tile_char

    return tile_char


def read_map(file_name, unpack_dir_name):
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

    # Extract the MPQ archive from the map file
    try:
        warning = extract_map_file(file_name, unpack_dir_name)
    except ValueError as e:
        raise ValueError(e)

    # Reads the tileset from the file
    if is_valid_w3e(unpack_dir_name + '/war3map.w3e'):
        with open(unpack_dir_name + '/war3map.w3e', "rb") as f:
            # 9nth byte contains the tileset
            main_tileset = f.read(9)
            main_tileset = main_tileset[-1]
            main_tileset = str(chr(main_tileset))

            # Determine the tileset from the char
            main_tileset = decode_tileset(main_tileset)
    else:
        raise ValueError("doesn't contain a valid .w3e file")

    # Read the .w3s string file
    try:
        strings_array = read_string_file(unpack_dir_name)
    except ValueError as e:
        raise ValueError(e)

    # Read the expansion state
    with open(unpack_dir_name + '/war3map.w3i', 'rb') as f:
        # first 4 bytes contain infofile format version
        info_file_bytes = f.read(4)
        infofile_format_ver = int.from_bytes(info_file_bytes,
                                             byteorder='little')

        if infofile_format_ver == 18:
            expansion_required = 'No'
        elif infofile_format_ver == 25:
            expansion_required = 'Yes'
        else:
            expansion_required = str(infofile_format_ver) + ' (bug?)'

        # second 4 bytes contain the number of saves during the map
        # development (ie. map version)
        info_file_bytes = f.read(4)
        map_version = int.from_bytes(info_file_bytes, byteorder='little')

        # third 4 bytes contain the version of editor used to create the map
        info_file_bytes = f.read(4)
        editor_version = int.from_bytes(info_file_bytes, byteorder='little')

        # read the string id from strings file describing map name, again
        info_file_bytes = 1
        map_name_infofile = ""
        while info_file_bytes != 0:
            info_file_bytes = f.read(1)
            info_file_bytes = info_file_bytes[0]
            map_name_infofile += str(chr(info_file_bytes))
        if 'TRIGSTR' in map_name_infofile:
            # remove the \x00 garbage at the end
            map_name_infofile = map_name_infofile.replace('\000', '')
            # read the correct string from the strings_array
            map_name_infofile = strings_array[map_name_infofile]
        else:
            map_name_infofile = map_name_infofile[:-1]

        # read the string id from strings file describing map author
        info_file_bytes = 1
        map_author = ""
        while info_file_bytes != 0:
            info_file_bytes = f.read(1)
            info_file_bytes = info_file_bytes[0]
            map_author += str(chr(info_file_bytes))
        if 'TRIGSTR' in map_author:
            map_author = map_author.replace('\000', '')
            map_author = strings_array[map_author]
        else:
            map_author = map_author.replace('\000', '')

        # read the string id from strings file describing map description
        info_file_bytes = 1
        map_description = ""
        while info_file_bytes != 0:
            info_file_bytes = f.read(1)
            info_file_bytes = info_file_bytes[0]
            map_description += str(chr(info_file_bytes))
        if 'TRIGSTR' in map_description:
            map_description = map_description.replace('\000', '')
            map_description = strings_array[map_description]
        else:
            map_description = map_description.replace('\000', '')

        # read the string id from strings file describing recommended players
        info_file_bytes = 1
        recommended_players = ""
        while info_file_bytes != 0:
            info_file_bytes = f.read(1)
            info_file_bytes = info_file_bytes[0]
            recommended_players += str(chr(info_file_bytes))
        if 'TRIGSTR' in recommended_players:
            recommended_players = recommended_players.replace('\000', '')
            recommended_players = strings_array[recommended_players]
        else:
            recommended_players = recommended_players.replace('\000', '')

        # we read 8 floats (each float is 4 bytes) where the camera bounds 
        # are defined, little endian
        # first 4 floats are enough but we also read the second 4, for some 
        # unidentified reason (verifying purposes?)
        left_camera_bound = f.read(4)
        left_camera_bound = struct.unpack_from('f', left_camera_bound)[0]
        bottom_camera_bound = f.read(4)
        bottom_camera_bound = struct.unpack_from('f', bottom_camera_bound)[0]
        right_camera_bound = f.read(4)
        right_camera_bound = struct.unpack_from('f', right_camera_bound)[0]
        top_camera_bound = f.read(4)
        top_camera_bound = struct.unpack_from('f', top_camera_bound)[0]
        # read over the rest of the 4 floats, we do not know why they exist
        for i in range(4):
            f.read(4)

        # read the camera bounds complements needed for calculating the 
        # map width and height
        camera_bounds_complement_a = f.read(4)
        camera_bounds_complement_a = int.from_bytes(camera_bounds_complement_a,
                                                    byteorder='little')
        camera_bounds_complement_b = f.read(4)
        camera_bounds_complement_b = int.from_bytes(camera_bounds_complement_b,
                                                    byteorder='little')
        camera_bounds_complement_c = f.read(4)
        camera_bounds_complement_c = int.from_bytes(camera_bounds_complement_c,
                                                    byteorder='little')
        camera_bounds_complement_d = f.read(4)
        camera_bounds_complement_d = int.from_bytes(camera_bounds_complement_d,
                                                    byteorder='little')

        # read the playable map width and height
        playable_map_area_width = f.read(4)
        playable_map_area_width = int.from_bytes(playable_map_area_width,
                                                 byteorder='little')
        playable_map_area_height = f.read(4)
        playable_map_area_height = int.from_bytes(playable_map_area_height,
                                                  byteorder='little')

        # calculate the map width and height
        map_width = camera_bounds_complement_a + playable_map_area_width + \
                    camera_bounds_complement_b
        map_height = camera_bounds_complement_c + playable_map_area_height + \
                     camera_bounds_complement_d

        # Read the 4 bytes from w3i file which contain the map flags
        # TODO: we have to experiment and figure out the correct flag meaning
        map_flags_w3i = ""
        for i in range(4):
            byte = f.read(1)
            byte = ord(byte)
            byte = bin(byte)[2:].rjust(8, '0')
            for bit in byte:
                map_flags_w3i += str(bit)

        # Now we read a byte which contains the map main ground type in w3i file
        main_ground_type = f.read(1)

        main_ground_type = str(chr(main_ground_type[0]))
        main_ground_type = decode_tileset(main_ground_type)

    map_data = {
        "warning": warning,
        "map_name": map_name,
        "map_flags": map_flags,
        "map_flags_w3i": map_flags_w3i,
        "max_players": max_player_num,
        "tileset": main_tileset,
        "main_ground_type": main_ground_type,
        "expansion_required": expansion_required,
        "map_version": map_version,
        "editor_version": editor_version,
        "map_name_info_file": map_name_infofile,
        "map_author": map_author,
        "map_description": map_description,
        "left_camera_bound": left_camera_bound,
        "right_camera_bound": right_camera_bound,
        "top_camera_bound": top_camera_bound,
        "bottom_camera_bound": bottom_camera_bound,
        "playable_map_area_height": playable_map_area_height,
        "playable_map_area_width": playable_map_area_width,
        "map_height": map_height,
        "map_width": map_width,
        "recommended_players": recommended_players
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


def map_error(error_string, file):
    """
    Returns a simple dictionary explaining the error during the map
    reading process, to be used as a JSON response
    """
    response = {
        "success": False,
        "error": str(error_string),
        "warning": None,
        "map_name": None,
        "map_flags": None,
        "map_flags_w3i": None,
        "max_players": None,
        "tileset": None,
        "main_ground_type": None,
        "expansion_required": None,
        "map_version": None,
        "editor_version": None,
        "map_name_info_file": None,
        "map_author": None,
        "map_description": None,
        "recommended_players": None,
        "left_camera_bound": None,
        "right_camera_bound": None,
        "top_camera_bound": None,
        "bottom_camera_bound": None,
        "playable_map_area_height": None,
        "playable_map_area_width": None,
        "map_height": None,
        "map_width": None,
        "file_name": secure_filename(file.filename)
    }

    return response


def extract_map_file(file_name, unpack_dir_name):
    """Extracts the given file name via the mpq-extract external tool."""
    warning = ""  # will contain any non-fatal warning

    try:
        os.mkdir(unpack_dir_name)
    except FileExistsError:
        shutil.rmtree(unpack_dir_name)
        os.mkdir(unpack_dir_name)

    # Construct the extract shell command
    extract_command = ("cd %s && mpq-extract -e %s &>/dev/null") % \
                      (unpack_dir_name.replace(" ", "\\ "),
                       file_name.replace(" ", "\\ "))
    # We need to escape the command because it may contain ' (or spacec like
    # above) which can confuse the shell
    extract_command = extract_command.replace("'", "\\'")
    extract_command = extract_command.replace("(", "\\(")
    extract_command = extract_command.replace(")", "\\)")

    # Call the external mpq-extract tool to extract the map
    extract_shell = subprocess.Popen(extract_command,
                                     shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
    extract_std = extract_shell.communicate()

    if extract_shell.returncode != 0:  # can't extract the map file properly
        raise ValueError("can't extract the map file properly: " \
                         + str(extract_std[1].decode("utf-8")))

    # Get the list of all physical files extracted by the mpq-extract tool
    archive_files = sorted(os.listdir(unpack_dir_name))

    # Sometimes mpg-extract doesn't extract anything at all and remains silent
    #  about it
    if len(archive_files) == 0:
        raise ValueError("external tool didn't extract anything")

    # And sometimes mpg-extract extracts one empty file, a valid map should
    # contain at least 16 files inside
    if len(archive_files) < 16:
        raise ValueError("external tool didn't extract properly")

    # Rename extracted files according to the data in listfile
    # The last file is usually attributes and the file before the last
    # file is listfile
    os.rename(unpack_dir_name + '/' + archive_files[-2],
              unpack_dir_name + '/listfile')
    os.rename(unpack_dir_name + '/' + archive_files[-1],
              unpack_dir_name + '/attributes')

    # But sometimes listfile may be the last file, we need to check if our
    # listfile is correct and rename a bit differently if the attributes and
    # the listfile were swapped in the map file

    if not is_valid_list_file(unpack_dir_name + '/listfile') and \
        is_valid_list_file(unpack_dir_name + '/attributes'):
        warning = "listfile and attribute file were swapped, reswapping"
        os.rename(unpack_dir_name + '/attributes',
                  unpack_dir_name + '/correctlistfile')
        os.rename(unpack_dir_name + '/listfile',
                  unpack_dir_name + '/attributes')
        os.rename(unpack_dir_name + '/correctlistfile',
                  unpack_dir_name + '/listfile')
    elif not is_valid_list_file(unpack_dir_name + '/listfile') \
         and not is_valid_list_file(unpack_dir_name + '/attributes'):
        raise ValueError("can't find valid listfile inside the map file")

    # We renamed the listfile and attributes file successfully so we remove
    # them from the list
    archive_files = archive_files[:-2]

    # We read the listfile into the list array
    list_file = []
    with open(unpack_dir_name + '/listfile', 'r') as f:
        for line in f:
            list_file.append(line.replace('\n', ''))

    # We check if the files listed in the listfile actually exist in the MPQ
    # archive or was the archive "protected" by removing some files.
    if len(list_file) != len(archive_files):
        warning = "number of files listed in the listfile (" + \
        str(len(list_file)) + ") do not match the number of physical files (" + \
        str(len(archive_files)) + "), protected map, may encounter errors"

    # We rename the files according to the listfile
    number_of_files = len(archive_files) - 1

    while number_of_files > -1:
        # archive_files contains regular filenames in the directory
        # (file00000.xxx, for example) list_file contains filenames from the
        # listfile (war3map.doo for example)
        genericfilename = unpack_dir_name + '/' + archive_files[number_of_files]
        listfilename = unpack_dir_name + '/' + list_file[number_of_files]
        os.rename(genericfilename, listfilename)

        # The archive can also contain subdirectories so we need to recreate
        # the subdirs and move files into it
        if len(list_file[number_of_files].split('\\')) > 1:
            path = ''

            for subdir in list_file[number_of_files].split('\\')[:-1]:
                path += subdir + '/'

            os.makedirs(unpack_dir_name + '/' + path, exist_ok=True)  # Recreate the subdir

            # .datadir/'AoW\Images\TGA\BTNRessAuraIcon.tga' bellow
            filenamewithslashes = unpack_dir_name + '/' + list_file[number_of_files]
            # .datadir/AoW/Images/TGA/'BTNRessAuraIcon.tga' bellow
            filenameinsubdir = unpack_dir_name + '/' + path + \
            list_file[number_of_files].split('\\')[-1]

            shutil.move(filenamewithslashes, filenameinsubdir)

        number_of_files -= 1

    return warning


def read_string_file(unpack_dir_name):
    """
    Reads the string file from the given file. String file is a text file
    which contains all the strings used within the map.
    """
    # We need to check if the strings file is a valid strings file at all.
    if not is_valid_wts(unpack_dir_name + '/war3map.wts'):
        raise ValueError("can't find valid strings file in the map")

    with open(unpack_dir_name + '/war3map.wts', 'r') as f:
        strings_array = {'TRIGSTR_START': ''}
        total_lines = len(f.readlines())
        f.seek(0)
        current_line = 0

        while current_line <= total_lines:
            line = f.readline()
            current_line += 1
            if 'STRING' in line:
                # create a key name for found string
                stringno = int(line.split(' ')[1])
                if stringno < 10:
                    stringno = '00' + str(stringno)
                elif stringno < 100:
                    stringno = '0' + str(stringno)
                keyname = 'TRIGSTR_' + str(stringno)
                line = f.readline()  # read the next line
                current_line += 1

                # maybe we stumbled upon a comment
                if line[:3] == '// ':
                    line = f.readline()
                    current_line += 1
                    
                # if the next line is a curly bracket which marks the beggining of the string
                if line == '{\n':
                    # read the next char which is hopefully the string value
                    line = f.readline()
                    current_line += 1
                    value = ''

                    # read the lines until we reach the mark which denotes end of the string
                    while line != '}\n':
                        value += line
                        line = f.readline()
                        current_line += 1

                    # we reached the end of the string so we need to save the string into the dictionary
                    strings_array[keyname] = value.strip('\n')

        strings_array.pop("TRIGSTR_START", None)  # we don't need this first dict entry anymore

    return strings_array


def is_valid_w3e(file_path):
    """Checks if a given file is a valid w3e file."""
    with open(file_path, "rb") as f:
        main_tileset_sig = f.read(4)

    main_tileset_sig = str(main_tileset_sig.decode('utf-8'))

    if main_tileset_sig == "W3E!":
        return True
    else:
        return False


def is_valid_list_file(list_file_path):
    """
    Checks if a given filename is a valid listfile. We read the listfile and
    check if any of the lines contain names such as war3map.w3i, war3map.wts
    or war3map.shd. If they do, it's a valid listfile.
    """
    with open(list_file_path, 'r') as f:
        try:
            listfile_data = f.readlines()
        except UnicodeDecodeError:  # prob. binary file, not a listfile
            return False

        if "war3map.w3i\n" in listfile_data or "war3map.wts\n" \
            in listfile_data or "war3map.shd\n" in listfile_data:
            return True
        else:
            return False


def is_valid_wts(strings_file_path):
    """Checks if the given file is a valid strings file."""
    with open(strings_file_path, 'r') as f:
        try:
            first_line = f.readline()
        except UnicodeDecodeError:  # probably a binary file
            return False

        if not 'STRING' in first_line:  # probably not a strings file
            return False
        else:
            return True


@KRAFTVER.route('/', methods=['POST'])
def route():
    """Accepts map, reads it and returns found data."""
    # remove slash at the end of TMP_DIR, if any
    if config.TMP_DIR[-1] == "/":
        config.TMP_DIR = config.TMP_DIR[:-1]

    file_name = config.TMP_DIR + "/kraftver-" + str(uuid.uuid1())
    unpack_dir_name = file_name + "-data"
    f = request.files['map']
    f.save(file_name)

    # Check if we didn't receive an empty file
    if os.stat(file_name).st_size == 0:
        os.remove(file_name)
        shutil.rmtree(unpack_dir_name)
        return json.dumps(map_error("empty map file", f), sort_keys=True,
                          indent=4) + '\n'

    # Check if the uploaded file is a valid wc3 map
    if not valid_map(file_name):
        os.remove(file_name)
        shutil.rmtree(unpack_dir_name)
        return json.dumps(map_error("invalid map file", f), sort_keys=True,
                          indent=4) + '\n'

    # Try to read the map
    try:
        map_data = read_map(file_name, unpack_dir_name)
    except Exception as e:
        os.remove(file_name)
        shutil.rmtree(unpack_dir_name)
        return json.dumps(map_error("can't process map file: " + str(e), f),
                          sort_keys=True, indent=4) + '\n'

    os.remove(file_name)
    shutil.rmtree(unpack_dir_name)

    # Return the data
    response = {
        "success": True,
        "error": None,
        "warning": map_data['warning'],
        "map_name": map_data['map_name'],
        "map_flags": map_data['map_flags'],
        "map_flags_w3i": map_data['map_flags_w3i'],
        "max_players": map_data['max_players'],
        "tileset": map_data['tileset'],
        "main_ground_type": map_data['main_ground_type'],
        "expansion_required": map_data['expansion_required'],
        "map_version": map_data['map_version'],
        "editor_version": map_data['editor_version'],
        "map_name_info_file": map_data['map_name_info_file'],
        "map_author": map_data['map_author'],
        "map_description": map_data['map_description'],
        "recommended_players": map_data['recommended_players'],
        "left_camera_bound": map_data['left_camera_bound'],
        "right_camera_bound": map_data['right_camera_bound'],
        "top_camera_bound": map_data['top_camera_bound'],
        "bottom_camera_bound": map_data['bottom_camera_bound'],
        "playable_map_area_height": map_data['playable_map_area_height'],
        "playable_map_area_width": map_data['playable_map_area_width'],
        "map_height": map_data['map_height'],
        "map_width": map_data['map_width'],
        "file_name": secure_filename(f.filename)
    }
    return json.dumps(response, sort_keys=True, indent=4) + '\n'

if __name__ == "__main__":
    KRAFTVER.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
 