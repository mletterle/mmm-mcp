from typing import Any
from os import environ
from urllib import parse as url_parse

import httpx
from httpx_retries import RetryTransport

from fastmcp import FastMCP

IMG_XL = 3

USER_AGENT = "Michael's Magic Music MCP/0.0.1 (bW9jLnNtYXJrb3JwQG1mbA==)"

LASTFM_USER = environ["LASTFM_USER"]
LASTFM_TOKEN = environ["LASTFM_TOKEN"]

LASTFM_API = "https://ws.audioscrobbler.com/2.0"
MUSICBRAINZ_API = "https://musicbrainz.org/ws/2"
DEEZER_API = "https://api.deezer.com/"
RECCOBEATS_API = "https://api.reccobeats.com/v1"

mcp = FastMCP("music")

async def json_api_call(url: str, args: dict={}) -> dict:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    url = f"{url}{("&" + url_parse.urlencode(args)) if args else ""}"
    async with httpx.AsyncClient(transport=RetryTransport()) as client:
       try:
           response = await client.get(url=url, headers=headers)
           response.raise_for_status()
           return response.json()
       except Exception:
           return {}

async def lastfm_api_call(method: str, args: dict={}) -> dict:
    return await json_api_call(f"{LASTFM_API}/?method={method}&api_key={LASTFM_TOKEN}&format=json", args)

async def musicbrains_api_call(resource: str, args: dict={}) -> dict:
    return await json_api_call(f"{MUSICBRAINZ_API}/{resource}?fmt=json", args)

async def deezer_api_call(path: str, args: dict={}) -> dict:
    return await json_api_call(f"{DEEZER_API}/{path}", args)

async def reccobeats_api_call(path: str, args: dict={}) -> dict:
    return await json_api_call(f"{RECCOBEATS_API}/{path}", args)

