# -*- coding: utf-8 -*-

# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2016 sliptonic <shopinthewoods@gmail.com>               *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

from __future__ import print_function
import FreeCAD
import Path
import PathScripts.PathLog as PathLog
from PySide import QtCore, QtGui
from PathScripts import PathUtils
import Part
from PathScripts.PathUtils import waiting_effects
from PathScripts.PathUtils import makeWorkplane
from PathScripts.PathUtils import depth_params

if True:
    PathLog.setLevel(PathLog.Level.DEBUG, PathLog.thisModule())
    PathLog.trackModule(PathLog.thisModule())
else:
    PathLog.setLevel(PathLog.Level.INFO, PathLog.thisModule())

if FreeCAD.GuiUp:
    import FreeCADGui


# Qt tanslation handling
def translate(context, text, disambig=None):
    return QtCore.QCoreApplication.translate(context, text, disambig)

__title__ = "Path Mill Face Operation"
__author__ = "sliptonic (Brad Collette)"
__url__ = "http://www.freecadweb.org"

"""Path Face object and FreeCAD command"""


class ObjectFace:

    def __init__(self, obj):
        obj.addProperty("App::PropertyLinkSubList", "Base", "Path", QtCore.QT_TRANSLATE_NOOP("App::Property", "The base geometry of this object"))
        obj.addProperty("App::PropertyBool", "Active", "Path", QtCore.QT_TRANSLATE_NOOP("App::Property", "Make False, to prevent operation from generating code"))
        obj.addProperty("App::PropertyString", "Comment", "Path", QtCore.QT_TRANSLATE_NOOP("App::Property", "An optional comment for this profile"))
        obj.addProperty("App::PropertyString", "UserLabel", "Path", QtCore.QT_TRANSLATE_NOOP("App::Property", "User Assigned Label"))

        # Tool Properties
        obj.addProperty("App::PropertyLink", "ToolController", "Path", QtCore.QT_TRANSLATE_NOOP("App::Property", "The tool controller that will be used to calculate the path"))

        # Depth Properties
        obj.addProperty("App::PropertyDistance", "ClearanceHeight", "Depth", QtCore.QT_TRANSLATE_NOOP("App::Property", "The height needed to clear clamps and obstructions"))
        obj.addProperty("App::PropertyDistance", "SafeHeight", "Depth", QtCore.QT_TRANSLATE_NOOP("App::Property", "Rapid Safety Height between locations."))
        obj.addProperty("App::PropertyFloatConstraint", "StepDown", "Depth", QtCore.QT_TRANSLATE_NOOP("App::Property", "Incremental Step Down of Tool"))
        obj.StepDown = (0.0, 0.01, 100.0, 0.5)
        obj.addProperty("App::PropertyDistance", "StartDepth", "Depth", QtCore.QT_TRANSLATE_NOOP("App::Property", "Starting Depth of Tool- first cut depth in Z"))
        obj.addProperty("App::PropertyDistance", "FinalDepth", "Depth", QtCore.QT_TRANSLATE_NOOP("App::Property", "Final Depth of Tool- lowest value in Z"))
        obj.addProperty("App::PropertyDistance", "FinishDepth", "Depth", QtCore.QT_TRANSLATE_NOOP("App::Property", "Maximum material removed on final pass."))

        # Face Properties
        obj.addProperty("App::PropertyEnumeration", "CutMode", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "The direction that the toolpath should go around the part ClockWise CW or CounterClockWise CCW"))
        obj.CutMode = ['Climb', 'Conventional']
        obj.addProperty("App::PropertyDistance", "PassExtension", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "How far the cutter should extend past the boundary"))
        obj.addProperty("App::PropertyEnumeration", "StartAt", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "Start Faceing at center or boundary"))
        obj.StartAt = ['Center', 'Edge']
        obj.addProperty("App::PropertyPercent", "StepOver", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "Percent of cutter diameter to step over on each pass"))
        obj.addProperty("App::PropertyBool", "KeepToolDown", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "Attempts to avoid unnecessary retractions."))
        obj.addProperty("App::PropertyBool", "ZigUnidirectional", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "Lifts tool at the end of each pass to respect cut mode."))
        obj.addProperty("App::PropertyBool", "UseZigZag", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "Use Zig Zag pattern to clear area."))
        obj.addProperty("App::PropertyFloat", "ZigZagAngle", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "Angle of the zigzag pattern"))
        obj.addProperty("App::PropertyEnumeration", "BoundaryShape", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "Shape to use for calculating Boundary"))
        obj.BoundaryShape = ['Perimeter', 'Boundbox']
        obj.addProperty("App::PropertyEnumeration", "OffsetPattern", "Face", QtCore.QT_TRANSLATE_NOOP("App::Property", "clearing pattern to use"))
        obj.OffsetPattern = ['ZigZag', 'Offset', 'Spiral', 'ZigZagOffset', 'Line', 'Grid', 'Triangle']

        # Start Point Properties
        obj.addProperty("App::PropertyVector", "StartPoint", "Start Point", QtCore.QT_TRANSLATE_NOOP("App::Property", "The start point of this path"))
        obj.addProperty("App::PropertyBool", "UseStartPoint", "Start Point", QtCore.QT_TRANSLATE_NOOP("App::Property", "make True, if specifying a Start Point"))

        # Debug Parameters
        obj.addProperty("App::PropertyString", "AreaParams", "Path")
        obj.setEditorMode('AreaParams', 2)  # hide
        obj.addProperty("App::PropertyString", "PathParams", "Path")
        obj.setEditorMode('PathParams', 2)  # hide
        obj.addProperty("Part::PropertyPartShape", "removalshape", "Path")
        obj.setEditorMode('removalshape', 2)  # hide

        if FreeCAD.GuiUp:
            _ViewProviderFace(obj.ViewObject)

        obj.Proxy = self

    def onChanged(self, obj, prop):
        PathLog.track(prop)
        if prop == "StepOver":
            if obj.StepOver == 0:
                obj.StepOver = 1
        if prop in ['AreaParams', 'PathParams', 'removalshape']:
            obj.setEditorMode(prop, 2)

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None

    def setDepths(self, obj):
        PathLog.track()
        parentJob = PathUtils.findParentJob(obj)
        if parentJob is None:
            return
        baseobject = parentJob.Base
        if baseobject is None:
            return

        d = PathUtils.guessDepths(baseobject.Shape, None)
        obj.ClearanceHeight = d.clearance_height
        obj.SafeHeight = d.safe_height + 1
        obj.StartDepth = d.safe_height
        obj.FinalDepth = d.start_depth
        obj.StepDown = obj.StartDepth.Value-obj.FinalDepth.Value

    def addFacebase(self, obj, ss, sub=""):
        baselist = obj.Base
        if baselist is None:
            baselist = []
        if len(baselist) == 0:  # When adding the first base object, guess at heights
            subshape = [ss.Shape.getElement(sub)]
            d = PathUtils.guessDepths(ss.Shape, subshape)
            obj.ClearanceHeight = d.clearance_height
            obj.SafeHeight = d.safe_height + 1
            obj.StartDepth = d.safe_height
            obj.FinalDepth = d.final_depth
            obj.StepDown = obj.StartDepth.Value-obj.FinalDepth.Value

        item = (ss, sub)
        if item in baselist:
            FreeCAD.Console.PrintWarning(translate("Path", "this object already in the list" + "\n"))
        elif PathUtils.findParentJob(obj).Base.Name != ss.Name:
            PathLog.debug("parentbase: {}, selectionobj: {}".format(PathUtils.findParentJob(obj).Base.Name, ss.Name))
            FreeCAD.Console.PrintWarning(translate("Path", "Please select features from the Job model object" + "\n"))
        else:
            baselist.append(item)
        PathLog.debug('baselist: {}'.format(baselist))
        obj.Base = baselist

    def getStock(self, obj):
        """find and return a stock object from hosting project if any"""
        for o in obj.InList:
            if hasattr(o, "Group"):
                for g in o.Group:
                    if hasattr(g, "Height_Allowance"):
                        return o
        # not found? search one level up
        for o in obj.InList:
            return self.getStock(o)
        return None

    @waiting_effects
    def _buildPathArea(self, obj, baseobject):
        """build the face path using PathArea"""

        PathLog.track()
        boundary = Path.Area()
        boundary.setPlane(makeWorkplane(baseobject))
        boundary.add(baseobject)

        stepover = (self.radius * 2) * (float(obj.StepOver)/100)

        pocketparams = {'Fill': 0,
                        'Coplanar': 0,
                        'PocketMode': 1,
                        'SectionCount': -1,
                        'Angle': obj.ZigZagAngle,
                        'FromCenter': (obj.StartAt == "Center"),
                        'PocketStepover': stepover,
                        'PocketExtraOffset': 0 - obj.PassExtension.Value}

        Pattern = ['ZigZag', 'Offset', 'Spiral', 'ZigZagOffset', 'Line', 'Grid', 'Triangle']
        pocketparams['PocketMode'] = Pattern.index(obj.OffsetPattern) + 1

        offsetval = self.radius
        pocketparams['ToolRadius'] = offsetval

        heights = [i for i in self.depthparams]
        boundary.setParams(**pocketparams)
        obj.AreaParams = str(boundary.getParams())
        sections = boundary.makeSections(mode=0, project=False, heights=heights)

        params = {'feedrate': self.horizFeed,
                  'feedrate_v': self.vertFeed,
                  'verbose': True,
                  'resume_height': obj.StepDown,
                  'retraction': obj.ClearanceHeight.Value}

        pp = []

        if obj.UseStartPoint and obj.StartPoint is not None:
            params['start'] = obj.StartPoint

        # store the params for debugging. Don't need the shape.
        obj.PathParams = str(params)
        PathLog.debug("Generating Path with params: {}".format(params))

        for sec in sections:
            shape = sec.getShape()
            respath = Path.fromShapes(shape, **params)
            # Insert any entry code to the layer

            # append the layer path
            pp.extend(respath.Commands)
            respath.Commands = pp

        return respath

    def execute(self, obj):
        PathLog.track()
        if not obj.Active:
            path = Path.Path("(inactive operation)")
            obj.Path = path
            obj.ViewObject.Visibility = False
            return

        commandlist = []
        toolLoad = obj.ToolController

        self.depthparams = depth_params(
                clearance_height=obj.ClearanceHeight.Value,
                safe_height=obj.SafeHeight.Value,
                start_depth=obj.SafeHeight.Value,
                step_down=obj.StepDown,
                z_finish_step=obj.FinishDepth.Value,
                final_depth=obj.FinalDepth.Value,
                user_depths=None)

        if toolLoad is None or toolLoad.ToolNumber == 0:
            FreeCAD.Console.PrintError("No Tool Controller is selected. We need a tool to build a Path.")
            return
        else:
            self.vertFeed = toolLoad.VertFeed.Value
            self.horizFeed = toolLoad.HorizFeed.Value
            self.vertRapid = toolLoad.VertRapid.Value
            self.horizRapid = toolLoad.HorizRapid.Value
            tool = toolLoad.Proxy.getTool(toolLoad)

            if tool.Diameter == 0:
                FreeCAD.Console.PrintError("No Tool found or diameter is zero. We need a tool to build a Path.")
                return
            else:
                self.radius = tool.Diameter/2

        commandlist.append(Path.Command("(" + obj.Label + ")"))

        # Facing is done either against base objects
        if obj.Base:
            PathLog.debug("obj.Base: {}".format(obj.Base))
            faces = []
            for b in obj.Base:
                for sub in b[1]:
                    shape = getattr(b[0].Shape, sub)
                    if isinstance(shape, Part.Face):
                        faces.append(shape)
                    else:
                        PathLog.debug('The base subobject is not a face')
                        return
            planeshape = Part.makeCompound(faces)
            PathLog.info("Working on a collection of faces {}".format(faces))

        # If no base object, do planing of top surface of entire model
        else:
            parentJob = PathUtils.findParentJob(obj)
            if parentJob is None:
                PathLog.debug("No base object. No parent job found")
                return
            baseobject = parentJob.Base
            if baseobject is None:
                PathLog.debug("Parent job exists but no Base Object")
                return
            planeshape = baseobject.Shape
            PathLog.info("Working on a shape {}".format(baseobject.Name))

        # if user wants the boundbox, calculate that
        PathLog.info("Boundary Shape: {}".format(obj.BoundaryShape))
        bb = planeshape.BoundBox
        if obj.BoundaryShape == 'Boundbox':
            bbperim = Part.makeBox(bb.XLength, bb.YLength, 1, FreeCAD.Vector(bb.XMin, bb.YMin, bb.ZMin), FreeCAD.Vector(0, 0, 1))
            env = PathUtils.getEnvelope(partshape=bbperim, depthparams=self.depthparams)
        else:
            env = PathUtils.getEnvelope(partshape=planeshape, depthparams=self.depthparams)

        # save the envelope for reference
        obj.removalshape = env

        try:
            commandlist.extend(self._buildPathArea(obj, env).Commands)
        except Exception as e:
            FreeCAD.Console.PrintError(e)
            FreeCAD.Console.PrintError(translate("Path_MillFace", "The selected settings did not produce a valid path.\n"))

        # Let's finish by rapid to clearance...just for safety
        commandlist.append(Path.Command("G0", {"Z": obj.ClearanceHeight.Value}))

        path = Path.Path(commandlist)
        obj.Path = path
        obj.ViewObject.Visibility = True


