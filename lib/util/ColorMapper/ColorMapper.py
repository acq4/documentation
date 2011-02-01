# -*- coding: utf-8 -*-
if __name__ == '__main__':
    import sys
    sys.path.append('..')
    
from PyQt4 import QtCore, QtGui
from SpinBox import SpinBox
from pyqtgraph.GradientWidget import GradientWidget
import numpy as np
import CMTemplate
import os
import configfile

class ColorMapper(QtGui.QWidget):
    def __init__(self, parent=None, filePath=None):
        QtGui.QWidget.__init__(self, parent)
        #self.layout = QtGui.QGridLayout()
        #self.addBtn = QtGui.QPushButton('+')
        #self.remBtn = QtGui.QPushButton('-')
        #self.tree = QtGui.QTreeWidget()
        #self.setLayout(self.layout)
        #self.layout.addWidget(self.tree, 0, 0, 1, 2)
        #self.layout.addWidget(self.addBtn, 1, 0)
        #self.layout.addWidget(self.remBtn, 1, 1)
        #self.layout.setSpacing(0)
        
        #self.tree.setColumnCount(5)
        #self.tree.setHeaderLabels(['  ', 'arg', 'op', 'min', 'max', 'colors'])
        
        self.ui = CMTemplate.Ui_Form()
        self.ui.setupUi(self)
        
        self.ui.tree.setColumnWidth(0, 15)
        self.ui.tree.setColumnWidth(2, 35)
        self.ui.tree.setColumnWidth(3, 80)
        self.ui.tree.setColumnWidth(4, 80)
        
        self.argList = []
        self.items = []
        self.loadedFile = None
        self.filePath = filePath
        
        self.refreshFileList()
        
        self.connect(self.ui.addBtn, QtCore.SIGNAL('clicked()'), self.addClicked)
        self.connect(self.ui.remBtn, QtCore.SIGNAL('clicked()'), self.remClicked)
        self.ui.fileCombo.currentIndexChanged[int].connect(self.load)
        self.ui.fileCombo.lineEdit().editingFinished.connect(self.save)
        self.ui.delBtn.clicked.connect(self.delete)
        
    def refreshFileList(self):
        combo = self.ui.fileCombo
        if self.filePath is None:
            return
        files = ["Load..."] + os.listdir(self.filePath)
        combo.blockSignals(True)
        combo.clear()
        ind = 0
        #print files
        #print self.loadedFile
        for i in range(len(files)):
            f = files[i]
            combo.addItem(f)
            if f == self.loadedFile:
                ind = i
        combo.setCurrentIndex(ind)
        combo.blockSignals(False)
        
    def load(self, ind):
        #print "Index changed to:", ind
        if ind == 0:
            return
        name = str(self.ui.fileCombo.currentText())
        file = os.path.join(self.filePath, name)
        if not os.path.isfile(file):
            return
        state = configfile.readConfigFile(file)
        self.restoreState(state)
        self.loadedFile = name

    def save(self):
        name = str(self.ui.fileCombo.currentText())
        if name == 'Load...':
            return
        file = os.path.join(self.filePath, name)
        #print "save:", file
        state = self.saveState()
        configfile.writeConfigFile(state, file)
        self.loadedFile = str(name)
        self.refreshFileList()

    def delete(self):
        if self.ui.fileCombo.currentIndex() == 0:
            return
        file = os.path.join(self.filePath, self.loadedFile)
        #print "delete", file
        os.remove(file)
        self.loadedFile = None
        self.refreshFileList()

    def widgetGroupInterface(self):
        return (None, ColorMapper.saveState, ColorMapper.restoreState)
        
    def emitChanged(self):
        self.emit(QtCore.SIGNAL('changed'))
    
    def setArgList(self, args):
        """Sets the list of variable names available for computing colors"""
        self.argList = args
        for i in self.items:
            i.updateArgList()
        
    def getColor(self, args):
        color = np.array([0.,0.,0.,1.])
        for item in self.items:
            c = item.getColor(args)
            c = np.array([c.red(), c.green(), c.blue(), c.alpha()], dtype=float) / 255.
            op = item.getOp()
            if op == '+':
                color += c
            elif op == '*':
                color *= c
            color = np.clip(color, 0, 1.)
            #print color, c
        color = np.clip(color*255, 0, 255).astype(int)
        return QtGui.QColor(*color)

    def addClicked(self):
        self.addItem()
        self.emitChanged()
        
    def addItem(self, state=None):
        item = ColorMapperItem(self)
        self.ui.tree.addTopLevelItem(item)
        item.postAdd()
        self.items.append(item)
        if state is not None:
            item.restoreState(state)
        
        
    def remClicked(self):
        item = self.ui.tree.currentItem()
        if item is None:
            return
        self.remItem(item)
        self.emitChanged()

    def remItem(self, item):
        index = self.ui.tree.indexOfTopLevelItem(item)
        self.ui.tree.takeTopLevelItem(index)
        self.items.remove(item)

    def saveState(self):
        items = [self.ui.tree.topLevelItem(i) for i in range(self.ui.tree.topLevelItemCount())]
        state = {'args': self.argList, 'items': [i.saveState() for i in items]}
        return state
        
    def restoreState(self, state):
        for i in self.items[:]:
            self.remItem(i)
        self.setArgList(state['args'])
        for i in state['items']:
            self.addItem(i)


