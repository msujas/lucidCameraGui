Two scripts for running a Lucid Vision camera, one of which is a gui form of the other, based on the script provided with the Arena (Lucid software) API. The gui script will run on it's own (run 'python lucidStreamGui.py'). Requires the arena_api package, pyqt5, and OpenCV.

On Pypi: run 'pip install lucidCameraGUI'. This should create a python executable called 'lucidCameraGui.exe' in the 'Scripts' folder linked to the LucidStreamGui.py main() function, so just run that 'lucidCameraGui' in the terminal to open the GUI.

Options include selecting the camera resolution, offsets (if using lower than max. resolution), gain, the size of the displayed image on the monitor, Mono8 or BGR8 colour formats, whether to overlay a red cross on the image (and to adjust the size and position of the cross) for e.g. centering a capillary.

![image](https://github.com/msujas/lucidCameraGui/assets/79653376/c6c1bcf4-271a-43bc-aa92-8d84a8ad4fb6)