class _ViewProviderFace:

    def __init__(self, vobj):
        vobj.Proxy = self

    def attach(self, vobj):
        self.Object = vobj.Object
        return

    def deleteObjectsOnReject(self):
        return hasattr(self, 'deleteOnReject') and self.deleteOnReject

    def setEdit(self, vobj, mode=0):
        FreeCADGui.Control.closeDialog()
        taskd = TaskPanel(vobj.Object, self.deleteObjectsOnReject())
        taskd.obj = vobj.Object
        taskd.setupUi()
        FreeCADGui.Control.showDialog(taskd)
        self.deleteOnReject = False
        return True

    def getIcon(self):
        return ":/icons/Path-Face.svg"

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return None


class CommandPathMillFace:

    def GetResources(self):
        return {'Pixmap': 'Path-Face',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("PathFace", "Face"),
                'Accel': "P, O",
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("PathFace", "Create a Facing Operation from a model or face")}

    def IsActive(self):
        if FreeCAD.ActiveDocument is not None:
            for o in FreeCAD.ActiveDocument.Objects:
                if o.Name[:3] == "Job":
                        return True
        return False

    def Activated(self):
        # if everything is ok, execute and register the transaction in the undo/redo stack
        FreeCAD.ActiveDocument.openTransaction(translate("PathFace", "Create Face"))
        FreeCADGui.addModule("PathScripts.PathMillFace")
        FreeCADGui.doCommand('obj = FreeCAD.ActiveDocument.addObject("Path::FeaturePython", "Face")')
        FreeCADGui.doCommand('PathScripts.PathMillFace.ObjectFace(obj)')
        FreeCADGui.doCommand('obj.ViewObject.Proxy.deleteOnReject = True')
        FreeCADGui.doCommand('PathScripts.PathUtils.addToJob(obj)')
        FreeCADGui.doCommand('obj.ToolController = PathScripts.PathUtils.findToolController(obj)')
        FreeCADGui.doCommand('PathScripts.PathMillFace.ObjectFace.setDepths(obj.Proxy, obj)')

        FreeCADGui.doCommand('obj.Active = True')
        FreeCADGui.doCommand('obj.StepOver = 50')
        FreeCADGui.doCommand('obj.StepDown = 1.0')
        FreeCADGui.doCommand('obj.ZigZagAngle = 45.0')
        FreeCAD.ActiveDocument.commitTransaction()

        FreeCADGui.doCommand('obj.ViewObject.startEditing()')