class ColorMapperItem(QtGui.QTreeWidgetItem):
    def __init__(self, cm):
        self.cm = cm
        QtGui.QTreeWidgetItem.__init__(self)
        self.argCombo = QtGui.QComboBox()
        self.opCombo = QtGui.QComboBox()
        self.minSpin = SpinBox(value=0.0)
        self.maxSpin = SpinBox(value=1.0)
        self.gradient = GradientWidget()
        self.updateArgList()
        self.opCombo.addItem('+')
        self.opCombo.addItem('*')

    def postAdd(self):
        t = self.treeWidget()
        self.setText(0, "-")
        t.setItemWidget(self, 1, self.argCombo)
        t.setItemWidget(self, 2, self.opCombo)
        t.setItemWidget(self, 3, self.minSpin)
        t.setItemWidget(self, 4, self.maxSpin)
        t.setItemWidget(self, 5, self.gradient)

    def updateArgList(self):
        prev = str(self.argCombo.currentText())
        self.argCombo.clear()
        for a in self.cm.argList:
            self.argCombo.addItem(a)
            if a == prev:
                self.argCombo.setCurrentIndex(self.argCombo.count()-1)

    def getColor(self, args):
        arg = str(self.argCombo.currentText())
        val = args[arg]
        mn = self.minSpin.value()
        mx = self.maxSpin.value()
        norm = np.clip((val - mn) / (mx - mn), 0.0, 1.0)
        return self.gradient.getColor(norm)

    def getOp(self):
        return self.opCombo.currentText()

    def saveState(self):
        state = {
            'arg': str(self.argCombo.currentText()),
            'op': str(self.opCombo.currentText()),
            'min': self.minSpin.value(),
            'max': self.maxSpin.value(),
            'gradient': self.gradient.saveState()
        }
        return state
        
    def restoreState(self, state):
        ind = self.argCombo.findText(state['arg'])
        self.argCombo.setCurrentIndex(ind)
        ind = self.opCombo.findText(state['op'])
        self.opCombo.setCurrentIndex(ind)
        
        self.minSpin.setValue(state['min'])
        self.maxSpin.setValue(state['max'])

        self.gradient.restoreState(state['gradient'])

if __name__ == '__main__':
    app = QtGui.QApplication([])
    win = QtGui.QMainWindow()
    w = ColorMapper(filePath='./test')
    win.setCentralWidget(w)
    win.show()
    win.resize(400,400)
    
    w.setArgList(['x', 'y', 'amp', 'tau'])
    #app.exec_()