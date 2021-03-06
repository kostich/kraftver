# Kraftver

Kraftver is a simple Flask webserver to which you can upload an Warcraft III map (in the .w3c and .w3x formats) and get the map data as a JSON response.

![Alt text](usage.gif?raw=true "Simple gif showing usage")

## Requirements

You will need [Flask](http://flask.pocoo.org/) and [Werkzeug](http://werkzeug.pocoo.org/). You should be able to get those via command `sudo pip3 install flask werkzeug` on any modern Linux system.

You will also need the mpq-extract program from the mpq-tools project. This tool is currently available in the repository https://github.com/mbroemme/mpq-tools.

## Installation

Clone locally this repository, `cd` to it and configure the service by opening `config.py` file and adjusting the options to your liking.

## Usage

Start the server with `./main.py`.

To send a map to the server, you can use `curl` or any other way to POST file under an parameter named `map`.

Example:
> curl -F "map=@$some_map.w3x" 127.0.0.1:8080/

## Docker

You can also use the pre-made Docker container.
Go to your Docker host, pull the container:

> docker pull kostic/kraftver:latest

Start it:

> docker run -d -p <DOCKER_HOST_PORT>:8080 kostic/kraftver:latest

Use it:

> curl -F "map=@$some_map.w3x" <DOCKER_HOST_IP>:<DOCKER_HOST_PORT>/
