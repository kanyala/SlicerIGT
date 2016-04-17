import os
import unittest
import vtk, qt, ctk, slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# ScreenCapture
#

class ScreenCapture(ScriptedLoadableModule):
  """Uses ScriptedLoadableModule base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def __init__(self, parent):
    ScriptedLoadableModule.__init__(self, parent)
    self.parent.title = "Screen Capture"
    self.parent.categories = ["Utilities"]
    self.parent.dependencies = []
    self.parent.contributors = ["Andras Lasso (PerkLab, Queen's)"]
    self.parent.helpText = """Capture image sequences from 2D and 3D viewers"""
    self.parent.acknowledgementText = """ """ # replace with organization, grant and thanks.

#
# ScreenCaptureWidget
#

class ScreenCaptureWidget(ScriptedLoadableModuleWidget):
  """Uses ScriptedLoadableModuleWidget base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setup(self):
    ScriptedLoadableModuleWidget.setup(self)

    self.logic = ScreenCaptureLogic()
    self.logic.logCallback = self.addLog

    # Instantiate and connect widgets ...

    #
    # Input area
    #
    inputCollapsibleButton = ctk.ctkCollapsibleButton()
    inputCollapsibleButton.text = "Input"
    self.layout.addWidget(inputCollapsibleButton)
    inputFormLayout = qt.QFormLayout(inputCollapsibleButton)

    # Input view selector
    self.viewNodeSelector = slicer.qMRMLNodeComboBox()
    self.viewNodeSelector.nodeTypes = ["vtkMRMLSliceNode", "vtkMRMLViewNode"]
    self.viewNodeSelector.addEnabled = False
    self.viewNodeSelector.removeEnabled = False
    self.viewNodeSelector.noneEnabled = False
    self.viewNodeSelector.showHidden = False
    self.viewNodeSelector.showChildNodeTypes = False
    self.viewNodeSelector.setMRMLScene( slicer.mrmlScene )
    self.viewNodeSelector.setToolTip( "Contents of this slice or 3D view will be captured." )
    inputFormLayout.addRow("View to capture: ", self.viewNodeSelector)

    #
    # Slice view options area
    #
    self.sliceViewOptionsCollapsibleButton = ctk.ctkCollapsibleButton()
    self.sliceViewOptionsCollapsibleButton.text = "Slice view options"
    self.layout.addWidget(self.sliceViewOptionsCollapsibleButton)
    sliceViewOptionsLayout = qt.QFormLayout(self.sliceViewOptionsCollapsibleButton)

    # Slice mode
    self.sliceModeWidget = qt.QComboBox()
    self.sliceModeWidget.addItem("sweep")
    self.sliceModeWidget.addItem("fade")
    self.sliceModeWidget.setToolTip("Select the property that will be adjusted")
    sliceViewOptionsLayout.addRow("Mode:", self.sliceModeWidget)

    # Start slice offset position
    self.startSliceOffsetSliderLabel = qt.QLabel("Start sweep offset:")
    self.startSliceOffsetSliderWidget = ctk.ctkSliderWidget()
    self.startSliceOffsetSliderWidget.singleStep = 30
    self.startSliceOffsetSliderWidget.minimum = -100
    self.startSliceOffsetSliderWidget.maximum = 100
    self.startSliceOffsetSliderWidget.value = 0
    self.startSliceOffsetSliderWidget.setToolTip("Start slice sweep offset.")
    sliceViewOptionsLayout.addRow(self.startSliceOffsetSliderLabel, self.startSliceOffsetSliderWidget)

    # End slice offset position
    self.endSliceOffsetSliderLabel = qt.QLabel("End sweep offset:")
    self.endSliceOffsetSliderWidget = ctk.ctkSliderWidget()
    self.endSliceOffsetSliderWidget.singleStep = 5
    self.endSliceOffsetSliderWidget.minimum = -100
    self.endSliceOffsetSliderWidget.maximum = 100
    self.endSliceOffsetSliderWidget.value = 0
    self.endSliceOffsetSliderWidget.setToolTip("End slice sweep offset.")
    sliceViewOptionsLayout.addRow(self.endSliceOffsetSliderLabel, self.endSliceOffsetSliderWidget)

    #
    # 3D view options area
    #
    self.threeDViewOptionsCollapsibleButton = ctk.ctkCollapsibleButton()
    self.threeDViewOptionsCollapsibleButton.text = "3D view options"
    self.layout.addWidget(self.threeDViewOptionsCollapsibleButton)
    threeDViewOptionsLayout = qt.QFormLayout(self.threeDViewOptionsCollapsibleButton)

    # Start rotation
    self.startRotationSliderWidget = ctk.ctkSliderWidget()
    self.startRotationSliderWidget.singleStep = 5
    self.startRotationSliderWidget.minimum = 0
    self.startRotationSliderWidget.maximum = 180
    self.startRotationSliderWidget.value = 180
    self.startRotationSliderWidget.setToolTip("Rotation angle for the first image, relative to current orientation.")
    threeDViewOptionsLayout.addRow("Start rotation angle:", self.startRotationSliderWidget)

    # End rotation
    self.endRotationSliderWidget = ctk.ctkSliderWidget()
    self.endRotationSliderWidget.singleStep = 5
    self.endRotationSliderWidget.minimum = 0
    self.endRotationSliderWidget.maximum = 180
    self.endRotationSliderWidget.value = 180
    self.endRotationSliderWidget.setToolTip("Rotation angle for the last image, relative to current orientation.")
    threeDViewOptionsLayout.addRow("End rotation angle:", self.endRotationSliderWidget)

    #
    # Output area
    #
    outputCollapsibleButton = ctk.ctkCollapsibleButton()
    outputCollapsibleButton.text = "Output"
    self.layout.addWidget(outputCollapsibleButton)
    outputFormLayout = qt.QFormLayout(outputCollapsibleButton)
    
    # Number of steps value
    self.numberOfStepsSliderWidget = ctk.ctkSliderWidget()
    self.numberOfStepsSliderWidget.singleStep = 10
    self.numberOfStepsSliderWidget.minimum = 2
    self.numberOfStepsSliderWidget.maximum = 150
    self.numberOfStepsSliderWidget.value = 31
    self.numberOfStepsSliderWidget.decimals = 0
    self.numberOfStepsSliderWidget.setToolTip("Number of images extracted between start and stop positions.")
    outputFormLayout.addRow("Number of images:", self.numberOfStepsSliderWidget)

    # Output directory selector
    self.outputDirSelector = ctk.ctkPathLineEdit()
    self.outputDirSelector.filters = ctk.ctkPathLineEdit.Dirs
    self.outputDirSelector.settingKey = 'ScreenCaptureOutputDir'
    outputFormLayout.addRow("Output directory:", self.outputDirSelector)
    if not self.outputDirSelector.currentPath:
      defaultOutputPath = os.path.abspath(os.path.join(slicer.app.defaultScenePath,'SlicerCapture'))
      self.outputDirSelector.setCurrentPath(defaultOutputPath)

    self.videoExportCheckBox = qt.QCheckBox()
    self.videoExportCheckBox.checked = False
    self.videoExportCheckBox.setToolTip("If checked, exported images will be written as a video file.")
    outputFormLayout.addRow("Video export:", self.videoExportCheckBox)

    self.videoFileNameWidget = qt.QLineEdit()
    self.videoFileNameWidget.setToolTip("String that defines file name, type, and numbering scheme. Default: capture.avi.")
    self.videoFileNameWidget.text = "SlicerCapture.avi"
    self.videoFileNameWidget.setEnabled(False)
    outputFormLayout.addRow("Video file name:", self.videoFileNameWidget)

    self.videoLengthSliderWidget = ctk.ctkSliderWidget()
    self.videoLengthSliderWidget.singleStep = 0.1
    self.videoLengthSliderWidget.minimum = 0.1
    self.videoLengthSliderWidget.maximum = 30
    self.videoLengthSliderWidget.value = 5
    self.videoLengthSliderWidget.decimals = 0
    self.videoLengthSliderWidget.setToolTip("Length of the exported video in seconds.")
    self.videoLengthSliderWidget.setEnabled(False)
    outputFormLayout.addRow("Video length:", self.videoLengthSliderWidget)

    # Capture button
    self.captureButton = qt.QPushButton("Capture")
    self.captureButton.toolTip = "Capture slice sweep to image sequence."
    outputFormLayout.addRow(self.captureButton)
        
    self.statusLabel = qt.QPlainTextEdit()
    self.statusLabel.setTextInteractionFlags(qt.Qt.TextSelectableByMouse)
    self.statusLabel.setCenterOnScroll(True)
    outputFormLayout.addRow(self.statusLabel)

    #
    # Advanced area
    #
    self.advancedCollapsibleButton = ctk.ctkCollapsibleButton()
    self.advancedCollapsibleButton.text = "Advanced"
    self.advancedCollapsibleButton.collapsed = not (not self.logic.getFfmpegPath())
    self.layout.addWidget(self.advancedCollapsibleButton)
    advancedFormLayout = qt.QFormLayout(self.advancedCollapsibleButton)

    self.fileNamePatternWidget = qt.QLineEdit()
    self.fileNamePatternWidget.setToolTip("String that defines file name, type, and numbering scheme. Default: image%05d.png.")
    self.fileNamePatternWidget.text = "image_%05d.png"
    advancedFormLayout.addRow("Image file name pattern:", self.fileNamePatternWidget)

    ffmpegPath = self.logic.getFfmpegPath()
    self.ffmpegPathSelector = ctk.ctkPathLineEdit()
    self.ffmpegPathSelector.setCurrentPath(ffmpegPath)
    self.ffmpegPathSelector.nameFilters = ['ffmpeg.exe', 'ffmpeg']
    self.ffmpegPathSelector.setMaximumWidth(300)
    self.ffmpegPathSelector.setToolTip("Set the path to ffmpeg executable. Download from: https://www.ffmpeg.org/")
    advancedFormLayout.addRow("ffmpeg executable:", self.ffmpegPathSelector)

    self.extraVideoOptionsWidget = qt.QLineEdit()
    self.extraVideoOptionsWidget.text = "-c:v mpeg4 -qscale:v 5"
    #self.extraVideoOptionsWidget.setToolTip("Additional video conversion options passed to ffmpeg.")
    self.extraVideoOptionsWidget.setToolTip(
        "<html>\n"
        "  <b>Examples:</b>"
        "  <ul>"
        "    <li><b>MPEG4:</b> -c:v mpeg4 -qscale:v 5</li>"
        "    <li><b>H264:</b> -c:v libx264 -preset veryslow -qp 0</li>"
        "  </ul>"
        "</html>")
    advancedFormLayout.addRow("Video extra options:", self.extraVideoOptionsWidget)

    # See encoding options at:
    # https://trac.ffmpeg.org/wiki/Encode/H.264
    # https://trac.ffmpeg.org/wiki/Encode/MPEG-4

    # Add vertical spacer
    self.layout.addStretch(1)
    
    # connections
    self.captureButton.connect('clicked(bool)', self.onCaptureButton)
    self.viewNodeSelector.connect("currentNodeChanged(vtkMRMLNode*)", self.onViewNodeSelected)
    self.sliceModeWidget.connect("currentIndexChanged(int)", self.onSliceViewModeSelected)
    self.startSliceOffsetSliderWidget.connect('valueChanged(double)', self.setSliceOffset)
    self.endSliceOffsetSliderWidget.connect('valueChanged(double)', self.setSliceOffset)
    self.videoExportCheckBox.connect('toggled(bool)', self.fileNamePatternWidget, 'setDisabled(bool)')
    self.videoExportCheckBox.connect('toggled(bool)', self.videoFileNameWidget, 'setEnabled(bool)')
    self.videoExportCheckBox.connect('toggled(bool)', self.videoLengthSliderWidget, 'setEnabled(bool)')

    self.onViewNodeSelected()

  def addLog(self, text):
    """Append text to log window
    """
    self.statusLabel.appendPlainText(text)
    self.statusLabel.ensureCursorVisible()
    slicer.app.processEvents() # force update
    
  def cleanup(self):
    pass

  def enableSliceViewOptions(self, enable):
    self.sliceViewOptionsCollapsibleButton.setVisible(enable)
    if enable:
      offsetResolution = self.logic.getSliceOffsetResolution(self.viewNodeSelector.currentNode())
      sliceOffsetMin, sliceOffsetMax = self.logic.getSliceOffsetRange(self.viewNodeSelector.currentNode())

      wasBlocked = self.startSliceOffsetSliderWidget.blockSignals(True)
      self.startSliceOffsetSliderWidget.singleStep = offsetResolution
      self.startSliceOffsetSliderWidget.minimum = sliceOffsetMin
      self.startSliceOffsetSliderWidget.maximum = sliceOffsetMax
      self.startSliceOffsetSliderWidget.value = sliceOffsetMin
      self.startSliceOffsetSliderWidget.blockSignals(wasBlocked)

      wasBlocked = self.endSliceOffsetSliderWidget.blockSignals(True)
      self.endSliceOffsetSliderWidget.singleStep = offsetResolution
      self.endSliceOffsetSliderWidget.minimum = sliceOffsetMin
      self.endSliceOffsetSliderWidget.maximum = sliceOffsetMax
      self.endSliceOffsetSliderWidget.value = sliceOffsetMax
      self.endSliceOffsetSliderWidget.blockSignals(wasBlocked)

  def enable3dViewOptions(self, enable):
    self.threeDViewOptionsCollapsibleButton.setVisible(enable)

  def onViewNodeSelected(self):
    viewNode = self.viewNodeSelector.currentNode()
    self.enableSliceViewOptions(viewNode.IsA("vtkMRMLSliceNode"))
    self.enable3dViewOptions(viewNode.IsA("vtkMRMLViewNode"))

  def onSliceViewModeSelected(self):
    sweepMode = (self.sliceModeWidget.currentText == "sweep")
    self.startSliceOffsetSliderWidget.setEnabled(sweepMode)
    self.endSliceOffsetSliderWidget.setEnabled(sweepMode)

  def setSliceOffset(self, offset):
    sliceLogic = self.logic.getSliceLogicFromSliceNode(self.viewNodeSelector.currentNode())
    sliceLogic.SetSliceOffset(offset) 
  
  def onSelect(self):
    self.captureButton.enabled = self.viewNodeSelector.currentNode()

  def onCaptureButton(self):
    self.logic.setFfmpegPath(self.ffmpegPathSelector.currentPath)

    slicer.app.setOverrideCursor(qt.Qt.WaitCursor)
    self.statusLabel.plainText = ''

    videoOutputRequested = self.videoExportCheckBox.checked
    viewNode = self.viewNodeSelector.currentNode()
    numberOfSteps = int(self.numberOfStepsSliderWidget.value)
    outputDir = self.outputDirSelector.currentPath

    # Need to create a new random file pattern if video output is requested to make sure that new image files are not mixed up with
    # existing files in the output directory
    imageFileNamePattern = self.logic.getRandomFilePattern() if videoOutputRequested else self.fileNamePatternWidget.text

    try:
      if viewNode.IsA("vtkMRMLSliceNode"):
        if self.sliceModeWidget.currentText == "sweep":
          self.logic.captureSliceSweep(viewNode, self.startSliceOffsetSliderWidget.value, self.endSliceOffsetSliderWidget.value, numberOfSteps, outputDir, imageFileNamePattern)
        elif self.sliceModeWidget.currentText == "fade":
          self.logic.captureSliceFade(viewNode, numberOfSteps, outputDir, imageFileNamePattern)
      elif viewNode.IsA("vtkMRMLViewNode"):
        self.logic.capture3dViewRotation(viewNode, self.startRotationSliderWidget.value, self.endRotationSliderWidget.value,
                                         numberOfSteps, outputDir, imageFileNamePattern)
      else:
        raise ValueError('Unsupported view node type.')

      if videoOutputRequested:
        fps = numberOfSteps / self.videoLengthSliderWidget.value
        self.logic.createVideo(fps, self.extraVideoOptionsWidget.text,
                               outputDir, imageFileNamePattern, self.videoFileNameWidget.text)
        self.logic.deleteTemporaryFiles(outputDir, imageFileNamePattern, numberOfSteps)

      self.addLog("Done.")
    except Exception as e:
      self.addLog("Unexpected error: {0}".format(e.message))
      import traceback
      traceback.print_exc()
    slicer.app.restoreOverrideCursor()

