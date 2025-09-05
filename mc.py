import sys
import re
import argparse
from pathlib import Path


def validate_arguments(pattern, folder):
    try:
        path = Path(folder)
        if not path.is_dir():
            print(f"ERROR: Given folder is not a directory: {folder}")
            sys.exit(1)
    except:
        print(f"ERROR: Given folder is not a valid directory: {folder}")
        sys.exit(1)

    try:
        regex = re.compile(rf"^{pattern}")
    except:
        print(f"ERROR: Given pattern is not a valid regex pattern: {pattern}")
        sys.exit(1)


def determine_groups(regex, folder)
    output = {}
    elements = sorted(Path(folder).iterdir(), key=lambda p: p.name.lower())
    for element in elements:
        if not element.is_file():
            continue

        filename = element.name
        extension = element.suffix
        match = regex.match(filename)

        if match:
            key = match.group(0)
            if key not in output:
                output[key] = []

            entry = {}
            entry["filename"] = filename
            entry["filepath"] = element.path
            entry["language"] = "deu"
            entry["take-video"] = extension in ["mkv","mp4"]
            entry["take-audio"] = extension in ["mkv","mp4"]
            entry["take-subtitles"] = extension in ["srt"]

            output[key].append(entry)

    return output


def search_and_merge_all(pattern, folder):
    validate_arguments(pattern, folder)
    regex = re.compile(rf"^{pattern}")

    output = determine_groups(regex, folder)

    output_keys = list(output.keys())
    if output is None or len(output_keys) < 1:
        print("ERROR: Could not determine groups of files with pattern {pattern} in folder {folder}.")
        sys.exit(1)

    for idx, element in enumerate(output[output_keys[0]], 1):
        print(f"[{idx}/{len(len(output[output_keys[0]]))}] {element["filename"]} - Specify which information should be taken.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge multiple media files from MediathekViewWeb into one.")
    parser.add_argument("pattern", help="Regex-Pattern for start of filenames, which should be merged into one.")
    parser.add_argument("folder", help="Folder where the media files are to be found.")
    args = parser.parse_args()

    search_and_merge_all(args.pattern, args.folder)
