import os
import slicer
from slicer.ScriptedLoadableModule import *
import ctk
import qt
import logging

#
# ImarisReader
#
class ImarisReader(ScriptedLoadableModule):
  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Imaris Reader"
    self.parent.categories = ["Informatics"]
    self.parent.contributors = ["Gemini (Google AI)"]
    self.parent.helpText = "Loads an Imaris (.ims) file using manually entered voxel spacing."
    self.parent.acknowledgementText = "Uses the 'imaris-ims-file-reader' package."

#
# ImarisReaderWidget
#
class ImarisReaderWidget(ScriptedLoadableModuleWidget):
  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    # UI Panel for File IO
    ioCollapsibleButton = ctk.ctkCollapsibleButton()
    ioCollapsibleButton.text = "File Input"
    self.layout.addWidget(ioCollapsibleButton)
    ioFormLayout = qt.QFormLayout(ioCollapsibleButton)

    self.inputFileSelector = ctk.ctkPathLineEdit()
    self.inputFileSelector.filters = ctk.ctkPathLineEdit.Files
    self.inputFileSelector.nameFilters = ["Imaris File (*.ims)"]
    self.inputFileSelector.setToolTip("Select the Imaris .ims file to load.")
    ioFormLayout.addRow("Imaris File:", self.inputFileSelector)

    # UI Panel for Manual Spacing
    dimsCollapsibleButton = ctk.ctkCollapsibleButton()
    dimsCollapsibleButton.text = "Voxel Spacing"
    self.layout.addWidget(dimsCollapsibleButton)
    dimsFormLayout = qt.QFormLayout(dimsCollapsibleButton)

    # Input fields for voxel spacing (resolution) on each axis
    self.spacingX = qt.QDoubleSpinBox()
    self.spacingX.setSuffix(" mm")
    self.spacingX.setDecimals(4)
    self.spacingX.setMinimum(0.0001)
    self.spacingX.setMaximum(1000.0)
    self.spacingX.setValue(0.018)
    dimsFormLayout.addRow("X Spacing:", self.spacingX)
    
    self.spacingY = qt.QDoubleSpinBox()
    self.spacingY.setSuffix(" mm")
    self.spacingY.setDecimals(4)
    self.spacingY.setMinimum(0.0001)
    self.spacingY.setMaximum(1000.0)
    self.spacingY.setValue(0.018)
    dimsFormLayout.addRow("Y Spacing:", self.spacingY)

    self.spacingZ = qt.QDoubleSpinBox()
    self.spacingZ.setSuffix(" mm")
    self.spacingZ.setDecimals(4)
    self.spacingZ.setMinimum(0.0001)
    self.spacingZ.setMaximum(1000.0)
    self.spacingZ.setValue(0.040)
    dimsFormLayout.addRow("Z Spacing:", self.spacingZ)

    # Load button
    self.loadButton = qt.QPushButton("Load Volume")
    self.loadButton.toolTip = "Load the selected file with the specified spacing."
    ioFormLayout.addRow(self.loadButton)

    # Connections
    self.loadButton.connect('clicked(bool)', self.onLoadButton)

    self.logic = ImarisReaderLogic()
    self.layout.addStretch(1)

  def onLoadButton(self):
    filePath = self.inputFileSelector.currentPath
    if not filePath:
      slicer.util.warningDisplay("Please select an Imaris file first.")
      return

    # Get spacing values directly from the UI
    spacings = [self.spacingX.value, self.spacingY.value, self.spacingZ.value]

    slicer.util.showStatusMessage("Loading Imaris file...")
    qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
    try: # <--- THIS COLON WAS MISSING
      self.logic.loadImarisFileWithManualSpacing(filePath, spacings)
      slicer.util.showStatusMessage("Loading complete.", 3000)
    except Exception as e:
      slicer.util.errorDisplay(f"Failed to load Imaris file: {e}")
      import traceback
      traceback.print_exc()
    finally:
      qt.QApplication.restoreOverrideCursor()

#
# ImarisReaderLogic
#
class ImarisReaderLogic(ScriptedLoadableModuleLogic):
  def loadImarisFileWithManualSpacing(self, filePath, spacings, time_point=0, channel=0):
    """
    Loads data from an Imaris file and applies the manually entered spacing directly.
    """
    from imaris_ims_file_reader.ims import ims
    import numpy as np

    # 1. Open the .ims file and get the data
    ims_file = ims(filePath)
    image_data = ims_file[time_point, channel, :, :, :]

    # 2. Create the Slicer volume node
    nodeName = os.path.basename(filePath).replace(".ims", f"_C{channel}T{time_point}")
    volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", nodeName)
    slicer.util.updateVolumeFromArray(volumeNode, image_data)

    # 3. Set the spacing directly from the user's input. No calculation.
    volumeNode.SetSpacing(spacings[0], spacings[1], spacings[2])

    # 4. Center the volume in the 3D viewers
    applicationLogic = slicer.app.applicationLogic()
    selectionNode = applicationLogic.GetSelectionNode()
    selectionNode.SetReferenceActiveVolumeID(volumeNode.GetID())
    applicationLogic.PropagateVolumeSelection(0)

    logging.info(f"Successfully loaded 3D volume '{nodeName}' with direct spacing {volumeNode.GetSpacing()}.")