#
# ScreenCaptureLogic
#

class ScreenCaptureLogic(ScriptedLoadableModuleLogic):
  """This class should implement all the actual
  computation done by your module.  The interface
  should be such that other python code can import
  this class and make use of the functionality without
  requiring an instance of the Widget.
  Uses ScriptedLoadableModuleLogic base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def addLog(self, text):
    logging.info(text)
    if self.logCallback:
      self.logCallback(text)

  def getRandomFilePattern(self):
    import string
    import random
    numberOfRandomChars=5
    randomString = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(numberOfRandomChars))
    filePathPattern = "tmp-"+randomString+"-%05d.png"
    return filePathPattern

  def getFfmpegPath(self):
    settings = qt.QSettings()
    if settings.contains('General/ffmpegPath'):
      return settings.value('General/ffmpegPath')
    return ''

  def setFfmpegPath(self, ffmpegPath):
    # don't save it if already saved
    settings = qt.QSettings()
    if settings.contains('General/ffmpegPath'):
      if ffmpegPath == settings.value('General/ffmpegPath'):
        return
    settings.setValue('General/ffmpegPath',ffmpegPath)

  def getSliceLogicFromSliceNode(self, sliceNode):
    lm = slicer.app.layoutManager()
    sliceLogic = lm.sliceWidget(sliceNode.GetLayoutName()).sliceLogic()
    return sliceLogic
  
  def getSliceOffsetRange(self, sliceNode):
    sliceLogic = self.getSliceLogicFromSliceNode(sliceNode)
        
    sliceBounds = [0, -1, 0, -1, 0, -1]
    sliceLogic.GetLowestVolumeSliceBounds(sliceBounds)
    sliceOffsetMin = sliceBounds[4]
    sliceOffsetMax = sliceBounds[5]

    # increase range if it is empty
    # to allow capturing even when no volumes are shown in slice views
    if sliceOffsetMin == sliceOffsetMax:
      sliceOffsetMin = sliceLogic.GetSliceOffset()-100
      sliceOffsetMax = sliceLogic.GetSliceOffset()+100
      
    return sliceOffsetMin, sliceOffsetMax
    
  def getSliceOffsetResolution(self, sliceNode):
    sliceLogic = self.getSliceLogicFromSliceNode(sliceNode)
    
    sliceOffsetResolution = 1.0
    sliceSpacing = sliceLogic.GetLowestVolumeSliceSpacing();
    if sliceSpacing is not None and sliceSpacing[2]>0:
      sliceOffsetResolution = sliceSpacing[2]

    return sliceOffsetResolution
      
  def captureSliceSweep(self, sliceNode, startSliceOffset, endSliceOffset, numberOfImages, outputDir, outputFilenamePattern):
    if not sliceNode.IsMappedInLayout():
      raise ValueError('Selected slice view is not visible in the current layout.')

    if not os.path.exists(outputDir):
      os.makedirs(outputDir)
    filePathPattern = os.path.join(outputDir,outputFilenamePattern)

    sliceLogic = self.getSliceLogicFromSliceNode(sliceNode)
    originalSliceOffset = sliceLogic.GetSliceOffset()
    
    sliceView = slicer.app.layoutManager().sliceWidget(sliceNode.GetLayoutName()).sliceView()
    compositeNode = sliceLogic.GetSliceCompositeNode()
    offsetStepSize = (endSliceOffset-startSliceOffset)/(numberOfImages-1)
    for offsetIndex in range(numberOfImages):
      sliceLogic.SetSliceOffset(startSliceOffset+offsetIndex*offsetStepSize)
      sliceView.forceRender()
      pixmap = qt.QPixmap().grabWidget(sliceView)
      filename = filePathPattern % offsetIndex
      self.addLog("Write "+filename)
      pixmap.save(filename)

    sliceLogic.SetSliceOffset(originalSliceOffset)

  def captureSliceFade(self, sliceNode, numberOfImages, outputDir,
                        outputFilenamePattern):
    if not sliceNode.IsMappedInLayout():
      raise ValueError('Selected slice view is not visible in the current layout.')

    if not os.path.exists(outputDir):
      os.makedirs(outputDir)
    filePathPattern = os.path.join(outputDir, outputFilenamePattern)

    sliceLogic = self.getSliceLogicFromSliceNode(sliceNode)
    sliceView = slicer.app.layoutManager().sliceWidget(sliceNode.GetLayoutName()).sliceView()
    compositeNode = sliceLogic.GetSliceCompositeNode()
    originalForegroundOpacity = compositeNode.GetForegroundOpacity()
    startForegroundOpacity = 0.0
    endForegroundOpacity = 1.0
    opacityStepSize = (endForegroundOpacity - startForegroundOpacity) / (numberOfImages - 1)
    for offsetIndex in range(numberOfImages):
      compositeNode.SetForegroundOpacity(startForegroundOpacity + offsetIndex * opacityStepSize)
      sliceView.forceRender()
      pixmap = qt.QPixmap().grabWidget(sliceView)
      filename = filePathPattern % offsetIndex
      self.addLog("Write " + filename)
      pixmap.save(filename)

    compositeNode.SetForegroundOpacity(originalForegroundOpacity)

  def capture3dViewRotation(self, viewNode, startRotation, endRotation, numberOfImages, outputDir,
                        outputFilenamePattern):
    """
    Acquire a set of screenshots of the 3D view while rotating it.
    """

    if not os.path.exists(outputDir):
      os.makedirs(outputDir)

    filePathPattern = os.path.join(outputDir, outputFilenamePattern)

    renderView = None
    lm = slicer.app.layoutManager()
    for widgetIndex in range(lm.threeDViewCount):
      view = lm.threeDWidget(widgetIndex).threeDView()
      if viewNode == view.mrmlViewNode():
        renderView = view
        break
    if not renderView:
      raise ValueError('Selected 3D view is not visible in the current layout.')

    # Save original orientation and go to start orientation
    originalPitchRollYawIncrement = renderView.pitchRollYawIncrement
    originalYawDirection = renderView.yawDirection
    renderView.setPitchRollYawIncrement(startRotation)
    renderView.yawDirection = renderView.YawLeft
    renderView.yaw()

    # Rotate step-by-step
    rotationStepSize = (endRotation + startRotation) / (numberOfImages - 1)
    renderView.setPitchRollYawIncrement(rotationStepSize)
    renderView.yawDirection = renderView.YawRight
    for offsetIndex in range(numberOfImages):
      renderView.forceRender()
      pixmap = qt.QPixmap().grabWidget(view)
      filename = filePathPattern % offsetIndex
      self.addLog("Write " + filename)
      pixmap.save(filename)
      renderView.yaw()

    # Restore original orientation and rotation step size & direction
    renderView.yawDirection = renderView.YawLeft
    renderView.yaw()
    renderView.setPitchRollYawIncrement(endRotation)
    renderView.yaw()
    renderView.setPitchRollYawIncrement(originalPitchRollYawIncrement)
    renderView.yawDirection = originalYawDirection

  def createVideo(self, frameRate, extraOptions, outputDir, imageFileNamePattern, videoFileName):
    self.addLog("Export to video...")

    # Get ffmpeg
    import os.path
    ffmpegPath = os.path.abspath(self.getFfmpegPath())
    if not ffmpegPath:
      raise ValueError("Video creation failed: ffmpeg executable path is not defined")
    if not os.path.isfile(ffmpegPath):
      raise ValueError("Video creation failed: ffmpeg executable path is invalid: "+ffmpegPath)

    filePathPattern = os.path.join(outputDir, imageFileNamePattern)
    outputVideoFilePath = os.path.join(outputDir, videoFileName)
    ffmpegParams = [ffmpegPath,
                    "-y", # overwrite without asking
                    "-r", str(frameRate),
                    "-start_number", "0",
                    "-i", str(filePathPattern)]
    ffmpegParams += filter(None, extraOptions.split(' '))
    ffmpegParams.append(outputVideoFilePath)

    logging.debug("ffmpeg parameters: "+repr(ffmpegParams))

    import subprocess
    p = subprocess.Popen(ffmpegParams, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output = p.communicate()
    if p.returncode != 0:
      self.addLog("ffmpeg error output: " + output[1])
      raise ValueError("ffmpeg returned with error")
    else:
      self.addLog("Video export succeeded to file: "+outputVideoFilePath)
      logging.debug("ffmpeg standard output: " + output[0])
      logging.debug("ffmpeg error output: " + output[1])

  def deleteTemporaryFiles(self, outputDir, imageFileNamePattern, numberOfImages):
    """
    Delete files after a video has been created from them.
    """
    import os
    filePathPattern = os.path.join(outputDir, imageFileNamePattern)
    for imageIndex in range(numberOfImages):
      filename = filePathPattern % imageIndex
      logging.debug("Delete temporary file " + filename)
      os.remove(filename)

  def takeScreenshot(self,name,description,type=-1):
    # show the message even if not taking a screen shot
    slicer.util.delayDisplay('Take screenshot: '+description+'.\nResult is available in the Annotations module.', 3000)

    lm = slicer.app.layoutManager()
    # switch on the type to get the requested window
    widget = 0
    if type == slicer.qMRMLScreenShotDialog.FullLayout:
      # full layout
      widget = lm.viewport()
    elif type == slicer.qMRMLScreenShotDialog.ThreeD:
      # just the 3D window
      widget = lm.threeDWidget(0).threeDView()
    elif type == slicer.qMRMLScreenShotDialog.Red:
      # red slice window
      widget = lm.sliceWidget("Red")
    elif type == slicer.qMRMLScreenShotDialog.Yellow:
      # yellow slice window
      widget = lm.sliceWidget("Yellow")
    elif type == slicer.qMRMLScreenShotDialog.Green:
      # green slice window
      widget = lm.sliceWidget("Green")
    else:
      # default to using the full window
      widget = slicer.util.mainWindow()
      # reset the type so that the node is set correctly
      type = slicer.qMRMLScreenShotDialog.FullLayout

    # grab and convert to vtk image data
    qpixMap = qt.QPixmap().grabWidget(widget)
    qimage = qpixMap.toImage()
    imageData = vtk.vtkImageData()
    slicer.qMRMLUtils().qImageToVtkImageData(qimage,imageData)

    annotationLogic = slicer.modules.annotations.logic()
    annotationLogic.CreateSnapShot(name, description, type, 1, imageData)

class ScreenCaptureTest(ScriptedLoadableModuleTest):
  """
  This is the test case for your scripted module.
  Uses ScriptedLoadableModuleTest base class, available at:
  https://github.com/Slicer/Slicer/blob/master/Base/Python/slicer/ScriptedLoadableModule.py
  """

  def setUp(self):
    """ Do whatever is needed to reset the state - typically a scene clear will be enough.
    """
    slicer.mrmlScene.Clear(0)

  def runTest(self):
    """Run as few or as many tests as needed here.
    """
    self.setUp()
    self.test_ScreenCapture1()

  def test_ScreenCapture1(self):
    """ Ideally you should have several levels of tests.  At the lowest level
    tests should exercise the functionality of the logic with different input
    (both valid and invalid).  At higher levels your tests should emulate the
    way the user would interact with your code and confirm that it still works
    the way you intended.
    One of the most important features of the tests is that it should alert other
    developers when their changes will have an impact on the behavior of your
    module.  For example, if a developer removes a feature that you depend on,
    your test should break so they know that the feature is needed.
    """

    self.delayDisplay("Starting the test")
    #
    # first, get some data
    #
    import urllib
    downloads = (
        ('http://slicer.kitware.com/midas3/download?items=5767', 'FA.nrrd', slicer.util.loadVolume),
        )

    for url,name,loader in downloads:
      filePath = slicer.app.temporaryPath + '/' + name
      if not os.path.exists(filePath) or os.stat(filePath).st_size == 0:
        logging.info('Requesting download %s from %s...\n' % (name, url))
        urllib.urlretrieve(url, filePath)
      if loader:
        logging.info('Loading %s...' % (name,))
        loader(filePath)
    self.delayDisplay('Finished with download and loading')

    volumeNode = slicer.util.getNode(pattern="FA")
    logic = ScreenCaptureLogic()
    self.assertIsNotNone( logic.hasImageData(volumeNode) )
    self.delayDisplay('Test passed!')
