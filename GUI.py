import re
import sys

from PyQt5 import QtGui, Qt
from PyQt5.QtWidgets import QPushButton, QCheckBox, QWidget, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout, QLineEdit, \
    QRadioButton, QGridLayout, QComboBox, QFileDialog, QApplication, QTabWidget


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

        # window geometry info
        self.title = "Beyond Chaos Randomizer"
        self.left = 200
        self.top = 200
        self.width = 650
        self.height = 600

        # values to be sent to randomizer
        self.romText = ""
        self.mode = ""
        self.flags = ""

        # dictionaries to hold flag data
        self.aesthetic = {}
        self.experimental = {}
        self.gamebreaking = {}
        self.major = {}
        self.minor = {}
        self.simple = {}

        # create window using geometry data
        self.InitWindow()

    def InitWindow(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

        self.loadCodes()
        self.CreateLayout()

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

    # Top groupbox consisting of ROM selection, and Sedd number input
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
            cbox.setToolTip(flagdesc['Explanation'])
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
            cbox.setToolTip(flagdesc['Explanation'])
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
            cbox.setToolTip(flagdesc['Explanation'])
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
            cbox.setToolTip(flagdesc['Explanation'])
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
            cbox.setToolTip(flagdesc['Explanation'])
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
            cbox.setToolTip(flagdesc['Explanation'])
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.flagButtonClicked("gamebreaking", temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1

        tab6.setLayout(flagGrid)

        # this is the line in the layout that displays the string of selected flags
        #   and the button to save those flags
        widget = QWidget()
        widgetHBoxLayout = QHBoxLayout()
        widgetHBoxLayout.addWidget(QLabel("Text-string of selected flags:"))
        flagString = QLineEdit()
        flagString.setReadOnly(True)
        flagString.setStyleSheet("background:lightgrey;")
        flagString.setText("string of selected flags here...")
        widgetHBoxLayout.addWidget(flagString)
        saveButton = QPushButton("Save flags selection")
        widgetHBoxLayout.addWidget(saveButton)

        widget.setLayout(widgetHBoxLayout)
        tabVBoxLayout.addWidget(tabs)
        tabVBoxLayout.addWidget(widget)

        middleRightGroupBox.setLayout(tabVBoxLayout)
        # ------------- Part two (right) end ---------------------------------------

        # add widgets to HBoxLayout and assign to middle groupbox layout
        middleHBox.addWidget(middleLeftGroupBox)
        middleHBox.addWidget(middleRightGroupBox)
        groupBoxTwo.setLayout(middleHBox)

        return groupBoxTwo

    def GroupBoxThreeLayout(self):
        bottomGroupBox = QGroupBox()
        bottomHBox = QHBoxLayout()

        bottomHBox.addWidget(QLabel("Saved flag selection: "))

        combolist = ["Select flag preset (optional)",
                "Dark Slash's formula",
                "Muppets's Garbage Brew",
                "Cecil's Murder Seed",
                "CecilBot Special"]
        comboBox = QComboBox()
        for string in combolist:
            comboBox.addItem(string)
        bottomHBox.addWidget(comboBox)

        deleteButton = QPushButton("Delete selection")
        bottomHBox.addWidget(deleteButton)

        bottomHBox.addStretch(1)

        generateButton = QPushButton("Generate Seed")
        generateButton.setStyleSheet("font:bold; font-size:18px; height:48px; width:150px")
        bottomHBox.addWidget(generateButton)

        bottomGroupBox.setLayout(bottomHBox)
        return bottomGroupBox

    # Function to test button click / lambda expression functionality
    def flagButtonClicked(self, dictionary, value):

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

    # Opens file dialog to select rom file and assigns it to value in parent class
    def openFileChooser(self):
        file_path = QFileDialog.getOpenFileName(self, 'Open File', './', filter="All Files(*.*);;Text Files(*.txt)")
        if file_path[0]:
            print(str(file_path[0]))

        # display file location in text input field
        self.romInput.setText(str(file_path[0]))

    # opens text files containing code flags/descriptions and puts data into separate dictionaries
    def loadCodes(self):
        codeLists = ["Codes-Aesthetic.txt", "Codes-Experimental.txt", "Codes-Gamebreaking.txt",
                     "Codes-Major.txt", "Codes-Minor.txt", "Codes-Simple.txt"]

        for fileList in codeLists:
            with open("gui-codes/" + fileList, 'r') as fl:
                content = fl.readlines()

                if fileList == "Codes-Aesthetic.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.aesthetic[temp[0]] = {'Explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Experimental.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        # print(temp)
                        self.experimental[temp[0]] = {'Explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Gamebreaking.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.gamebreaking[temp[0]] = {'Explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Major.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.major[temp[0]] = {'Explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Minor.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.minor[temp[0]] = {'Explanation': temp[1], 'checked': False}

                elif fileList == "Codes-Simple.txt":
                    for l in content:
                        temp = re.split('\t|\n', l)
                        temp = list(filter(None, temp))
                        self.simple[temp[0]] = {'Explanation': temp[1], 'checked': False}

        # print(self.aesthetic)
        # print(self.experimental)
        # print(self.gamebreaking)
        # print(self.major)
        # print(self.minor)
        # print(self.simple)


if __name__ == "__main__":
    App = QApplication(sys.argv)
    window = Window()
    sys.exit(App.exec())
