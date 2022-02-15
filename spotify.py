import pandas as pd
import spotipy
import time
import os
import json
    

output_path = "output"
if not os.path.isdir(output_path):
    os.mkdir(output_path)
REDIRECT_URI = "http://localhost:7777/callback"
SCOPE = "user-read-recently-played"

with open("auth.txt") as f:
    CLIENT_ID, CLIENT_SECRET = f.read().splitlines()

CREDENTIALS = spotipy.oauth2.SpotifyClientCredentials(client_id=CLIENT_ID,
                                                     client_secret=CLIENT_SECRET)
def gen_token():
    """
        returns refreshed Spotify API authentication with defined credentials
    """
    return spotipy.Spotify(client_credentials_manager=CREDENTIALS)

def create_streams_df(path):
    """Create streaming history data frame from raw .json files

    Parameters:
    ----------
    path: str, required
        filepath from script location to folder containing containing 
        streaming files
    
    Returns:
    -------
    streams_df: Pandas DataFrame with columns
                    time (index): datetime objects in Y-m-d H:M:S format
                    track_name: str of trackname
                    artist_name: str of track name
                    album_name: str of album name
                    track_id: str of track's unique spotify id 

    """
    # get list of json streaming history files
    files = [os.path.join(path, filepath) for filepath in os.listdir(path)if filepath.split("_")[0] == "endsong"]
    streams = sum([json.load(open(file, "r")) for file in files], [])
    streams_df = pd.DataFrame(streams)
    print(f"getting streaming history from {', '.join([filepath.split('/')[-1] for filepath in files])}")
    
    useful_columns = ['ts',
                     'master_metadata_track_name',
                     'master_metadata_album_artist_name',
                     'master_metadata_album_album_name',
                     'spotify_track_uri',
                     'reason_end']
    col_names = ['time',
             'track_name',
             'artist_name',
             'album_name',
             'track_id',
             'reason_end']
    # rename, keep and clean useful columns
    streams_df = streams_df[useful_columns]
    streams_df.columns = col_names
    streams_df = streams_df.dropna(subset = ["track_name"])
    streams_df.track_id = streams_df.track_id.str.split(":", expand = True)[2]
    streams_df.time = streams_df.time.str.replace("T", " ")
    streams_df.time = streams_df.time.str.replace("Z", " ")
    streams_df.time = pd.to_datetime(streams_df.time, format = "%Y-%m-%d %H:%M:%S")
    # remove skipped streams
    streams_df["skip"] = False
    streams_df.skip[streams_df.reason_end == "fwdbtn"] = True
    streams_df.drop(["reason_end", "skip"], axis = 1, inplace = True)
    # clean up index
    streams_df.sort_values(by = "time", inplace = True)
    streams_df.reset_index(inplace = True, drop = True)

    print(f"successfully imported {len(streams_df)} streams")
    return streams_df


def create_streaming_history(streams_df):
    """Saves streaming history dataframe created from streams dataframe to csv

    Parameters:
    ----------
    streams_df: Pandas DataFrame, required
                    streams_df returned by create_streams_df

    Returns:
    -------
    None

    """
    columns = ["track_id", "time", "artist_name", "album_name"]
    streaming_history = streams_df[columns]
    streaming_history.set_index("time", drop=True, inplace=True)
    streaming_history.index = streaming_history.index.strftime("%d/%m/%Y %H:%M:S")
    streaming_history.to_csv(os.path.join(output_path, "streaming_history.csv"))
    print(f"streaming history written to {os.path.join(output_path, 'streaming_history.csv')}")
    return None


def get_alternate_album(track, artist, sp):
    """Function to get correct album for tracks where sp.search cannot

    Used when sp.search or streaming history returns albums with type=single/compilations
    whch are not useful. Attempts to get proper album instead

    Parameters:
    ----------
    track: str, required
                 name of track
    artist: str, required
                name of artist
    sp: spotify.client.Spotify
            active instance of authenticator

    Returns:
    -------
    (track name, id): tuple of track name, id
        track_name: str, search name if successful, original name if unsuccessful
        id: str, album_id if successful, None if unsuccessful
    """
    results = sp.search(q = f"artist:{artist} track:{track}", type = "track",
                       limit = 5)["tracks"]["items"]
    names_ids = [(res["album"]["name"], res["album"]["id"]) for res in results]
    for name, id in names_ids:
        if (name != track):# and (sp.album(id)["album_type"] == "album"):
            return name, id
        
    return track, None


