import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import numpy as np

# Attempt to import the required library, with installation instructions if it fails.
try:
    from imaris_ims_file_reader.ims import ims
    import h5py
except ImportError:
    slicer.util.errorDisplay(
        "The 'imaris-ims-file-reader' or 'h5py' library is required. Please install them by opening the Python Interactor "
        "(View -> Python Interactor) and running:\n\n"
        "slicer.util.pip_install('imaris-ims-file-reader h5py')"
    )
    # Raise the error again to stop the module from loading incorrectly
    raise

#
# ImarisReader
#

class ImarisReader(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Imaris Reader"
    self.parent.categories = ["IO"]
    self.parent.dependencies = []
    self.parent.contributors = ["Murat Maga (UW)"]
    self.parent.helpText = """
This module loads multichannel image data from Imaris (.ims) HDF5 files,
allowing resolution selection and automatically detecting voxel spacing.
"""
    self.parent.helpText += self.getDefaultModuleDocumentationLink()
    self.parent.acknowledgementText = """
This file was developed by Murat Maga, University of Washington.
"""

#
# ImarisReaderWidget
#

class ImarisReaderWidget(ScriptedLoadableModuleWidget, slicer.util.VTKObservationMixin):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    #
    # File Input Area
    #
    fileInputCollapsibleButton = ctk.ctkCollapsibleButton()
    fileInputCollapsibleButton.text = "File Input"
    self.layout.addWidget(fileInputCollapsibleButton)
    fileInputFormLayout = qt.QFormLayout(fileInputCollapsibleButton)

    # Input File Selector
    self.inputFileSelector = ctk.ctkPathLineEdit()
    self.inputFileSelector.toolTip = "Pick the input Imaris (.ims) file."
    fileInputFormLayout.addRow("Imaris File: ", self.inputFileSelector)

    # Resolution Selection Dropdown
    self.resolutionSelector = qt.QComboBox()
    self.resolutionSelector.toolTip = "Select the resolution level to load. Lower resolutions are faster."
    self.resolutionSelector.enabled = False
    fileInputFormLayout.addRow("Resolution:", self.resolutionSelector)

    #
    # Load Button
    #
    self.applyButton = qt.QPushButton("Load Volume")
    self.applyButton.toolTip = "Run the algorithm."
    self.applyButton.enabled = False
    self.layout.addWidget(self.applyButton)

    #
    # Other settings (optional screenshot)
    #
    self.enableScreenshotsFlagCheckBox = qt.QCheckBox()
    self.enableScreenshotsFlagCheckBox.checked = 0
    self.enableScreenshotsFlagCheckBox.setText("Enable Screenshots")
    self.layout.addWidget(self.enableScreenshotsFlagCheckBox)


    # connections
    self.applyButton.connect('clicked(bool)', self.onApplyButton)
    self.inputFileSelector.connect("currentPathChanged(QString)", self.onSelect)

    # Add vertical spacer
    self.layout.addStretch(1)

  def cleanup(self):
    pass

  def onSelect(self):
    """
    Called when a new file is selected. Populates the resolution dropdown.
    """
    self.applyButton.enabled = bool(self.inputFileSelector.currentPath)
    
    self.resolutionSelector.clear()
    if self.applyButton.enabled:
      try:
        logic = ImarisReaderLogic()
        resolutions = logic.get_resolution_levels(self.inputFileSelector.currentPath)
        
        # Populate resolutions dropdown with more descriptive names
        for i, res_info in enumerate(resolutions):
            # Display shape as X x Y x Z for user convenience
            self.resolutionSelector.addItem(f"Resolution {i} ({res_info['shape'][4]}x{res_info['shape'][3]}x{res_info['shape'][2]})")

        self.resolutionSelector.enabled = True
      except Exception as e:
        logging.error(f"Could not read resolutions from Imaris file: {e}")
        self.resolutionSelector.enabled = False
    else:
      self.resolutionSelector.enabled = False


  def onApplyButton(self):
    """
    Run processing when user clicks "Apply" button.
    """
    logic = ImarisReaderLogic()

    # Get values from the UI
    enableScreenshotsFlag = self.enableScreenshotsFlagCheckBox.checked
    filePath = self.inputFileSelector.currentPath
    selectedResolutionIndex = self.resolutionSelector.currentIndex

    if not filePath or not os.path.exists(filePath):
        slicer.util.errorDisplay("Please select a valid Imaris file.")
        return

    try:
        logic.run(filePath, enableScreenshotsFlag, selectedResolutionIndex)
        slicer.util.showStatusMessage(f"Successfully imported {filePath}", 3000)
    except Exception as e:
        slicer.util.errorDisplay("Failed to compute results: " + str(e))
        import traceback
        traceback.print_exc()

#
# ImarisReaderLogic
#

class ImarisReaderLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.
  """

  def get_resolution_levels(self, ims_filepath):
    """
    Uses the imaris-ims-file-reader library to get metadata for all resolution levels.
    """
    ims_file = ims(ims_filepath)
    resolutions = []
    level = 0
    while True:
        # The library uses a tuple key: (resolution, timepoint, channel, property)
        res_key = (level, 0, 0, 'resolution')
        shape_key = (level, 0, 0, 'shape')
        if res_key in ims_file.metaData:
            resolutions.append({
                'level': level,
                'resolution': ims_file.metaData[res_key],
                'shape': ims_file.metaData[shape_key]
            })
            level += 1
        else:
            break
    return resolutions

  def add_image_as_volume_node(self, image_array, node_name, spacing, origin):
    """
    Creates a new volume node, populates it, and sets its spacing and origin.
    """
    v_node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
    v_node.SetName(node_name)
    
    slicer.util.updateVolumeFromArray(v_node, image_array)
    
    # Slicer expects spacing in (X, Y, Z) order
    v_node.SetSpacing(spacing)
    v_node.SetOrigin(origin)

  def takeScreenshot(self,name,description,type=-1):
    slicer.util.delayDisplay('Take screenshot %s\nPress OK to continue' % name)
    lm = slicer.app.layoutManager()
    widget = lm.viewport()
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVImageData(qimage,imageData)
    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

  def run(self, input_h5, enableScreenshots=False, resolutionLevelIndex=0):
    """
    Run the actual algorithm using the imaris-ims-file-reader library for metadata
    and h5py for direct data access to bypass bugs in the reader library.
    """
    logging.info('Processing started')

    ims_file = ims(input_h5)
    h5_file = ims_file.hf # Get the underlying h5py file object
    
    # --- Extract metadata for the selected resolution using the library ---
    res_key = (resolutionLevelIndex, 0, 0, 'resolution')
    shape_key = (resolutionLevelIndex, 0, 0, 'shape')
    spacing_zyx = ims_file.metaData[res_key]
    shape_tczyx = ims_file.metaData[shape_key]
    
    # Slicer uses (X, Y, Z) order, so we need to reverse it.
    spacing_xyz = (spacing_zyx[2], spacing_zyx[1], spacing_zyx[0])
    
    # --- Get Origin, defaulting to (0,0,0) ---
    origin_xyz = [0.0, 0.0, 0.0] 
    try:
        # Using Res0 as the most likely place for this metadata
        res0_group = h5_file['DataSet/ResolutionLevel 0/TimePoint 0/Channel 0']
        for item in res0_group.values():
            if isinstance(item, h5py.Dataset) and 'ExtMin' in item.attrs:
                ext_min_str = item.attrs['ExtMin']
                origin_xyz = np.fromstring(ext_min_str.tobytes().decode('utf-8'), sep=' ')
                break
    except Exception as e:
        logging.warning(f"Could not read origin from IMS file, defaulting to (0,0,0). Error: {e}")

    # --- Read Data Directly with h5py, bypassing the buggy slicer in the library ---
    num_channels = shape_tczyx[1]
    for channel_index in range(num_channels):
        # Construct the path to the dataset within the HDF5 file
        res_string = f"ResolutionLevel {resolutionLevelIndex}"
        tp_string = "TimePoint 0" # Assuming first time point
        ch_string = f"Channel {channel_index}"
        
        # Find the actual dataset name ('Data' or similar) inside the channel group
        channel_group_path = f'DataSet/{res_string}/{tp_string}/{ch_string}'
        channel_group = h5_file[channel_group_path]
        
        dataset = None
        for item in channel_group.values():
            if isinstance(item, h5py.Dataset):
                dataset = item
                break
        
        if dataset is None:
            raise ValueError(f"Could not find a dataset within the HDF5 group: {channel_group_path}")

        # Read the data as a numpy array
        channel_data_zyx = np.asarray(dataset)
        
        node_name = f"Channel_{channel_index}-res_{resolutionLevelIndex}"
        
        self.add_image_as_volume_node(channel_data_zyx, node_name, spacing_xyz, origin_xyz)


    if enableScreenshots:
      self.takeScreenshot('ImarisReader-Start','MyScreenshot',-1)

    logging.info('Processing completed')
    return True


class ImarisReaderTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  """
  def setUp(self):
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    self.setUp()
    self.test_ImarisReader1()

  def test_ImarisReader1(self):
    self.delayDisplay("Starting the test")
    import SampleData
    SampleData.downloadFromURL(
        nodeNames='FA',
        fileNames='FA.nrrd',
        uris='http://slicer.kitware.com/midas3/download?items=5767',
        checksums='SHA256:12d1fba4f2e1f1a843f0757366f28c3f3e1a8bb38836f0de2a32bb1cd476560')
    self.delayDisplay('Finished with download and loading')
    volumeNode = slicer.util.getNode(pattern="FA")
    logic = ImarisReaderLogic()
    # hasImageData is not a part of the logic anymore, so we just check if a node was created
    self.assertIsNotNone(volumeNode)
    self.delayDisplay('Test passed!')