class _CommandSetFaceStartPoint:
    def GetResources(self):
        return {'Pixmap': 'Path-StartPoint',
                'MenuText': QtCore.QT_TRANSLATE_NOOP("PathFace", "Pick Start Point"),
                'ToolTip': QtCore.QT_TRANSLATE_NOOP("PathFace", "Pick Start Point")}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def setpoint(self, point, o):
        obj = FreeCADGui.Selection.getSelection()[0]
        obj.StartPoint.x = point.x
        obj.StartPoint.y = point.y

    def Activated(self):
        FreeCADGui.Snapper.getPoint(callback=self.setpoint)


class TaskPanel:
    def __init__(self, obj, deleteOnReject):
        FreeCAD.ActiveDocument.openTransaction(translate("Path_MillFace", "Mill Facing Operation"))
        # self.form = FreeCADGui.PySideUic.loadUi(FreeCAD.getHomePath() + "Mod/Path/MillFaceEdit.ui")
        self.form = FreeCADGui.PySideUic.loadUi(":/panels/MillFaceEdit.ui")
        self.deleteOnReject = deleteOnReject
        self.obj = obj
        self.isDirty = True

    def accept(self):
        FreeCADGui.Control.closeDialog()
        FreeCADGui.ActiveDocument.resetEdit()
        FreeCAD.ActiveDocument.commitTransaction()
        FreeCADGui.Selection.removeObserver(self.s)
        if self.isDirty:
            FreeCAD.ActiveDocument.recompute()

    def reject(self):
        FreeCADGui.Control.closeDialog()
        FreeCADGui.ActiveDocument.resetEdit()
        FreeCAD.ActiveDocument.abortTransaction()
        FreeCADGui.Selection.removeObserver(self.s)
        if self.deleteOnReject:
            FreeCAD.ActiveDocument.openTransaction(translate("Path_MillFace", "Uncreate Mill Face Operation"))
            FreeCAD.ActiveDocument.removeObject(self.obj.Name)
            FreeCAD.ActiveDocument.commitTransaction()
        FreeCAD.ActiveDocument.recompute()

    def clicked(self, button):
        if button == QtGui.QDialogButtonBox.Apply:
            self.getFields()
            FreeCAD.ActiveDocument.recompute()
            self.isDirty = False

    def getFields(self):
        if self.obj:
            if hasattr(self.obj, "StartDepth"):
                self.obj.StartDepth = FreeCAD.Units.Quantity(self.form.startDepth.text()).Value
            if hasattr(self.obj, "FinalDepth"):
                self.obj.FinalDepth = FreeCAD.Units.Quantity(self.form.finalDepth.text()).Value
            if hasattr(self.obj, "FinishDepth"):
                self.obj.FinishDepth = FreeCAD.Units.Quantity(self.form.finishDepth.text()).Value
            if hasattr(self.obj, "StepDown"):
                self.obj.StepDown = FreeCAD.Units.Quantity(self.form.stepDown.text()).Value
            if hasattr(self.obj, "SafeHeight"):
                self.obj.SafeHeight = FreeCAD.Units.Quantity(self.form.safeHeight.text()).Value
            if hasattr(self.obj, "ClearanceHeight"):
                self.obj.ClearanceHeight = FreeCAD.Units.Quantity(self.form.clearanceHeight.text()).Value
            if hasattr(self.obj, "PassExtension"):
                self.obj.PassExtension = FreeCAD.Units.Quantity(self.form.extraOffset.text()).Value
            if hasattr(self.obj, "CutMode"):
                self.obj.CutMode = str(self.form.cutMode.currentText())
            if hasattr(self.obj, "ZigZagAngle"):
                self.obj.ZigZagAngle = FreeCAD.Units.Quantity(self.form.zigZagAngle.text()).Value
            if hasattr(self.obj, "StepOver"):
                self.obj.StepOver = self.form.stepOverPercent.value()
            if hasattr(self.obj, "BoundaryShape"):
                self.obj.BoundaryShape = str(self.form.boundaryShape.currentText())
            if hasattr(self.obj, "OffsetPattern"):
                self.obj.OffsetPattern = str(self.form.offsetpattern.currentText())

            if hasattr(self.obj, "ToolController"):
                tc = PathUtils.findToolController(self.obj, self.form.uiToolController.currentText())
                self.obj.ToolController = tc

        self.isDirty = True

    def setFields(self):
        self.form.startDepth.setText(FreeCAD.Units.Quantity(self.obj.StartDepth.Value, FreeCAD.Units.Length).UserString)
        self.form.finalDepth.setText(FreeCAD.Units.Quantity(self.obj.FinalDepth.Value, FreeCAD.Units.Length).UserString)
        self.form.finishDepth.setText(FreeCAD.Units.Quantity(self.obj.FinishDepth.Value, FreeCAD.Units.Length).UserString)
        self.form.stepDown.setText(FreeCAD.Units.Quantity(self.obj.StepDown, FreeCAD.Units.Length).UserString)
        self.form.safeHeight.setText(FreeCAD.Units.Quantity(self.obj.SafeHeight.Value, FreeCAD.Units.Length).UserString)
        self.form.clearanceHeight.setText(FreeCAD.Units.Quantity(self.obj.ClearanceHeight.Value,  FreeCAD.Units.Length).UserString)

        self.form.stepOverPercent.setValue(self.obj.StepOver)
        self.form.zigZagAngle.setText(FreeCAD.Units.Quantity(self.obj.ZigZagAngle, FreeCAD.Units.Angle).UserString)
        self.form.extraOffset.setValue(self.obj.PassExtension.Value)

        index = self.form.cutMode.findText(
                self.obj.CutMode, QtCore.Qt.MatchFixedString)
        if index >= 0:

            self.form.cutMode.blockSignals(True)
            self.form.cutMode.setCurrentIndex(index)
            self.form.cutMode.blockSignals(False)

        index = self.form.boundaryShape.findText(
                self.obj.BoundaryShape, QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.form.boundaryShape.blockSignals(True)
            self.form.boundaryShape.setCurrentIndex(index)
            self.form.boundaryShape.blockSignals(False)

        index = self.form.offsetpattern.findText(
                self.obj.OffsetPattern, QtCore.Qt.MatchFixedString)
        if index >= 0:
            self.form.offsetpattern.blockSignals(True)
            self.form.offsetpattern.setCurrentIndex(index)
            self.form.offsetpattern.blockSignals(False)

        for i in self.obj.Base:
            for sub in i[1]:
                self.form.baseList.addItem(i[0].Name + "." + sub)

        controllers = PathUtils.getToolControllers(self.obj)
        labels = [c.Label for c in controllers]
        self.form.uiToolController.blockSignals(True)
        self.form.uiToolController.addItems(labels)
        self.form.uiToolController.blockSignals(False)

        if self.obj.ToolController is None:
            self.obj.ToolController = PathUtils.findToolController(self.obj)

        if self.obj.ToolController is not None:
            index = self.form.uiToolController.findText(
                self.obj.ToolController.Label, QtCore.Qt.MatchFixedString)
            if index >= 0:
                self.form.uiToolController.blockSignals(True)
                self.form.uiToolController.setCurrentIndex(index)
                self.form.uiToolController.blockSignals(False)

    def open(self):
        self.s = SelObserver()
        # install the function mode resident
        FreeCADGui.Selection.addObserver(self.s)

    def addBase(self):
        # check that the selection contains exactly what we want
        selection = FreeCADGui.Selection.getSelectionEx()

        if len(selection) != 1:
            FreeCAD.Console.PrintError(translate("PathProject", "Please select only faces from one solid\n"))
            return
        sel = selection[0]
        if not sel.HasSubObjects:
            FreeCAD.Console.PrintError(translate("PathProject", "Please select faces from one solid\n"))
            return
        if not selection[0].SubObjects[0].ShapeType == "Face":
            FreeCAD.Console.PrintError(translate("PathProject", "Please select faces from one solid\n"))
            return
        for i in sel.SubElementNames:
            self.obj.Proxy.addFacebase(self.obj, sel.Object, i)

        self.setFields()  # defaults may have changed.  Reload.
        self.form.baseList.clear()

        for i in self.obj.Base:
            for sub in i[1]:
                self.form.baseList.addItem(i[0].Name + "." + sub)

    def deleteBase(self):
        dlist = self.form.baseList.selectedItems()
        newlist = []
        for d in dlist:
            deletebase = d.text().partition(".")[0]
            deletesub = d.text().partition(".")[2]

            for i in self.obj.Base:
                sublist = []
                basesubs = i[1]
                for sub in basesubs:
                    if sub != deletesub:
                        sublist.append(sub)
                if len(sublist) >= 1:
                    newlist.append((deletebase, tuple(sublist)))

                if i[0].Name != d.text().partition(".")[0] and d.text().partition(".")[2] not in i[1]:
                    newlist.append(i)
            self.form.baseList.takeItem(self.form.baseList.row(d))
        self.obj.Base = newlist

    def itemActivated(self):
        FreeCADGui.Selection.clearSelection()
        slist = self.form.baseList.selectedItems()
        for i in slist:
            objstring = i.text().partition(".")
            obj = FreeCAD.ActiveDocument.getObject(objstring[0])
            if objstring[2] != "":
                FreeCADGui.Selection.addSelection(obj, objstring[2])
            else:
                FreeCADGui.Selection.addSelection(obj)

        FreeCADGui.updateGui()

    def reorderBase(self):
        newlist = []
        for i in range(self.form.baseList.count()):
            s = self.form.baseList.item(i).text()
            objstring = s.partition(".")

            obj = FreeCAD.ActiveDocument.getObject(objstring[0])
            item = (obj, str(objstring[2]))
            newlist.append(item)
        self.obj.Base = newlist

    def getStandardButtons(self):
        return int(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Apply | QtGui.QDialogButtonBox.Cancel)

    def resetObject(self, remove=None):
        "transfers the values from the widget to the object"

        self.obj.touch()
        FreeCAD.ActiveDocument.recompute()

    def setupUi(self):

        # Connect Signals and Slots
        # Base Controls
        self.form.baseList.itemSelectionChanged.connect(self.itemActivated)
        self.form.addBase.clicked.connect(self.addBase)
        self.form.deleteBase.clicked.connect(self.deleteBase)
        self.form.reorderBase.clicked.connect(self.reorderBase)

        # Depths
        self.form.startDepth.editingFinished.connect(self.getFields)
        self.form.finalDepth.editingFinished.connect(self.getFields)
        self.form.finishDepth.editingFinished.connect(self.getFields)
        self.form.stepDown.editingFinished.connect(self.getFields)

        # Heights
        self.form.safeHeight.editingFinished.connect(self.getFields)
        self.form.clearanceHeight.editingFinished.connect(self.getFields)

        # operation
        self.form.cutMode.currentIndexChanged.connect(self.getFields)
        self.form.extraOffset.editingFinished.connect(self.getFields)
        self.form.boundaryShape.currentIndexChanged.connect(self.getFields)
        self.form.stepOverPercent.editingFinished.connect(self.getFields)
        self.form.offsetpattern.currentIndexChanged.connect(self.getFields)
        self.form.zigZagAngle.editingFinished.connect(self.getFields)
        self.form.uiToolController.currentIndexChanged.connect(self.getFields)

        self.setFields()

        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) != 0 and sel[0].HasSubObjects:
                self.addBase()


class SelObserver:
    def __init__(self):
        import PathScripts.PathSelection as PST
        PST.pocketselect()

    def __del__(self):
        import PathScripts.PathSelection as PST
        PST.clear()

    def addSelection(self, doc, obj, sub, pnt):
        FreeCADGui.doCommand('Gui.Selection.addSelection(FreeCAD.ActiveDocument.' + obj + ')')
        FreeCADGui.updateGui()

if FreeCAD.GuiUp:
    # register the FreeCAD command
    FreeCADGui.addCommand('Path_MillFace', CommandPathMillFace())
    FreeCADGui.addCommand('Set_FaceStartPoint', _CommandSetFaceStartPoint())


FreeCAD.Console.PrintLog("Loading PathMillFace... done\n")
