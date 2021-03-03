import json
import os
import sys
import platform
import sys
from pathlib import Path

# Write all the environmental variables so the QGIS interpreter
# can (re)set them properly.
if platform.system() == "Windows":
    configdir = Path(os.environ["APPDATA"]) / "imod-qgis"
else:
    configdir = Path(os.environ["HOME"]) / ".imod-qgis"
configdir.mkdir(exist_ok=True)

env_vars = {key: value for key, value in os.environ.items()}
with open(configdir / "environmental-variables.json", "w") as f:
    f.write(json.dumps(env_vars))

#TODO: Ensure setup.py can find iMOD6.exe somewhere. Probably requires iMOD6 installer.
viewer_exe = sys.argv[1]

with open(configdir / "viewer_exe.txt", "w") as f:
    f.write(viewer_exe)