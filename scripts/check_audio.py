"""Quick check for whether an MP4 contains an audio track.

Scans the MP4 box structure for track handler ('hdlr') boxes and reports
their handler type. 'soun' => audio track, 'vide' => video track.
No external dependencies (no ffmpeg needed).
"""
import sys
import struct


def iter_boxes(data, start, end):
    pos = start
    while pos + 8 <= end:
        size = struct.unpack(">I", data[pos:pos + 4])[0]
        box_type = data[pos + 4:pos + 8]
        header = 8
        if size == 1:  # 64-bit largesize
            size = struct.unpack(">Q", data[pos + 8:pos + 16])[0]
            header = 16
        elif size == 0:  # extends to end of file
            size = end - pos
        yield box_type, pos, header, size
        if size <= 0:
            break
        pos += size


# Boxes that contain child boxes we want to descend into.
CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl"}


def find_handlers(data, start, end, found):
    for box_type, pos, header, size in iter_boxes(data, start, end):
        body = pos + header
        box_end = pos + size
        if box_type == b"hdlr":
            # hdlr: version(1)+flags(3)+predefined(4)+handler_type(4)...
            handler_type = data[body + 8:body + 12]
            found.append(handler_type.decode("latin-1", "replace"))
        elif box_type in CONTAINERS:
            find_handlers(data, body, box_end, found)


def main(path):
    with open(path, "rb") as f:
        data = f.read()
    found = []
    find_handlers(data, 0, len(data), found)
    if not found:
        print(f"{path}: could not find any track handlers (unexpected format).")
        return
    print(f"{path}: track handlers found -> {found}")
    has_audio = any(h == "soun" for h in found)
    has_video = any(h == "vide" for h in found)
    print(f"  video track: {'YES' if has_video else 'no'}")
    print(f"  audio track: {'YES' if has_audio else 'NO'}")
    if not has_audio:
        print("  => This file has NO sound.")
    else:
        print("  => This file contains an audio track.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "sepang_cine_highlight.mp4"
    main(target)
