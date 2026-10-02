from pathlib import Path

from setuptools import setup


ASSET_PATH = Path("assets/heartsteel-proc.wav")
DATA_FILES = []
if ASSET_PATH.is_file():
    DATA_FILES.append(("share/soundboard/assets", [str(ASSET_PATH)]))

setup(data_files=DATA_FILES)
