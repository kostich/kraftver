# Kraftver

Kraftver is a simple Flask webserver to which you can upload an Warcraft III map (in the .w3c and .w3x formats) and get the map data as a JSON response.

## Requirements

You will need [Flask](http://flask.pocoo.org/). You should be able to get it with `sudo pip3 install flask` on any modern Linux system.

## Installation/Usage

Clone locally this repository, `cd` to it and start the server with `FLASK_APP=./main.py flask run`.

To send a map to the server, you can use `curl` or any other way to POST file under an parameter named `map`.

Example:
> curl -F "map=@$some_map.w3x" 127.0.0.1:5000/