# spotify
Parse Spotify listening history files and retrieve the relevant track, album, artist and genre info using Spotipy, a Python Spotify API wrapper

## about
By emailing privacy@spotify.com, your entire Spotify activity can be downloaded. Amongst the creepy location info, there's a series of files containing your entire listening history. The project extracts the relevant info from these files and uses Spotipy to gather all relevant necessary supporting information about the tracks in it, outputting them in clean .csv files.

Spotify takes about two weeks to send you the data from when you email them. There is a way to instantly access your previous 90 days activity via the privacy settings, however this data is given in a different format and isn't compatiable with this code.

## how to run
To run, change the path argument in __main__ to point from the script location to the directory containing the spotify listening history files.

## output
The script creates a directory called output, containing 6 csv files.
1. streaming_history.csv: the cleaned streaming history all in once file
2. track_lookup.csv: details for each unique track in the streaming history
3. album_lookup.csv: details for each unique album in the streaming history
4. artist_lookup.csv: details for each unique artist in the streaming history
5. genre_lookup.csv: details of genre for each artist
6. album_mapping.csv: mapping from "incorrect" album names to correct names. More details explained in code documentation

Details of each albums columns can be found in the docstring of the function that creates each one.

## notes
The outputted data is unnecessarily lean and avoids duplication of data through use of lookup tables as this was done as a learning exercise. This makes the data hard to read on its own - for example, the history file contains only the track ids, not the names. Sorry.

Spotify's search sucks.

For 50,000 tracks, the code takes approximately 15 minutes to run. This is almost entirely due to the album information retrieval. Due to mismatches in data explained in the code and having to query one album at a time through manual searches, only about 10 albums can be done per second.

The required packages are spotipy, pandas, time, os, json.
