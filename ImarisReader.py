import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging
import h5py
import numpy as np

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
This module loads multichannel image data from Imaris (.ims) HDF5 files.
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
    # Voxel Spacing Area
    #
    spacingCollapsibleButton = ctk.ctkCollapsibleButton()
    spacingCollapsibleButton.text = "Voxel Spacing (for Resolution Level 0)"
    self.layout.addWidget(spacingCollapsibleButton)
    spacingFormLayout = qt.QFormLayout(spacingCollapsibleButton)

    self.xSpacingSpinBox = qt.QDoubleSpinBox()
    self.xSpacingSpinBox.setDecimals(4)
    self.xSpacingSpinBox.setSingleStep(0.01)
    self.xSpacingSpinBox.setValue(1.8)
    spacingFormLayout.addRow("X Spacing:", self.xSpacingSpinBox)

    self.ySpacingSpinBox = qt.QDoubleSpinBox()
    self.ySpacingSpinBox.setDecimals(4)
    self.ySpacingSpinBox.setSingleStep(0.01)
    self.ySpacingSpinBox.setValue(1.8)
    spacingFormLayout.addRow("Y Spacing:", self.ySpacingSpinBox)

    self.zSpacingSpinBox = qt.QDoubleSpinBox()
    self.zSpacingSpinBox.setDecimals(4)
    self.zSpacingSpinBox.setSingleStep(0.01)
    self.zSpacingSpinBox.setValue(4.0)
    spacingFormLayout.addRow("Z Spacing:", self.zSpacingSpinBox)

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
        logic.open_h5(self.inputFileSelector.currentPath)
        res_levels = logic.get_res_levels()
        self.resolutionSelector.addItems(res_levels)
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
    voxelSpacing = [
        self.xSpacingSpinBox.value,
        self.ySpacingSpinBox.value,
        self.zSpacingSpinBox.value
    ]
    selectedResolution = self.resolutionSelector.currentText
    
    if not filePath or not os.path.exists(filePath):
        slicer.util.errorDisplay("Please select a valid Imaris file.")
        return

    try:
        logic.run(filePath, enableScreenshotsFlag, voxelSpacing, selectedResolution)
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
  def __init__(self):
    self.h5 = None

  def open_h5(self, h5_filename):
    self.h5 = h5py.File(h5_filename, 'r')

  def get_res_levels(self):
    return list(self.h5['DataSet'].keys())

  def get_timepoint_names(self, res='ResolutionLevel 0'):
    return list(self.h5[os.path.join('DataSet', res)].keys())

  def get_channel_names(self, res='ResolutionLevel 0', timepoint='TimePoint 0'):
    path = os.path.join('DataSet', res, timepoint)
    return list(self.h5[path].keys())

  def get_array_from_channel(self, channel, res='ResolutionLevel 0', timepoint='TimePoint 0'):
    channel_group_path = os.path.join('DataSet', res, timepoint, channel)
    channel_group = self.h5[channel_group_path]

    for item in channel_group.values():
      if isinstance(item, h5py.Dataset):
        return np.asarray(item)
    
    raise KeyError(f"No HDF5 dataset found within channel group: {channel_group_path}")

  def add_image_as_volume_node(self, image_array, node_name, base_spacing, resolution_level_string):
    """
    Creates a new volume node, populates it with the image_array, and sets its spacing.
    The spacing is adjusted based on the resolution level.
    """
    v_node = slicer.mrmlScene.AddNewNodeByClass('vtkMRMLScalarVolumeNode')
    v_node.SetName(node_name)
    
    # The unnecessary np.swapaxes call has been removed to preserve the correct Z,Y,X order.
    slicer.util.updateVolumeFromArray(v_node, image_array)

    # Calculate spacing based on resolution level, assuming a downsampling factor of 2 per level.
    try:
      # Extract the integer level (e.g., 0, 1, 2) from the string 'ResolutionLevel 0'
      level = int(resolution_level_string.replace('ResolutionLevel ', ''))
      scale_factor = 2 ** level
      adjusted_spacing = [s * scale_factor for s in base_spacing]
      v_node.SetSpacing(adjusted_spacing)
    except (ValueError, TypeError):
      # Fallback if parsing fails for any reason
      logging.warning(f"Could not parse resolution level from '{resolution_level_string}'. Using base spacing.")
      v_node.SetSpacing(base_spacing)
    
    # Set the origin to a default of (0,0,0)
    v_node.SetOrigin(0, 0, 0)


  def takeScreenshot(self,name,description,type=-1):
    slicer.util.delayDisplay('Take screenshot %s\nPress OK to continue' % name)
    lm = slicer.app.layoutManager()
    widget = lm.viewport()
    qimage = ctk.ctkWidgetsUtils.grabWidget(widget)
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)
    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

  def run(self, input_h5, enableScreenshots=False, voxelSpacing=None, resolutionLevel=None):
    """
    Run the actual algorithm
    """
    logging.info('Processing started')

    self.open_h5(input_h5)
    
    if not resolutionLevel:
        res_levels = list(self.get_res_levels())
        resolutionLevel = res_levels[0]

    timepoints = self.get_timepoint_names(resolutionLevel)
    first_timepoint = timepoints[0]

    for channel in self.get_channel_names(resolutionLevel, first_timepoint):
      channel_array = self.get_array_from_channel(channel, resolutionLevel, first_timepoint)
      
      if voxelSpacing is None:
          voxelSpacing = [1.0, 1.0, 1.0]
      
      # Create a new node name with the resolution level as a suffix.
      res_suffix = resolutionLevel.replace('ResolutionLevel ', 'res_')
      node_name_with_res = f"{channel.replace(' ', '_')}-{res_suffix}"
      
      # Pass base spacing (from UI) and the resolution level string to the node creation method
      self.add_image_as_volume_node(channel_array, node_name_with_res, voxelSpacing, resolutionLevel)

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
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')