def create_album_lookup(streams_df):
    """creates album lookup df and dictionary. writes df to output path
    
    Parameters:
    ----------
    streams_df: Pandas DataFrame, required
                    streams_df returned by create_streams_df

    Returns:
    -------
    album_dict: dictionary of Pandas.DataFrame which is written to file with album_id
                used as the index
                  (album_name,album_artist) is used as album keys as ids not suitable
                  for future use when creating tracks lookup
    album_mapping: dictionary of (old name, correct/new name) key/value pairs for special cases. 


    """
    start = time.time()
    sp = gen_token()
    features = ["label",
            "release_date",
            "popularity",
            "total_tracks"]
    columns = ["album_name", "artist_name"]
    album_lookup = streams_df[columns].drop_duplicates()
    album_lookup.index = [album_lookup.album_name, album_lookup.artist_name]
    album_dict = album_lookup.T.to_dict()
    searches = album_dict.keys()
    nalbums = len(album_lookup)
    album_mapping = dict()
    print(f"getting details of {nalbums} unique albums")
    for nreq, (album, artist) in enumerate(searches):
        search_result = sp.search(q=f"artist:{artist} album:{album}",
                                  limit=1,
                                  type="album")["albums"]["items"]
        if (len(search_result) == 0) or (sp.album(search_result[0]["id"])["album_type"]!="album"):
            name, id = get_alternate_album(album, artist, sp)
            album_dict[(album, artist)]["album_id"] = id
            album_dict[(album, artist)]["album_name"] = name
            album_mapping[(album, artist)] = name
        else:
            id = search_result[0]["id"]
            album_dict[(album, artist)]["album_id"] = id
        
        if id != None:
            details = sp.album(id)
            for feature in features:
                album_dict[(album, artist)][feature] = details[feature]
        
        if nreq % 250 == 0:
            print(f"{nreq} albums completed; time taken: {time.time() - start:.0f}s")
            print(f"remaining time: ~{(nalbums-nreq)*((time.time()-start)/(nreq+1)):.0f}s")
            sp = gen_token()
    album_lookup = pd.DataFrame(album_dict).T.drop_duplicates()
    album_lookup.set_index("album_id", inplace = True)
    album_lookup.to_csv(os.path.join(output_path, "album_lookup.csv"))
    pd.DataFrame(album_mapping, index = album_mapping.keys()).T.to_csv(os.path.join(output_path, "album_mapping.csv"))
    print(f"album lookup written to {os.path.join(output_path, 'album_lookup.csv')}")
    time.sleep(1)
    print(f"album mapping lookup written to {os.path.join(output_path, 'album_mapping.json')}")
    album_lookup["album_id"] = album_lookup.index
    album_dict = album_lookup.set_index(["album_name", "artist_name"], drop=False).T.to_dict()
    return album_dict, album_mapping


def create_artist_lookup(streams_df):
    """
    creates artist lookup df and dict, writing df to csv file

    Parameters:
    ----------
    streams_df: Pandas DataFrame, required
                    streams_df returned by create_streams_df

    Returns:
    -------


    parameters: streams_df

    returns: dict of artist dicts with keys:artist_names
                values: artist_id, list of genres, followers,
                                             popularity
            writes identical csv to file with artist id as index
    """
    sp = gen_token()
    nreq = 0
    columns = ["artist_name"]
    artist_lookup = streams_df[columns].drop_duplicates()
    artists = artist_lookup.artist_name.values
    print(f"getting details of {len(artists)} artists")
    artist_lookup["artist_id"] = None
    artist_dict = {artist_name:{} for artist_name in artists}
    
    for artist in artists:
        try:
            search_result = sp.search(q=f"artist:{artist}",
                                      type = "artist",
                                      limit = 1)["artists"]["items"][0]
            artist_dict[artist]["artist_id"] = search_result["id"]
            artist_dict[artist]["genres"] = search_result["genres"]
            artist_dict[artist]["followers"] = search_result["followers"]["total"]
            artist_dict[artist]["popularity"] = search_result["popularity"]
        except Exception as e:
            artist_dict[artist]["genres"] = []
            artist_dict[artist]["artist_id"] = ""
        nreq += 1
        if nreq > 500:
            sp = gen_token()
            nreq = 0
            print("New token")
    artist_lookup = pd.DataFrame(artist_dict).T
    artist_lookup["artist_name"] = artist_lookup.index
    artist_lookup.to_csv(os.path.join(output_path, "artist_lookup.csv"))
    print(f"artist information written to {os.path.join(output_path, 'artist_lookup.csv')}")
    return artist_dict

