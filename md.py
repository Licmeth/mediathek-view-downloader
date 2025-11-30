import requests
import os
import re
import argparse
from ebutt2srt import convert_ebutt_to_srt
from tqdm import tqdm

VIDEO_TYPE_EPISODE = "episode"
VIDEO_TYPE_MOVIE = "movie"


def download_video(video_url, filepath, filename):
    video_response = requests.get(video_url, stream=True)
    if video_response.status_code == 200:
        total_size = int(video_response.headers.get("content-length", 0))
        with open(filepath, "wb") as f, tqdm(
            desc=filename,
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)
                bar.update(len(chunk))
        print(f"  Saved to: {filepath}\n")
    else:
        print(f"  Failed to download: {video_url} (Status {video_response.status_code})\n")


def download_subtitle(subtitle_url, filepath):
    response = requests.get(subtitle_url)
    if response.status_code == 200:
        with open(filepath, "wb") as f:
            f.write(response.content)
        print(f"  Subtitles saved to: {filepath}\n")
    else:
        print(f"  Failed to download subtitles: {subtitle_url} (Status {response.status_code})\n")


def get_subtitle_url(video_info):
    """
    Extracts the subtitle URL from video_info if available.
    Returns the subtitle URL or None if not found.
    Returns a tuple: (subtitle_url, file_extension)
    """
    subtitle_url = video_info.get("url_subtitle")

    # Determine file extension from URL (default to .srt if not found)
    file_extension = ".srt"
    if subtitle_url:
        match = re.search(r"\.([a-zA-Z0-9]+)(?:$)", subtitle_url)
        if match:
            file_extension = f".{match.group(1)}" 
    return subtitle_url, file_extension


def get_video_url_by_quality(video_info, quality):
    """
    Extracts the video URL from video_info based on the desired quality.
    Falls back to available qualities if the desired one is not found.
    Returns a tuple: (video_url, file_extension)
    """
    quality_map = {
        "low": "url_video_low",
        "medium": "url_video",
        "hd": "url_video_hd"
    }

    if quality not in quality_map:
        print(f"Warning: Quality '{quality}' not recognized. Defaulting to 'medium'.")
        quality = "medium"

    url_key = quality_map.get(quality)
    video_url = video_info.get(url_key)
    if not video_url:
        # fallback order: hd -> medium -> low
        for q in ["url_video_hd", "url_video", "url_video_low"]:
            video_url = video_info.get(q)
            if video_url:
                break

    # Determine file extension from URL (default to .mp4 if not found)
    file_extension = ".mp4"
    if video_url:
        match = re.search(r"\.([a-zA-Z0-9]+)(?:$)", video_url)
        if match:
            file_extension = f".{match.group(1)}"

    return video_url, file_extension


def query_api(query, use_title_field=False, use_topic_field=False, include_future_content=False):
    """Query the API and return all results for the given title."""
    api_url = "https://mediathekviewweb.de/api/query"
    offset = 0
    size = 100
    all_results = []

    print(f"Searching for '{query}'...")

    while True:
        if use_title_field and use_topic_field:
            queries = [{"fields": ["title", "topic"], "query": query}]
        elif use_title_field:   
            queries = [{"fields": ["title"], "query": query}]
        elif use_topic_field:
            queries = [{"fields": ["topic"], "query": query}]
        else:
            queries = [{"query": query}]
        query_json = {
            "queries": queries,
            "sortBy": "timestamp",
            "sortOrder": "desc",
            "future": include_future_content,
            "offset": offset,
            "size": size
        }

        response = requests.post(api_url, json=query_json, headers={"Content-Type": "text/plain"})
        if response.status_code != 200:
            print("Error querying API:", response.status_code)
            break

        results = response.json().get("result", {}).get("results", [])
        if not results:
            break

        all_results.extend(results)
        offset += size

    print(f"Found {len(all_results)} results.\n")
    return all_results


def select_topic(all_results):
    """Select a topic if multiple topics are found, filter results by topic."""
    topics = set()
    for video_info in all_results:
        topic = video_info.get("topic")
        if topic:
            topics.add(topic)
    topics = sorted(topics)

    if len(topics) > 1:
        print("Multiple topics found:")
        for idx, topic in enumerate(topics, 1):
            print(f"{idx}: {topic}")
        while True:
            try:
                choice = int(input("Select the topic number to download: "))
                if 1 <= choice <= len(topics):
                    selected_topic = topics[choice - 1]
                    break
                else:
                    print("Invalid selection. Try again.")
            except ValueError:
                print("Please enter a valid number.")
        filtered_results = [v for v in all_results if v.get("topic") == selected_topic]
        print(f"\nProceeding with topic: {selected_topic}\n")
        return filtered_results, selected_topic
    elif len(topics) == 1:
        print(f"Only one topic found: {topics[0]}\n")
        return all_results, topics[0]
    else:
        print("No topics found in results.\n")
        return [], None


