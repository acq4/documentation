# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'FlowchartTemplate.ui'
#
# Created: Thu Jan 27 11:25:39 2011
#      by: PyQt4 UI code generator 4.7.2
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")
        Form.resize(529, 329)
        self.selInfoWidget = QtGui.QWidget(Form)
        self.selInfoWidget.setGeometry(QtCore.QRect(260, 10, 264, 222))
        self.selInfoWidget.setObjectName("selInfoWidget")
        self.gridLayout = QtGui.QGridLayout(self.selInfoWidget)
        self.gridLayout.setObjectName("gridLayout")
        self.selDescLabel = QtGui.QLabel(self.selInfoWidget)
        self.selDescLabel.setText("")
        self.selDescLabel.setAlignment(QtCore.Qt.AlignLeading|QtCore.Qt.AlignLeft|QtCore.Qt.AlignTop)
        self.selDescLabel.setWordWrap(True)
        self.selDescLabel.setObjectName("selDescLabel")
        self.gridLayout.addWidget(self.selDescLabel, 0, 0, 1, 1)
        self.selNameLabel = QtGui.QLabel(self.selInfoWidget)
        font = QtGui.QFont()
        font.setWeight(75)
        font.setBold(True)
        self.selNameLabel.setFont(font)
        self.selNameLabel.setText("")
        self.selNameLabel.setObjectName("selNameLabel")
        self.gridLayout.addWidget(self.selNameLabel, 0, 1, 1, 1)
        self.selectedTree = DataTreeWidget(self.selInfoWidget)
        self.selectedTree.setObjectName("selectedTree")
        self.selectedTree.headerItem().setText(0, "1")
        self.gridLayout.addWidget(self.selectedTree, 1, 0, 1, 2)
        self.hoverText = QtGui.QTextEdit(Form)
        self.hoverText.setGeometry(QtCore.QRect(0, 240, 521, 81))
        self.hoverText.setObjectName("hoverText")
        self.view = FlowchartGraphicsView(Form)
        self.view.setGeometry(QtCore.QRect(0, 0, 256, 192))
        self.view.setObjectName("view")

        self.retranslateUi(Form)
        QtCore.QMetaObject.connectSlotsByName(Form)

    def retranslateUi(self, Form):
        Form.setWindowTitle(QtGui.QApplication.translate("Form", "Form", None, QtGui.QApplication.UnicodeUTF8))

from DataTreeWidget import DataTreeWidget
from FlowchartGraphicsView import FlowchartGraphicsView