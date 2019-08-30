import sys

from PyQt5 import QtGui, Qt
from PyQt5.QtWidgets import *


class FlagButton(QPushButton):
    def __init__(self, text, value):
        super(FlagButton,self).__init__()
        self.setText(text)
        self.value = value

class FlagCheckBox(QCheckBox):
    def __init__(self, text, value):
        super(FlagCheckBox,self).__init__()
        self.setText(text)
        self.value = value



class Window(QWidget):

    def __init__(self):
        super().__init__()

        self.title = "Beyond Chaos Randomizer"
        self.left = 200
        self.top = 200
        self.width = 650
        self.height = 600

        self.InitWindow()

    def InitWindow(self):
        self.setWindowTitle(self.title)
        self.setGeometry(self.left, self.top, self.width, self.height)

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
        romInput = QLineEdit()
        romInput.setPlaceholderText("Required")
        TopHBox.addWidget(romInput)
        browseButton = QPushButton("Browse")
        TopHBox.addWidget(browseButton)
        seedLabel = QLabel("Seed:")
        TopHBox.addWidget(seedLabel)
        seedInput = QLineEdit()
        seedInput.setPlaceholderText("Optional")
        TopHBox.addWidget(seedInput)

        topGroupBox.setLayout(TopHBox)

        return topGroupBox

    # Middle groupbox of sub-groupboxes. Consists of left section (game mode selection)
    #   and right section (flag selection -> tab-sorted)
    # Flag selection is loop-driven generation with data read from text files. The option
    #   to save flag selections is available
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

        flagGrid = QGridLayout()

        count = 0
        # for x in range(23):
        #     button = FlagButton("Flag name here " + str(x), "Hi" + str(x))
        #     button.setCheckable(True)
        #     button.setToolTip(button.value)
        #     button.clicked.connect(lambda checked, temp=button.value: self.buttonClicked(temp))
        #     flagGrid.addWidget(button, count / 3, count % 3)
        #     count += 1

        for x in range(23):
            cbox = FlagCheckBox("Flag name here " + str(x), "Hi" + str(x))
            #cbox.setStyleSheet("font:bold; font-size:14px")
            cbox.setCheckable(True)
            cbox.setToolTip(cbox.value)
            cbox.clicked.connect(lambda checked, temp=cbox.value: self.buttonClicked(temp))
            flagGrid.addWidget(cbox, count / 3, count % 3)
            count += 1

        tab1.setLayout(flagGrid)

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
        bottomGroupBox = QGroupBox("Generation Options")
        bottomHBox = QHBoxLayout()

        bottomHBox.addWidget(QLabel("Saved flag selection: "))

        list = ["Select flag preset (optional)",
                "Dark Slash's formula",
                "Muppets's Garbage Brew",
                "Cecil's Murder Seed",
                "CecilBot Special"]
        comboBox = QComboBox()
        for string in list:
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
    def buttonClicked(self, value):
        print(str(value))


if __name__ == "__main__":
    App = QApplication(sys.argv)
    window = Window()
    sys.exit(App.exec())