async def describe_tracks(tracks: []) -> str:
    resp = "When available Music Features are provied, the Features have the following definitions:\n"
    resp += """
- Acousticness: Refers to how much of a song or piece of music is made up of natural, organic sounds rather than synthetic or electronic elements. In other words, it's a measure of how "acoustic" a piece of music sounds. A confidence measure from 0.0 to 1.0, greater value represents higher confidence the track is acoustic.

- Danceability: A measure of how suitable a song is for dancing, ranging from 0 to 1. A score of 0 means the song is not danceable at all, while a score of 1 indicates it is highly danceable. This score takes into account factors like tempo, rhythm, beat consistency, and energy, with higher scores indicating stronger, more rhythmically engaging tracks.

- Energy: Refers to the intensity and liveliness of a track, with a range from 0 to 1. A score of 0 indicates a very calm, relaxed, or low-energy song, while a score of 1 represents a high-energy, intense track. It’s influenced by elements like tempo, loudness, and the overall drive or excitement in the music.

- Instrumentalness: Predicts whether a track contains no vocals. “Ooh” and “aah” sounds are treated as instrumental in this context. Rap or spoken word tracks are clearly “vocal”. The closer the instrumentalness value is to 1.0, the greater likelihood the track contains no vocal content. Values above 0.5 are intended to represent instrumental tracks, but confidence is higher as the value approaches 1.0.

- Key: The key the track is in. Integers map to pitches using standard Pitch Class notation. E.g. 0 = C, 1 = C♯/D♭, 2 = D, and so on. If no key was detected, the value is -1.

- Liveness: The presence of an audience in the recording. Higher liveness values represent an increased probability that the track was performed live. A value above 0.8 provides strong likelihood that the track is live.

- Loudness: The overall loudness of a track in decibels (dB). Loudness values are averaged across the entire track and are useful for comparing relative loudness of tracks. Loudness is the quality of a sound that is the primary psychological correlate of physical strength (amplitude). Values typical range between -60 and 0 db.

- Mode: Indicates the modality (major or minor) of a track.

- Speechiness: Detects the presence of spoken words in a track. The more exclusively speech-like the recording (e.g. talk show, audio book, poetry), the closer to 1.0 the attribute value. Values above 0.66 describe tracks that are probably made entirely of spoken words. Values between 0.33 and 0.66 describe tracks that may contain both music and speech, either in sections or layered, including such cases as rap music. Values below 0.33 most likely represent music and other non-speech-like tracks.

- Tempo: The overall estimated tempo of a track in beats per minute (BPM). Values typical range between 0 and 250

- Valence: Measures the emotional tone or mood of a track, with a range from 0 to 1. A score of 0 indicates a song with a more negative, sad, or dark feeling, while a score of 1 represents a more positive, happy, or uplifting mood. Tracks with a high valence tend to feel joyful or energetic, while those with a low valence may evoke feelings of melancholy or sadness."""
    for track in tracks["track"]:
        tags = []
        urls = []

        artist_name = track["artist"]["name"]
        album_name = track["album"]["#text"] if (track["album"] and track["album"]["#text"]) else ""
        track_name = track["name"]

        lastfm_tags = await lastfm_api_call("track.gettoptags", {"artist": artist_name, "track": track_name})
        for tag in lastfm_tags["toptags"]["tag"][:5] if "toptags" in lastfm_tags else []:
            tags.append(tag["name"])

        lastfm_tags = await lastfm_api_call("artist.gettoptags", {"artist": artist_name})
        for tag in lastfm_tags["toptags"]["tag"][:5] if "toptags" in lastfm_tags else []:
            tags.append(tag["name"])

        if album_name:
            lastfm_tags = await lastfm_api_call("album.gettoptags", {"artist": artist_name, "album": album_name})
            for tag in lastfm_tags["toptags"]["tag"][:5] if "toptags" in lastfm_tags else []:
                tags.append(tag["name"])

        query = f"recording:\"{track_name}\" AND artist:\"{artist_name}\""
        query += f" AND release:\"{album_name}\"" if album_name else ""

        mb = await musicbrains_api_call("recording", {"query": query, "limit": 1})

        rid = None
        if mb["count"] > 0:
            recording = mb["recordings"][mb["offset"]]
            rid = recording["id"]

        if not rid is None:
            mb_rec = await musicbrains_api_call(f"recording/{rid}", {"inc": "url-rels annotation tags isrcs"})

            for tag in mb_rec["tags"]:
                tags.append(tag["name"])

            for rel in mb_rec["relations"]:
                if "url" in rel:
                    urls.append(rel["url"]["resource"])

        query = f"artist:\"{artist_name}\" "
        query += f"track:\"{track_name}\" "
        if album_name:
            query += f"album:\"{album_name}\" "

        isrc = None
        audio_feats = None

        deezer = await deezer_api_call("search", {"q": query, "limit": 1})
        if deezer["total"] > 0:
            isrc = deezer["data"][0]["isrc"]

        if not isrc is None:
            rb = await reccobeats_api_call(f"track?ids={isrc}")
            if "content" in rb and len(rb["content"]) > 0:
                track_id = rb["content"][0]["id"]
                rb_audio = await reccobeats_api_call(f"track/{track_id}/audio-features")
                audio_feats = rb_audio

        resp += f"## ⌚ {track["date"]["#text"] if "date" in track else "Now Playing"}: 🎶 {track["artist"]["name"]} - {track["name"]}\n"

        resp += f"🧑‍🎤: Singer: {track["artist"]["name"]}\n"
        resp += f"🎵: Track: {track["name"]}\n"

        if track["image"][IMG_XL]["#text"]:
            resp += f"🖼️: Image: ![Track Cover Image]({track["image"][IMG_XL]["#text"]})\n"


        if track["loved"] == "1":
            resp += "❤️: Loved: The user loves this track.\n"

        if tags:
            resp += f"🏷️: Tags: {" ".join(set(tags))}\n"

        if audio_feats:
            resp += "\n### ♮ Musical Features\n\n"
            resp += f"Key: {audio_feats["key"]}\n"
            resp += f"Mode: {"Major" if audio_feats["mode"] == 1 else "Minor"}\n"
            resp += f"Tempo: {audio_feats["tempo"]} bpm\n"
            resp += f"Acousticness: {audio_feats["acousticness"]}\n"
            resp += f"Danceablity: {audio_feats["danceability"]}\n"
            resp += f"Energy: {audio_feats["energy"]}\n"
            resp += f"Instrumentalness: {audio_feats["instrumentalness"]}\n"
            resp += f"Liveness: {audio_feats["liveness"]}\n"
            resp += f"Loudness: {audio_feats["loudness"]}\n"
            resp += f"Speechiness: {audio_feats["speechiness"]}\n"
            resp += f"Valence: {audio_feats["valence"]}\n"

        if urls:
            resp += "\n### 🌐 Related Links\n\n"
            for url in urls:
                resp += f"- {url}\n"
            resp += "\n"
    return resp



@mcp.tool()
async def mmm_music_get_recent_tracks() -> str:
    """Gets the user's ten most recently played tracks, including any currently playing track."""
    recent_tracks = await lastfm_api_call("user.getrecenttracks", {"user": LASTFM_USER, "extended": 1, "limit": 10})

    resp = "# Top Ten Most Recent Tracks\n\n"
    resp += "Tracks are listed from most recently played.\n"
    resp += await describe_tracks(recent_tracks["recenttracks"])
    resp += "\n"

    print(resp)
    return resp


def main():
    # Initialize and run the server
    mcp.run(transport="http", host="0.0.0.0", port=8345)


if __name__ == "__main__":
    main()