def determine_season_and_episode(results):
    """
    Determines the season and episode numbers and whether this is a special version from the video titles.
    Returns a list of video_info dictionaries with season and episode added.
    """
    for video_info in results:
        #print(f"[debug] Video title: {video_info.get("title","")}")
        match = re.search(r"S(\d+)\/E(\d+)", video_info.get("title", ""))
        special = re.search(r" \([A-Za-z]+\)$", video_info.get("title", ""))

        video_info["season"] = None
        video_info["episode"] = None
        video_info["special"] = None
        if match:
            video_info["season"] = match.group(1)
            video_info["episode"] = match.group(2)
        if special:
            # Removing space and parathesis and converting to lowercase
            video_info["special"] = special.group(0)[2:-1].lower()
    return results


def intValueOrElse(value, default):
    if value is None:
        return default
        
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def strValueOrElse(value, default):
    if value is None:
        return default

    try:
        return str(value)
    except (ValueError, TypeError):
        return default


def sort_seasons_by_season_and_special_and_episode(seasons):
    """
    Sorts the seasons by season and episode number.
    Returns a sorted list of seasons.
    """
    return sorted(seasons, key=lambda x: (intValueOrElse(x["season"], 0), strValueOrElse(x["special"], ""), intValueOrElse(x["episode"], 0)))


def select_season(results):
    """
    Allows the user to select a season from the available seasons.
    Returns the list of episodes for the selected season.
    Supports multiple selections by using '+' (e.g., '1+3+5' to select seasons 1, 3, and 5).
    """
    results = determine_season_and_episode(results)
    results = sort_seasons_by_season_and_special_and_episode(results)

    seasons = {}
    for video_info in results:
        season_key = f"{video_info["season"]} {strValueOrElse(video_info["special"], "")}"

        if season_key not in seasons:
            seasons[season_key] = []
        seasons[season_key].append(video_info)

    if len(seasons) == 0:
        print("No seasons found.")
        return []

    while True:
        print("Available seasons:")
        for idx, season in enumerate(seasons, 1):
            print(f"{idx}: Season {season} ({len(seasons[season])} episodes)")

        choice = input("Select the season number(s) to download (e.g., '1' or '1+3+5'). Leave empty or 'y' to download all: ")
        if not choice or (isinstance(choice, str) and choice.lower() == "y"):
            print("Downloading all seasons.")
            return [video for season in seasons.values() for video in season]

        # Check if multiple seasons are selected with '+'
        if '+' in choice:
            try:
                selected_indices = [int(x.strip()) for x in choice.split('+')]
                season_keys = list(seasons.keys())
                
                # Validate all indices
                invalid_indices = [idx for idx in selected_indices if idx < 1 or idx > len(seasons)]
                if invalid_indices:
                    print(f"Invalid selection(s): {', '.join(map(str, invalid_indices))}. Please select valid season numbers.")
                    continue
                
                # Collect all episodes from selected seasons
                selected_episodes = []
                selected_season_names = []
                for idx in selected_indices:
                    season_key = season_keys[idx - 1]
                    selected_episodes.extend(seasons[season_key])
                    selected_season_names.append(season_key)
                
                print(f"\nSelected seasons: {', '.join(selected_season_names)} with {len(selected_episodes)} total episodes.\n")
                return selected_episodes
                
            except ValueError:
                print("Please enter valid numbers separated by '+'.")
                continue
        else:
            # Single season selection
            try:
                if 1 <= intValueOrElse(choice, 0) <= len(seasons):
                    selected_season = list(seasons.keys())[int(choice) - 1]
                    print(f"\nSelected season {selected_season} with {len(seasons[selected_season])} episodes.\n")
                    return seasons[selected_season]
                else:
                    print(f"Invalid selection: {choice}. Please select a valid season number.")
                    continue
            except ValueError:
                print("Please enter a valid number.")
                continue


def update_video_type(results):
    """
    Updates the video type in the results to 'series' if it contains episodes.
    Returns the updated results.
    """
    for video_info in results:
        if re.search(r"S[0-9]+\/E[0-9]+", video_info.get("title", "")):
            video_info["video-type"] = VIDEO_TYPE_EPISODE
        else:
            video_info["video-type"] = VIDEO_TYPE_MOVIE
    return results


def download_all_videos(all_results, download_folder, title, quality="medium", download_subtitles=False, output_strategy="extend"):
    """Download all videos (and optionally subtitles) from the filtered results."""
    os.makedirs(download_folder, exist_ok=True)
    for i, video_info in enumerate(all_results, start=1):
        print(f"[{i}/{len(all_results)}] Downloading: {compile_filename_base(title, video_info)} (quality: {quality})")

        video_url, video_extension = get_video_url_by_quality(video_info, quality)
        print(f"  URL: {video_url}")

        filename_base, filename_video, filepath_video = handle_file_existance(download_folder, video_extension, title, video_info, output_strategy)
        if filename_base is None:
            continue
        print(f"  Output file: {filename_video}")

        download_video(video_url, filepath_video, filename_video)

        if download_subtitles:
            subtitle_url, subtitle_extension = get_subtitle_url(video_info)
            if subtitle_url:
                subtitle_filepath = os.path.join(download_folder, f"{filename_base}{subtitle_extension}")
                download_subtitle(subtitle_url, subtitle_filepath)

                if is_edu_tt_subtitles(subtitle_filepath):
                    convert_subtitles(subtitle_filepath)
            else:
                print(f"  No subtitles available for {filename_video}.\n")


