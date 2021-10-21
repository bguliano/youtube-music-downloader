import os
import subprocess
from subprocess import DEVNULL
import pytube
from googlesearch import search
from bs4 import BeautifulSoup
import requests
import re
import music_tag

DEFAULT_DOWNLOAD_PATH = r'C:\Users\mguli\Downloads'
DEFAULT_ALBUM_ART_PATH = 'auto_album_art.jpg'
debug = False


def get_stream(link: pytube.YouTube) -> pytube.Stream:
    query = link.streams.filter(only_audio=True, mime_type="audio/mp4")
    stream_data = {stream.abr: stream.itag for stream in query}
    highest_quality = max([int(abr.removesuffix('kbps')) for abr in stream_data.keys()])
    itag = int(stream_data[str(highest_quality) + 'kbps'])
    return link.streams.get_by_itag(itag)


def download_image(url: str):
    with open(DEFAULT_ALBUM_ART_PATH, "wb") as handle:
        response = requests.get(url, stream=True)
        if not response.ok:
            raise Exception("Download image failed: " + str(response))
        for block in response.iter_content(1024):
            if not block:
                break
            handle.write(block)


def get_music_data(title: str) -> dict:
    # Ask user first
    print("Enter in custom values for song, or leave blank to automatically fill them")
    result = {
        "title": input("Song title: ").strip(),
        "artist": input("Artist: ").strip(),
        "album": input("Album: ").strip(),
        "year": input("Year: ").strip(),
        "art": input("Path to album art: ").strip()
    }

    if any(map(lambda x: x == '', [result['title'], result['artist'], result['art'], result['year']])):
        url = next(search("site:genius.com " + title))
        soup = BeautifulSoup(requests.get(url).content, features='html.parser')
        if result["art"] == '':
            album_art_url = soup.find('div', {'role': 'img'}).find('img')['src']
            download_image(album_art_url)
            result["art"] = DEFAULT_ALBUM_ART_PATH
            print("Found album art")
        song_info_html = soup.find('div', {'class': re.compile('SongHeader__Center')})
        if result["title"] == '':
            result["title"] = song_info_html.find('h1').text
            print(f"Found song title: {result['title']}")
        if result["artist"] == '':
            result["artist"] = song_info_html.find('a').text
            print(f"Found artist: {result['artist']}")
        if result["year"] == '':
            result["year"] = soup.find(text="Release Date").parent.parent.text.split(', ')[-1]
            print(f"Found year: {result['year']}")
    if result["album"] == '':
        album_search = search(f"site:music.apple.com {result['artist']} {result['title']} album")
        possible_album_names = []
        for i in range(5):
            soup = BeautifulSoup(requests.get(next(album_search)).content, features='html.parser')
            try:
                album_name = soup.find('h1', {'id': "page-container__first-linked-element"}).text.strip()
            except AttributeError:
                break
            else:
                possible_album_names.append(album_name)
        if len(set(possible_album_names)) == 1:
            result["album"] = possible_album_names[0]
            print(f"Found album name: {result['album']}")
        else:
            print("Found multiple possible album names:")
            for i, name in enumerate(possible_album_names):
                print(f"{i + 1}: {name}")
            selected_album = 0
            while selected_album == 0:
                temp = input("Select the album to use: ")
                try:
                    temp = int(temp)
                except ValueError:
                    continue
                if 0 < temp < len(possible_album_names):
                    selected_album = temp
            result["album"] = possible_album_names[selected_album - 1]
    return result


def set_music_data(song_path: str, data: dict):
    audiofile = music_tag.load_file(song_path)
    audiofile['title'] = data['title']
    audiofile['album artist'] = data['artist']
    audiofile['album'] = data['album']
    audiofile['year'] = data['year']
    with open(data['art'], 'rb') as img_in:
        audiofile['artwork'] = img_in.read()
    audiofile.save()


def convert_song(song_path: str) -> str:
    new_song_path = song_path.removesuffix('mp4') + 'm4a'
    subprocess.run(f'ffmpeg -i "{song_path}" -c:a aac -b:a 192k "{new_song_path}"', stderr=DEVNULL, stdout=DEVNULL)
    return new_song_path


if not debug and __name__ == '__main__':
    search_term = input('Search: ').strip()
    search_results = pytube.Search(search_term).results
    for i, result in enumerate(search_results):
        print(f"{i + 1}: {result.title}")
    chosen = 0
    while chosen == 0:
        temp = input("Select song #: ").strip()
        try:
            temp = int(temp)
        except ValueError:
            continue
        if 0 < temp < len(search_results):
            chosen = temp
    download_path = None
    while download_path is None:
        temp = input(f"Path to download to (defaulting to {DEFAULT_DOWNLOAD_PATH}): ").strip('" ')
        if temp == '':
            download_path = DEFAULT_DOWNLOAD_PATH
        elif os.path.isdir(temp):
            download_path = temp
    print("Downloading song...")
    stream = get_stream(search_results[chosen - 1])
    mp4_path = stream.download(download_path)
    print("Converting to m4a...")
    m4a_path = convert_song(mp4_path)
    print("Finding music data...")
    music_data = get_music_data(stream.title)
    print("Setting music data...")
    set_music_data(m4a_path, music_data)
    print("Cleaning up...")
    os.remove(mp4_path)
    if music_data['art'] == DEFAULT_ALBUM_ART_PATH:
        os.remove(DEFAULT_ALBUM_ART_PATH)
    print("Finished")