def create_track_lookup(streams_df,
                        artist_dict,
                        album_dict,
                        album_mapping):
    """
    creates track lookup df, writing to csv file

    Parameters:
    ----------
    streams_df: Pandas DataFrame, required
                    streams_df returned by create_streams_df
    artist_dict: dict, required
                    dictionary returned by create_artists_df
    album_dict: dict, required
                    dictionary returned by create_album_df
    album_mapping: dict, required
                    dictionary returned by create_album_df

    Returns:
    -------


    parameters: streams_df

    returns: dict of artist dicts with keys:artist_names
                values: artist_id, list of genres, followers,
                                             popularity
            writes identical csv to file with artist id as index
    """
    columns = [ "track_id", 
                "track_name", 
                "artist_name", 
                "album_name"
                ]
    track_lookup = streams_df[columns]
    track_lookup.drop_duplicates(inplace = True)
    track_lookup.index = track_lookup.track_id
    track_dict = track_lookup.T.to_dict()
    tracks = track_dict.keys()
    track_features = ['danceability',
                 'energy',
                 'key',
                 'loudness',
                 'mode',
                 'speechiness',
                 'acousticness',
                 'instrumentalness',
                 'liveness',
                 'valence',
                 'tempo',
                 'duration_ms',
                 'time_signature']
    
    artistalbum = list(zip(track_lookup.artist_name.values, track_lookup.album_name.values))
    ntracks = len(track_lookup)
    start = time.time()
    print(f"getting details of {ntracks} tracks")
    for ndone, (track_id, (artist, album)) in enumerate(zip(tracks, artistalbum)):
        track_dict[track_id]["artist_id"] = artist_dict[artist]["artist_id"]
        if (album, artist) not in album_dict.keys():
            name = album_mapping[(album, artist)]
            track_dict[track_id]["album_name"] = name
            album = name
        track_dict[track_id]["album_id"] = album_dict[(album, artist)]["album_id"]
        track_dict[track_id]["album_name"] = album_dict[(album, artist)]["album_name"]

        
        if (ndone % 1000 == 0) and (ndone > 0):
            print(f"{ndone} tracks done. time taken: {time.time()-start:.0f}s")
            print(f"time remaining: {(ntracks-ndone)*((time.time()-start)/(ndone+1)):.0f}s")
    
    valid_ids = track_lookup.track_id[~track_lookup.track_id.isna()]
    nreq = len(valid_ids)//100 + max(0, len(valid_ids)%100)
    sp = gen_token()
    for n in range(nreq):
        curr_ids = valid_ids[n*100 : (n+1)*100]
        curr_details = zip(curr_ids, sp.audio_features(curr_ids))
        for id, details in curr_details:
            for feature in track_features:
                track_dict[id][feature] = details[feature]
    track_lookup = pd.DataFrame(track_dict).T
    track_lookup.drop(columns = ["artist_name", "album_name", "track_id"], inplace = True)
    track_lookup.to_csv(os.path.join(output_path, "track_lookup.csv"))
    print(f"track lookup written to {os.path.join(output_path, 'track_lookup.csv')}")
    return track_lookup

def create_genres_lookup(artist_dict):
    """Creates artist genres df and writes to file

    DataFrame is one-hot encoding with True/False values with index=artists
    and columns=all genres found   

    Parameters:
    ----------
    artist_dict: dict, required
                    dictionary returned by create_artist_df

    Returns:
    -------
    None

    """
    all_genres = sum([artist_dict[artist]["genres"] for artist in artist_dict.keys()], [])
    genres_df = pd.DataFrame(False, index = [artist_dict[artist]["artist_id"] for artist in artist_dict.keys()], columns = all_genres)
    for artist in artist_dict.keys():
        genres_df.loc[artist_dict[artist]["artist_id"], artist_dict[artist]["genres"]] = True
    genres_df.to_csv(os.path.join(output_path, "genre_lookup.csv"))
    print(f"genres lookup written to {os.path.join(output_path, 'genre_lookup.csv')}")
    return None

def pipeline(input = "MyData"):
    """ function to put it all together
    Parameters:
    ----------
    input: str, optional
            filepath from script to folder containing streaming history files

    Returns:
    -------
    None

    """
    streams_df = create_streams_df(input)[:100]
    create_streaming_history(streams_df)
    album_dict, album_mapping = create_album_lookup(streams_df)
    artist_dict = create_artist_lookup(streams_df)
    create_genres_lookup(artist_dict)
    track_lookup = create_track_lookup(streams_df,
                                        artist_dict,
                                        album_dict,
                                        album_mapping)
    print("congratulation.")
    # return artist_dict, album_dict, track_lookup
    return None

if __name__ == "__main__":
    pipeline()