def is_edu_tt_subtitles(filepath: str) -> bool:
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 20:
                return False
            if "<ebuttm:documentMetadata>" in line:
                return True


def convert_subtitles(filepath):
    if os.path.splitext(filepath)[1] != ".xml":
        new_filepath = os.path.splitext(filepath)[0] + ".xml"
        os.rename(filepath, new_filepath)
        filepath = new_filepath
    convert_ebutt_to_srt(filepath)


def compile_filename_base(title, video_info, suffix=None):
    filename_base = f"{title}"
    if video_info["video-type"] == VIDEO_TYPE_EPISODE:
        episode_code = f"S{int(video_info['season']):02d}E{int(video_info['episode']):02d}"
        filename_base += f" {episode_code}"
    if video_info["special"]:
        filename_base += f".{video_info["special"]}"
    if suffix:
        filename_base += f".{suffix}"
    return filename_base


def handle_file_existance(download_folder, video_extension, title, video_info, output_strategy):
    """
    Checks whether the desired output file exsits already. Depending on the output strategy extends the filename
    by a suffix, keeps it or returns a None tuple.
    Returns a tuple of filename_base, filename_video and filepath_video
    """
    filename_base = compile_filename_base(title, video_info)
    filename_video = f"{filename_base}{video_extension}"
    filepath_video = os.path.join(download_folder, filename_video)

    if output_strategy == "overwrite":
        print(f"  Output file {filepath_video} exists already.\n  Overwriting..")
        return filename_base, filename_video, filepath_video

    suffix = 0
    while os.path.isfile(filepath_video):
        if output_strategy == "skip":
            print(f"  Output file {filepath_video} exists already.\n  Skipping..")
            return None, None, None
        suffix += 1
        filename_base = compile_filename_base(title, video_info, suffix)
        filename_video = f"{filename_base}{video_extension}"
        filepath_video = os.path.join(download_folder, filename_video)

    return filename_base, filename_video, filepath_video


def is_topic_is_series(results):
    """
    Determines if the filtered results represent a series (multiple episodes).
    Returns True if the title contains episode codes.
    """
    return any(re.search(r"S[0-9]+\/E[0-9]+", v.get("title", "")) for v in results)


def search_and_download_all(query, download_folder, quality="medium", download_subtitles=False, use_title_field=False, use_topic_field=False, include_future_content=False, output_strategy="extend"):
    all_results = query_api(query, use_title_field, use_topic_field, include_future_content)
    if not all_results:
        print("No results found for the given query.")
        exit(1)
    
    filtered_results, topic = select_topic(all_results)
    if not filtered_results:
        print(f"No videos found for topic {topic}.")
        exit(1)

    if is_topic_is_series(filtered_results):
        filtered_results = update_video_type(filtered_results)
        print("This is a series. Do you want to download a specific or all episodes?")
        filtered_results = select_season(filtered_results)
        if len(filtered_results) > 0:
            download_all_videos(filtered_results, download_folder, topic, quality, download_subtitles, output_strategy)
        else:
            print("No seasons detected in the results.")
            exit(1)
    else:
        print("This is not a series. Downloading the single video...")
        raise NotImplementedError("Single video download not implemented yet.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search and download videos from MediathekViewWeb.")
    parser.add_argument("query", help="Search query")
    parser.add_argument("folder", help="Output folder for downloads")
    parser.add_argument(
        "--quality",
        choices=["low", "medium", "hd"],
        default="medium",
        help="Video quality to download (default: medium)"
    )
    parser.add_argument(
        "-s", "--subtitles",
        action="store_true",
        help="Download subtitles if available"
    )
    parser.add_argument(
        "-t", "--title",
        action="store_true",
        help="Search using the title field (default: search all fields)"
    )
    parser.add_argument(
        "-T", "--topic",
        action="store_true",
        help="Search using the topic field (default: search all fields)"
    )
    parser.add_argument(
        "-f", "--future",
        action="store_true",
        help="Search including future content (default: false)"
    )
    parser.add_argument(
        "-o", "--output",
        choices=["extend", "overwrite", "skip"],
        default="extend",
        help="Output strategy: If the output exists, should it be overwritten, extended or skipped?"
    )
    args = parser.parse_args()

    search_and_download_all(args.query, args.folder, args.quality, args.subtitles, args.title, args.topic, args.future, args.output)
