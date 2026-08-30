import zlib

DEVICE_ICONS = [
    "🦊", "🐼", "🐸", "🦉", "🐙", "🦄", "🐳", "🦖",
    "🐝", "🦋", "🐢", "🦩", "🐨", "🐯", "🦁", "🐵",
]

DEVICE_COLORS = [
    "#F87171", "#FBBF24", "#34D399", "#60A5FA",
    "#A78BFA", "#F472B6", "#2DD4BF", "#FB923C",
    "#4ADE80", "#22D3EE", "#E879F9", "#FACC15",
    "#94A3B8", "#FB7185", "#A3E635", "#38BDF8",
]


def _device_index(device_id: str) -> int:
    """Детерминированный индекс иконки по id устройства."""
    return zlib.crc32(device_id.encode()) % len(DEVICE_ICONS)


def device_icon(device_id: str) -> str:
    return DEVICE_ICONS[_device_index(device_id)]


def device_color(device_id: str) -> str:
    return DEVICE_COLORS[_device_index(device_id)]
