import sys
import os
import argparse
import datetime as dt
from lxml import etree as et

TAG_BODY = "{http://www.w3.org/ns/ttml}body"
TAG_DIV = "{http://www.w3.org/ns/ttml}div"
TAG_SPAN = "{http://www.w3.org/ns/ttml}span"

ATTR_BEGIN = "begin"
ATTR_END = "end"

TIMESTAMP_FORMAT = "%H:%M:%S.%f"

BEGIN = "begin"
END = "end"
MESSAGE = "message"

OUTPUT_EXTENSION = "srt"

def convert_ebutt_to_srt(input_file: str):
    filepath = check_input_filepath(input_file)
    print(f"Converting {filepath}")

    subs = parse_ebu_file(filepath)
    print(f"Found {len(subs)} subtitles.")

    output_filepath = get_output_filepath(filepath)
    write_output(subs, output_filepath)
    print(f"Subtitles successfully written to {output_filepath}")


def check_input_filepath(input_file: str) -> str:
    if len(input_file) < 1:
        print("Error. Please provide an EBU-TT encoded xml file as argument.")
        sys.exit(1)

    if not os.path.exists(input_file):
        print("Error. The given input file does not exist.")
        sys.exit(1)
    
    return os.path.abspath(input_file)


def get_output_filepath(input_filepath: str) -> str:
    basepath, _ = os.path.splitext(input_filepath)
    filepath = f"{basepath}.{OUTPUT_EXTENSION}"
    if os.path.exists(filepath):
        for i in range(1,1000):
            filepath = f"{basepath}{i:03}.{OUTPUT_EXTENSION}"
            if not os.path.exists(filepath):
                return filepath
        print("Error. Could not create output file.")
        sys.exit(1)
    return filepath


def parse_ebu_file(filepath: str):
    try:
        root = et.parse(filepath)
    except Exception as e:
        print("Error parsing file")
        print(e)
        sys.exit(1)

    subs = list()
    try:
        for node in root.find(TAG_BODY).find(TAG_DIV):
            sub = dict()
            sub[BEGIN] = get_timestamp(node, ATTR_BEGIN)
            sub[END] = get_timestamp(node, ATTR_END)
            sub[MESSAGE] = get_message(node)
            if not None in (sub[BEGIN], sub[END], sub[MESSAGE]):
                subs.append(sub)
    except Exception as e:
        print("Error parsing xml content")
        print(e)
        sys.exit(1)
    return subs


def get_timestamp(node: et.Element, attribute: str) -> dt.datetime:
    try:
        value = node.get(attribute)
        value = f"{value}000"
        timestamp =  dt.datetime.strptime(value, TIMESTAMP_FORMAT)
    except:
        return None
    return timestamp
    

def get_message(node: et.Element) -> str:
    text = None
    for span in node.findall(TAG_SPAN):
        line = span.text
        if not line:
            next
        if text:
            text = f"{text}\n{line}"
        else:
            text = line
    return text


def write_output(subs: dict, filepath: str):
    with open(filepath, 'w', encoding='utf8') as f:
        for i, sub in enumerate(subs):
            f.write(f"{i+1:d}\n")
            f.write(f"{format_output_timestamp(sub[BEGIN])} --> {format_output_timestamp(sub[END])}\n")
            f.writelines(sub[MESSAGE])
            f.write("\n\n")


def format_output_timestamp(timestamp: dt.datetime) -> str:
    return f"{timestamp.strftime('%H:%M:%S')},{timestamp.microsecond/1000:03.0f}"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert subtitles in EBU-TT xml format to srt.")
    parser.add_argument("inputfile", help="Input xml file.")
    args = parser.parse_args()
    convert_ebutt_to_srt(args.inputfile)



