"""
Cache module to avoid re-searching already matched Spotify tracks.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

CACHE_DIR = Path(".cache")
CACHE_FILE = CACHE_DIR / "matches.json"


class MatchCache:
    def __init__(self, cache_file: Path = CACHE_FILE):
        self.cache_file = cache_file
        self.data: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        else:
            self.data = {}

    def save(self):
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, track_id_or_isrc: str) -> Optional[Dict[str, Any]]:
        return self.data.get(track_id_or_isrc)

    def set(self, track_id_or_isrc: str, match_data: Dict[str, Any]):
        self.data[track_id_or_isrc] = match_data
        self.save()
