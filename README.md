Two scripts for running a Lucid Vision camera, one of which is a gui form of the other, based on the script provided with the Arena (Lucid software) API. The gui script will run on it's own (run 'python lucidStreamGui.py'). Requires the arena_api package, pyqt5, and OpenCV.

On Pypi: run 'pip install lucidCameraGUI'. This should create a python executable called 'lucidCameraGui.exe' in the 'Scripts' folder linked to the LucidStreamGui.py main() function, so just run that 'lucidCameraGui' in the terminal to open the GUI. You can also clone the repository and run 'pip install -e .' within it.

Options include selecting the camera resolution, offsets (if using lower than max. resolution), gain, the size of the displayed image on the monitor, Mono8 or BGR8 colour formats, whether to overlay a red cross on the image (and to adjust the size and position of the cross) for e.g. centering a capillary.

![image](https://github.com/user-attachments/assets/d438c38f-f29c-4640-9e90-72d1aa2383ee)

<img width="735" height="551" alt="image" src="https://github.com/user-attachments/assets/76867bfb-d764-4092-9fb6-ad9d39a63b92" />

