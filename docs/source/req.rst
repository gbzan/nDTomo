Installation of nDTomo software
-------------------------------

Repository
^^^^^^^^^^
The nDTomo project repository is available for download from GitHub: 
https://github.com/antonyvam/nDTomo

Building procedure
^^^^^^^^^^^^^^^^^^
Open a terminal, navigate to the nDTomo folder and install it using the setup.py file:
python setup.py build

In Windows the GUIs can also be run directly using the corresponding .bat files:

* ID15Ahelper
* Integrator
* MultiTool

Dependencies
^^^^^^^^^^^^
nDTomo is a Python library which relies on the following packages:

* Python: version 2.7 or 3 (tested on 3.7.1)
* PyQt5
* Numpy: version 1.8 or newer
* Scipy: version 0.14 or newer
* Matplotlib: version 1.4 or newer
* Fabio: version 0.6 or newer
* Scikit-image: version 0.10 or newer
* h5py (to access HDF5 files)
* pyqtgraph (for the ID15A helper GUI)
* pyFAI: version 0.13 or newer (for the Intergator GUI)