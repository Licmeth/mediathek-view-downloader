import sys
import re
import subprocess
import argparse
import platform
import shutil
from pathlib import Path


def is_mkvtoolnix_installed() -> bool:
    # Check if system is Linux. If not, print warning and continue
    if platform.system() != "Linux":
        print(f"WARNING: Cannot determine whether MkvToolNix is installed.")
        return True
    
    # Check if mkvmerge (MKVToolNix) is installed
    if shutil.which("mkvmerge") is None:
        return False
    
    return True


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


def determine_groups(regex, folder):
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
            entry["filepath"] = element.absolute()
            entry["language"] = "deu"
            entry["take-video"] = extension in [".mkv",".mp4"]
            entry["take-audio"] = extension in [".mkv",".mp4"]
            entry["take-subtitles"] = extension in [".srt", ".stl", ".xml"]

            output[key].append(entry)

    return output


def search_and_merge_all(pattern, folder):
    if not is_mkvtoolnix_installed():
        print("ERROR: MKVToolNix (mkvmerge) is not installed or not in PATH.")
        sys.exit(1)

    validate_arguments(pattern, folder)
    regex = re.compile(rf"^{pattern}")

    output = determine_groups(regex, folder)

    output_keys = list(output.keys())
    if output is None or len(output_keys) < 1:
        print(f"ERROR: Could not determine groups of files with pattern {pattern} in folder {folder}.")
        sys.exit(1)

    set_language_and_layers(output)

    for group in output:
        output_filepath = Path(folder).joinpath(f"{group}.mkv").absolute()
        command = f"mkvmerge -o \"{output_filepath}\""

        for element in output[group]:
            command += getSingleFileParameters(element)

        print(subprocess.check_output(command, shell=True))


def getSingleFileParameters(element: dict) -> str:
    result = " "
    if "language" in element:
        result += f"--language -1:{element["language"]} "
    if "take-video" not in element or element["take-video"] == False:
        result += "--no-video "
    if "take-audio" not in element or element["take-audio"] == False:
        result += "--no-audio "
    if "take-subtitles" not in element or element["take-subtitles"] == False:
        result += "--no-subtitles "
    result += f"\"{element["filepath"]}\""
    return result


def strLowerOrElse(value: str, default: str) -> str:
    if value is None or value == "":
        return default.lower()
    return value.lower()


def boolValueOrElse(value: str, default: bool) -> bool:
    if value is None or value == "":
        return default
    return toBoolean(value)


def toBoolean(value: str) -> bool:
    return value is not None and value.lower() in ["true", "yes", "y", "1"]


def set_language_and_layers(output: dict):
    output_keys = list(output.keys())
    key_0 = output_keys[0]

    # Ask user for settings for first group
    for i, element in enumerate(output[key_0], 1):
        print(f"[{i}/{len(output[key_0])}] Specify which information should be taken: {element["filename"]}")
        element["language"] = strLowerOrElse(input(f"Which langage has the content? (default: {element["language"]}) :"), element["language"])
        element["take-video"] = boolValueOrElse(input(f"Should the video be taken? (default: {element["take-video"]}) :"), element["take-video"])
        element["take-audio"] = boolValueOrElse(input(f"Should the audio be taken? (default: {element["take-audio"]}) :"), element["take-audio"])
        element["take-subtitles"] = boolValueOrElse(input(f"Should the subtitles be taken? (default: {element["take-subtitles"]}) :"), element["take-subtitles"])

    # Copy seetings of first group to all other groups
    for key in output_keys[1:]:
        if len(output[key]) < len(output[key_0]):
            print(f"WARNING: Group {key} has less files then reference group {key_0}.")
        if len(output[key]) > len(output[key_0]):
            print(f"ERROR: Group {key} has more files then reference group {key_0}. Aborting..")
            sys.exit(1)

        for i, element in enumerate(output[key], 0):
            element["language"] = output[key_0][i]["language"]
            element["take-video"] = output[key_0][i]["take-video"]
            element["take-audio"] = output[key_0][i]["take-audio"]
            element["take-subtitles"] = output[key_0][i]["take-subtitles"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge multiple media files from MediathekViewWeb into one.")
    parser.add_argument("pattern", help="Regex-Pattern for start of filenames, which should be merged into one.")
    parser.add_argument("folder", help="Folder where the media files are to be found.")
    args = parser.parse_args()

    search_and_merge_all(args.pattern, args.folder)
