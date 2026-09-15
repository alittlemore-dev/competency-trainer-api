import re

FILE_ID_MARKER_PATTERN = re.compile(r"(?:[?#&])fileId=([A-Za-z0-9_-]+)")


def extract_file_ids_from_markdown(content: str) -> frozenset[str]:
    return frozenset(FILE_ID_MARKER_PATTERN.findall(content))
