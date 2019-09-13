import fnmatch
import os
import re
import sys

from PyQt5 import QtGui, Qt
from PyQt5.QtWidgets import QPushButton, QCheckBox, QWidget, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout, QLineEdit, \
    QRadioButton, QGridLayout, QComboBox, QFileDialog, QApplication, QTabWidget, QInputDialog, QDialog, QPlainTextEdit, \
    QScrollArea, QMessageBox
import json


class FlagButton(QPushButton):
    def __init__(self, text, value):
        super(FlagButton, self).__init__()
        self.setText(text)
        self.value = value


class FlagCheckBox(QCheckBox):
    def __init__(self, text, value):
        super(FlagCheckBox, self).__init__()
        self.setText(text)
        self.value = value


class Window(QWidget):

    def __init__(self):
        super().__init__()

        # window geometry data
        self.title = "Beyond Chaos Randomizer"
        self.left = 200
        self.top = 200
        self.width = 650
        self.height = 600

        # values to be sent to randomizer
        self.romText = ""
        self.mode = ""
        self.flags = ""
        self.flagString = ""

        # dictionaries to hold flag data
        self.aesthetic = {}
        self.experimental = {}
        self.gamebreaking = {}
        self.major = {}
        self.minor = {}
        self.simple = {}
        self.dictionaries = [self.simple, self.aesthetic, self.major,
                        self.minor, self.experimental, self.gamebreaking]
        self.savedPresets = {}

        # ui elements
        self.comboBox = QComboBox()

        # ----------- Begin buiding program/window ------------------------------

        # checking for saved data directory
        if not os.path.exists('saved_flagsets'):
            os.mkdir('saved_flagsets')

        # pull data from files
        self.initCodes()
        self.compilePresets()

        # create window using geometry data
        self.InitWindow()

    def InitWindow(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        # build the UI
        self.CreateLayout()

        # show program onscreen
        self.show()

    def CreateLayout(self):
        # Primary Vertical Box Layout
        vbox = QVBoxLayout()

        titleLabel = QLabel("Beyond Chaos Randomizer")
        font = QtGui.QFont("Arial", 20, QtGui.QFont.Black)
        titleLabel.setFont(font)
        titleLabel.setAlignment(Qt.Qt.AlignCenter)
        titleLabel.setMargin(25)
        vbox.addWidget(titleLabel)

        # Adding first/top groupbox to the layout
        vbox.addWidget(self.GroupBoxOneLayout())
        # Adding second/middle groupbox
        vbox.addWidget(self.GroupBoxTwoLayout())
        # Adding third/bottom groupbox
        vbox.addWidget(self.GroupBoxThreeLayout())
        # vbox.addStretch(1)

        self.setLayout(vbox)

    # Top groupbox consisting of ROM selection, and Seed number input
    def GroupBoxOneLayout(self):
        topGroupBox = QGroupBox()
        TopHBox = QHBoxLayout()

        romLabel = QLabel("ROM:")
        TopHBox.addWidget(romLabel)
        self.romInput = QLineEdit()
        self.romInput.setPlaceholderText("Required")
        TopHBox.addWidget(self.romInput)
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(lambda: self.openFileChooser())
        TopHBox.addWidget(browseButton)
        seedLabel = QLabel("Seed:")
        TopHBox.addWidget(seedLabel)
        self.seedInput = QLineEdit()
        self.seedInput.setPlaceholderText("Optional")
        TopHBox.addWidget(self.seedInput)

        topGroupBox.setLayout(TopHBox)

        return topGroupBox

    # Middle groupbox of sub-groupboxes. Consists of left section (game mode selection)
    #   and right section (flag selection -> tab-sorted)
    def GroupBoxTwoLayout(self):
        groupBoxTwo = QGroupBox()
        middleHBox = QHBoxLayout()

        # ------------ Part one (left) of middle section ---------------------
        middleLeftGroupBox = QGroupBox("Select mode")
        midLeftVBox = QVBoxLayout()

        radioButton = QRadioButton("Normal (Default)")
        radioButton.setToolTip("Play through the normal story")
        radioButton.setChecked(True)
        radioButton.mode = "normal"
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Ancient Cave")
        radioButton.setToolTip("Play though a long randomized dungeon")
        radioButton.mode = "ancientcave"
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Speed Cave")
        radioButton.setToolTip("Play through a medium-sized randomized dungeon")
        radioButton.mode = "speedcave"
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Race Cave")
        radioButton.setToolTip("Play through a short randomized dungeon")
        radioButton.mode = "racecave"
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Kefka@Narshe")
        radioButton.setToolTip("Play the normal story up to Kefka at Narshe, "
                               "with extra wackiness. Intended for racing.")
        radioButton.mode = "katn"
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Dragon Hunt")
        radioButton.setToolTip("Kill all 8 dragons in the World of Ruin. Intended for racing.")
        radioButton.mode = "dragonhunt"
        midLeftVBox.addWidget(radioButton)

        middleLeftGroupBox.setLayout(midLeftVBox)
        # ------------- Part one (left) end ----------------------------------------------

        # ------------- Part two (right) of middle section --------------------------
        middleRightGroupBox = QGroupBox("Flag Selection - Hover over for description")

        tabVBoxLayout = QVBoxLayout()

        tabs = QTabWidget()
        tab1 = QWidget()
        tab2 = QWidget()
        tab3 = QWidget()
        tab4 = QWidget()
        tab5 = QWidget()
        tab6 = QWidget()
        tabs.addTab(tab1, "Simple")
        tabs.addTab(tab2, "Aesthetic")
        tabs.addTab(tab3, "Major")
        tabs.addTab(tab4, "Minor")
        tabs.addTab(tab5, "Experimental")
        tabs.addTab(tab6, "Gamebreaking")

        # ----------- tab1 -------------------------
        flagGrid = QGridLayout()
        count = 0
        for flagname, flagdesc in self.simple.items():
            cbox = FlagCheckBox(flagname, flagname)
            # cbox.setStyleSheet("font:bold; font-size:14px")
            cbox.setCheckable(True)
            cbox.setToolTip(flagdesc['explanation'])
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.flagButtonClicked("simple", temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1
        tab1.setLayout(flagGrid)

        # ----------- tab2 -------------------------
        flagGrid = QGridLayout()
        count = 0
        for flagname, flagdesc in self.aesthetic.items():
            cbox = FlagCheckBox(flagname, flagname)
            # cbox.setStyleSheet("font:bold; font-size:14px")
            cbox.setCheckable(True)
            cbox.setToolTip(flagdesc['explanation'])
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.flagButtonClicked("aesthetic", temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1
        tab2.setLayout(flagGrid)

        # ----------- tab3 -------------------------
        flagGrid = QGridLayout()
        count = 0
        for flagname, flagdesc in self.major.items():
            cbox = FlagCheckBox(flagname, flagname)
            # cbox.setStyleSheet("font:bold; font-size:14px")
            cbox.setCheckable(True)
            cbox.setToolTip(flagdesc['explanation'])
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.flagButtonClicked("major", temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1
        tab3.setLayout(flagGrid)

        # ----------- tab4 -------------------------
        flagGrid = QGridLayout()
        count = 0
        for flagname, flagdesc in self.minor.items():
            cbox = FlagCheckBox(flagname, flagname)
            # cbox.setStyleSheet("font:bold; font-size:14px")
            cbox.setCheckable(True)
            cbox.setToolTip(flagdesc['explanation'])
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.flagButtonClicked("minor", temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1
        tab4.setLayout(flagGrid)

        # ----------- tab5 -------------------------
        flagGrid = QGridLayout()
        count = 0
        for flagname, flagdesc in self.experimental.items():
            cbox = FlagCheckBox(flagname, flagname)
            # cbox.setStyleSheet("font:bold; font-size:14px")
            cbox.setCheckable(True)
            cbox.setToolTip(flagdesc['explanation'])
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.flagButtonClicked("experimental", temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1
        tab5.setLayout(flagGrid)

        # ----------- tab6 -------------------------
        flagGrid = QGridLayout()
        count = 0
        for flagname, flagdesc in self.gamebreaking.items():
            cbox = FlagCheckBox(flagname, flagname)
            # cbox.setStyleSheet("font:bold; font-size:14px")
            cbox.setCheckable(True)
            cbox.setToolTip(flagdesc['explanation'])
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.flagButtonClicked("gamebreaking", temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1
        tab6.setLayout(flagGrid)

        # this is the line in the layout that displays the string of selected flags
        #   and the button to save those flags
        widgetV = QWidget()
        widgetVBoxLayout = QVBoxLayout()
        widgetV.setLayout(widgetVBoxLayout)

        widgetVBoxLayout.addWidget(QLabel("Text-string of selected flags:"))

        self.flagString = QLineEdit()
        self.flagString.setReadOnly(True)
        self.flagString.setStyleSheet("background:lightgrey;")
        widgetVBoxLayout.addWidget(self.flagString)

        saveButton = QPushButton("Save flags selection")
        saveButton.clicked.connect(lambda : self.saveSeed())
        widgetVBoxLayout.addWidget(saveButton)

        # This part makes a group box and adds the selected-flags display
        #   and a button to show help
        flagTextWidget = QGroupBox()
        flagTextHBox = QHBoxLayout()
        flagTextHBox.addWidget(widgetV)
        helpButton = QPushButton("Flag Help")
        helpButton.setStyleSheet("font-size:12px; height:60px")
        helpButton.clicked.connect(lambda: self.showFlagHelp())
        flagTextHBox.addWidget(helpButton)
        flagTextWidget.setLayout(flagTextHBox)

        tabVBoxLayout.addWidget(tabs)
        tabVBoxLayout.addWidget(flagTextWidget)

        middleRightGroupBox.setLayout(tabVBoxLayout)
        # ------------- Part two (right) end ---------------------------------------

        # add widgets to HBoxLayout and assign to middle groupbox layout
        middleHBox.addWidget(middleLeftGroupBox)
        middleHBox.addWidget(middleRightGroupBox)
        groupBoxTwo.setLayout(middleHBox)

        return groupBoxTwo

    # Bottom groupbox consisting of saved seeds selection box, and button to generate seed
    def GroupBoxThreeLayout(self):
        bottomGroupBox = QGroupBox()
        bottomHBox = QHBoxLayout()

        bottomHBox.addWidget(QLabel("Saved flag selection: "))

        self.comboBox.addItem("Select a preset")
        for string in self.savedPresets:
            self.comboBox.addItem(string)
        self.comboBox.currentTextChanged.connect(lambda: self.updatePresetDropdown())
        bottomHBox.addWidget(self.comboBox)



        deleteButton = QPushButton("Delete selection")
        deleteButton.clicked.connect(lambda: self.deleteSeed())
        bottomHBox.addWidget(deleteButton)

        bottomHBox.addStretch(1)

        generateButton = QPushButton("Generate Seed")
        generateButton.setStyleSheet("font:bold; font-size:18px; height:48px; width:150px")
        bottomHBox.addWidget(generateButton)

        bottomGroupBox.setLayout(bottomHBox)
        return bottomGroupBox

    # --------------------------------------------------------------------------------
    # -------------- NO MORE LAYOUT DESIGN PAST THIS POINT ---------------------------
    # --------------------------------------------------------------------------------

    # opens input dialog to get a name to assign a desired seed flagset, then saves all dictionaries
    #   to a text file under that flagset name.
    def saveSeed(self):

        text, okPressed = QInputDialog.getText(self, "Save Seed", "Enter a name for this flagset", QLineEdit.Normal, "")
        if okPressed and text != '':
            print(f"{text}.txt saved!")

            f = open(f"saved_flagsets/flagset_{text}.txt", "w")
            for l in self.dictionaries:
                # print(l)
                f.write(str(l) + "\n")
            f.close()
            self.savedPresets[text] = f"{text}.txt"
            self.comboBox.addItem(text)

    def deleteSeed(self):
        seed = self.comboBox.currentText()

        if not seed == "Select a preset":
            response = QMessageBox.question(self, 'Delete confimation', f"Do you want to delete \'{seed}\'?",
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if response == QMessageBox.Yes:
                print("You selected yes!")
                if os.path.exists(f"saved_flagsets/flagset_{seed}.txt"):
                    os.remove(f"saved_flagsets/flagset_{seed}.txt")
                    del self.savedPresets[seed]
                    self.comboBox.removeItem(self.comboBox.findText(seed))
                    print(f"{seed} deleted!")
            else:
                print("You selected no!")

    def updatePresetDropdown(self):
        selectedPreset = self.comboBox.currentText()
        print(selectedPreset + " selected")
        self.loadPreset(selectedPreset)

    # (MAKE THIS CLEANER IN THE FUTURE)
    # When flag is selected/unselected, updates flag value in appropriate dictionary
    #   Also updates textbox with updated string of flags
    def flagButtonClicked(self, dictionary, value):
        # This part updates the appropriate dictionary (CLEAN THIS)
        if dictionary == "simple":
            if not self.simple[value]['checked']:
                self.simple[value]['checked'] = True
            else:
                self.simple[value]['checked'] = False
        elif dictionary == "aesthetic":
            if not self.aesthetic[value]['checked']:
                self.aesthetic[value]['checked'] = True
            else:
                self.aesthetic[value]['checked'] = False
        elif dictionary == "major":
            if not self.major[value]['checked']:
                self.major[value]['checked'] = True
            else:
                self.major[value]['checked'] = False
        elif dictionary == "minor":
            if not self.minor[value]['checked']:
                self.minor[value]['checked'] = True
            else:
                self.minor[value]['checked'] = False
        elif dictionary == "experimental":
            if not self.experimental[value]['checked']:
                self.experimental[value]['checked'] = True
            else:
                self.experimental[value]['checked'] = False
        elif dictionary == "gamebreaking":
            if not self.gamebreaking[value]['checked']:
                self.gamebreaking[value]['checked'] = True
            else:
                self.gamebreaking[value]['checked'] = False

        # This part updates the textbox with the string of flag values
        # dictionaries = [self.simple, self.aesthetic, self.major,
        #                 self.minor, self.experimental, self.gamebreaking]
        s = ""
        for d in self.dictionaries:
            space = False
            for name, info in d.items():
                if info['checked']:
                    s = s + name
                    space = True
            if space:
                s = s + " "

        print(s)  # print to console for testing
        self.flagString.setText(s)

    # Opens file dialog to select rom file and assigns it to value in parent class
    def openFileChooser(self):
        file_path = QFileDialog.getOpenFileName(self, 'Open File', './', filter="All Files(*.*);;Text Files(*.txt)")
        if file_path[0]:
            print(str(file_path[0]))

        # display file location in text input field
        self.romInput.setText(str(file_path[0]))

    # (MAKE THIS CLEANER IN THE FUTURE)
    # (At startup) Opens text files containing code flags/descriptions and
    #   puts data into separate dictionaries
    def initCodes(self):
        codeLists = ["Codes-Aesthetic.txt", "Codes-Experimental.txt", "Codes-Gamebreaking.txt",
                     "Codes-Major.txt", "Codes-Minor.txt", "Codes-Simple.txt"]

        for fileList in codeLists:
            with open("gui-codes/" + fileList, 'r') as fl:
                content = fl.readlines()

                if fileList == "Codes-Aesthetic.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.aesthetic[temp[0]] = {'explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Experimental.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        # print(temp)
                        self.experimental[temp[0]] = {'explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Gamebreaking.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.gamebreaking[temp[0]] = {'explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Major.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.major[temp[0]] = {'explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Minor.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.minor[temp[0]] = {'explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Simple.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.simple[temp[0]] = {'explanation': temp[1], 'checked': False}

        # print(self.aesthetic)
        # print(self.experimental)
        # print(self.gamebreaking)
        # print(self.major)
        # print(self.minor)
        # print(self.simple)

    # Open second window and display list of flags and their descriptions
    # (CLEAN THIS UP)
    def showFlagHelp(self):
        dia = QDialog()
        dia.setWindowTitle("Flag Descriptions")
        dia.setGeometry(300, 300, 600, 550)

        tab = QTabWidget()

        tab1 = QScrollArea()
        tab1wid = QWidget()
        tab.addTab(tab1, "Simple")
        tab1layout = QVBoxLayout()
        for flagname, flagdesc in self.simple.items():
            tab1layout.addWidget(QLabel(f"{flagname}  -  {flagdesc['explanation']}"))
        tab1layout.addStretch(1)
        tab1wid.setLayout(tab1layout)
        tab1.setWidgetResizable(True)
        tab1.setWidget(tab1wid)

        tab2 = QScrollArea()
        tab2wid = QWidget()
        tab.addTab(tab2, "Aesthetic")
        tab2layout = QVBoxLayout()
        for flagname, flagdesc in self.aesthetic.items():
            tab2layout.addWidget(QLabel(f"{flagname}  -  {flagdesc['explanation']}"))
        tab2layout.addStretch(1)
        tab2wid.setLayout(tab2layout)
        tab2.setWidgetResizable(True)
        tab2.setWidget(tab2wid)

        tab3 = QScrollArea()
        tab3wid = QWidget()
        tab.addTab(tab3, "Major")
        tab3layout = QVBoxLayout()
        for flagname, flagdesc in self.major.items():
            tab3layout.addWidget(QLabel(f"{flagname}  -  {flagdesc['explanation']}"))
        tab3layout.addStretch(1)
        tab3wid.setLayout(tab3layout)
        tab3.setWidgetResizable(True)
        tab3.setWidget(tab3wid)

        tab4 = QScrollArea()
        tab4wid = QWidget()
        tab.addTab(tab4, "Minor")
        tab4layout = QVBoxLayout()
        for flagname, flagdesc in self.minor.items():
            tab4layout.addWidget(QLabel(f"{flagname}  -  {flagdesc['explanation']}"))
        tab4layout.addStretch(1)
        tab4wid.setLayout(tab4layout)
        tab4.setWidgetResizable(True)
        tab4.setWidget(tab4wid)

        tab5 = QScrollArea()
        tab5wid = QWidget()
        tab.addTab(tab5, "Experimental")
        tab5layout = QVBoxLayout()
        for flagname, flagdesc in self.experimental.items():
            tab5layout.addWidget(QLabel(f"{flagname}  -  {flagdesc['explanation']}"))
        tab5layout.addStretch(1)
        tab5wid.setLayout(tab5layout)
        tab5.setWidgetResizable(True)
        tab5.setWidget(tab5wid)

        tab6 = QScrollArea()
        tab6wid = QWidget()
        tab.addTab(tab6, "Gamebreaking")
        tab6layout = QVBoxLayout()
        for flagname, flagdesc in self.gamebreaking.items():
            tab6layout.addWidget(QLabel(f"{flagname}  -  {flagdesc['explanation']}"))
        tab6layout.addStretch(1)
        tab6wid.setLayout(tab6layout)
        tab6.setWidgetResizable(True)
        tab6.setWidget(tab6wid)

        tablayout = QVBoxLayout()
        tablayout.addWidget(tab)
        dia.setLayout(tablayout)
        dia.exec()

    # reads files from save directory and puts them in a list
    def compilePresets(self):
        for file in os.listdir('./saved_flagsets'):
            if re.match(r'flagset_(.*).txt$', file):
                print(file)
                temp = list(re.split('[_.]', file))
                self.savedPresets[temp[1]] = file
                print(self.savedPresets)

    # Reads dictionary data from text file and populates class dictionaries
    def loadPreset(self, flagdict):
        s = open(f'saved_flagsets/flagset_{flagdict}.txt', 'r')

        for d in self.dictionaries:
            d = eval(s.readline())
            print(d)
        s.close()





if __name__ == "__main__":
    App = QApplication(sys.argv)
    window = Window()
    sys.exit(App.exec())
