import fnmatch, os, re, sys, ast, pickle
from subprocess import call
from PyQt5 import QtGui, Qt
from PyQt5.QtWidgets import QPushButton, QCheckBox, QWidget, QVBoxLayout, QLabel, QGroupBox, QHBoxLayout, QLineEdit, \
    QRadioButton, QGridLayout, QComboBox, QFileDialog, QApplication, QTabWidget, QInputDialog, QDialog, QPlainTextEdit, \
    QScrollArea, QMessageBox, QErrorMessage

print("Loading Complete! Any errors shown here should be reported to Green Knight")

if sys.version_info[0] < 3:
    raise Exception("Python 3 or a more recent version is required. Report this to Green Knight")

# Extended QButton widget to hold flag value - NOT USED PRESENTLY
class FlagButton(QPushButton):
    def __init__(self, text, value):
        super(FlagButton, self).__init__()
        self.setText(text)
        self.value = value

# Extended QCheckBox widget to hold flag value - CURRENTLY USED
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
        self.width = 700
        self.height = 600

        # values to be sent to randomizer
        self.romText = ""
        self.version = ""
        self.mode = "normal"
        self.seed = ""
        self.flags = ""


        # dictionaries to hold flag data
        self.aesthetic = {}
        self.experimental = {}
        self.gamebreaking = {}
        self.major = {}
        self.minor = {}
        self.simple = {}
        self.dictionaries = [self.simple, self.aesthetic, self.major,
                        self.minor, self.experimental, self.gamebreaking]

        # dictionary? of saved presets
        self.savedPresets = {}

        # ui elements
        self.flagString = QLineEdit()
        self.comboBox = QComboBox()
        self.tab1 = QWidget()
        self.tab2 = QWidget()
        self.tab3 = QWidget()
        self.tab4 = QWidget()
        self.tab5 = QWidget()
        self.tab6 = QWidget()
        self.middleLeftGroupBox = QGroupBox()
        self.tablist = [self.tab1, self.tab2, self.tab3, self.tab4, self.tab5, self.tab6]

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
        self.romInput.setPlaceholderText("Required - Will save to presets")
        TopHBox.addWidget(self.romInput)
        browseButton = QPushButton("Browse")
        browseButton.clicked.connect(lambda: self.openFileChooser())
        TopHBox.addWidget(browseButton)
        seedLabel = QLabel("Seed:")
        TopHBox.addWidget(seedLabel)
        self.seedInput = QLineEdit()
        self.seedInput.setPlaceholderText("Optional - WILL NOT SAVE TO PRESETS!")
        TopHBox.addWidget(self.seedInput)

        topGroupBox.setLayout(TopHBox)

        return topGroupBox

    # Middle groupbox of sub-groupboxes. Consists of left section (game mode selection)
    #   and right section (flag selection -> tab-sorted)
    def GroupBoxTwoLayout(self):
        groupBoxTwo = QGroupBox()
        middleHBox = QHBoxLayout()

        # ------------ Part one (left) of middle section - Mode radio buttons -------

        self.middleLeftGroupBox.setTitle("Select Mode")
        midLeftVBox = QVBoxLayout()

        radioButton = QRadioButton("Normal (Default)")
        radioButton.setToolTip("Play through the normal story")
        radioButton.setChecked(True)
        radioButton.mode = "normal"
        radioButton.clicked.connect(lambda : self.updateRadioSelection("normal"))
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Ancient Cave")
        radioButton.setToolTip("Play though a long randomized dungeon")
        radioButton.mode = "ancientcave"
        radioButton.clicked.connect(lambda: self.updateRadioSelection("ancientcave"))
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Speed Cave")
        radioButton.setToolTip("Play through a medium-sized randomized dungeon")
        radioButton.mode = "speedcave"
        radioButton.clicked.connect(lambda: self.updateRadioSelection("speedcave"))
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Race Cave")
        radioButton.setToolTip("Play through a short randomized dungeon")
        radioButton.mode = "racecave"
        radioButton.clicked.connect(lambda: self.updateRadioSelection("racecave"))
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Kefka@Narshe")
        radioButton.setToolTip("Play the normal story up to Kefka at Narshe, "
                               "with extra wackiness. Intended for racing.")
        radioButton.mode = "katn"
        radioButton.clicked.connect(lambda: self.updateRadioSelection("katn"))
        midLeftVBox.addWidget(radioButton)

        radioButton = QRadioButton("Dragon Hunt")
        radioButton.setToolTip("Kill all 8 dragons in the World of Ruin. Intended for racing.")
        radioButton.mode = "dragonhunt"
        radioButton.clicked.connect(lambda: self.updateRadioSelection("dragonhunt"))
        midLeftVBox.addWidget(radioButton)

        self.middleLeftGroupBox.setLayout(midLeftVBox)
        # ------------- Part one (left) end ----------------------------------------------

        # ------------- Part two (right) of middle section - Flag tabs -----------------
        middleRightGroupBox = QGroupBox("Flag Selection")
        tabVBoxLayout = QVBoxLayout()
        tabs = QTabWidget()
        tabNames = ["Simple", "Aesthetic", "Major", "Minor", "Experimental", "Gamebreaking"]

        ############## Only checkboxes, no inline description ###############

        # # loop to add tab objects to 'tabs' TabWidget
        #
        # for tabObj, name in zip(self.tablist, tabNames):
        #     tabs.addTab(tabObj, name)
        #
        # for t, d in zip(self.tablist, self.dictionaries):
        #     flagGrid = QGridLayout()
        #     count = 0
        #     for flagname, flagdesc in d.items():
        #         cbox = FlagCheckBox(flagname, flagname)
        #         cbox.setCheckable(True)
        #         if flagdesc['checked']:
        #             cbox.isChecked = True
        #         cbox.setToolTip(flagdesc['explanation'])
        #         cbox.clicked.connect(lambda checked : self.flagButtonClicked())
        #         flagGrid.addWidget(cbox, count / 3, count % 3)
        #         count += 1
        #     t.setLayout(flagGrid)


        ############## Checkboxes and inline descriptions #####################

        # loop to add tab objects to 'tabs' TabWidget

        for t, d, names in zip(self.tablist, self.dictionaries, tabNames):
            tabObj = QScrollArea()
            tabs.addTab(tabObj, names)
            tablayout = QVBoxLayout()
            for flagname, flagdesc in d.items():
                cbox = FlagCheckBox(f"{flagname}  -  {flagdesc['explanation']}", flagname)
                tablayout.addWidget(cbox)
                #cbox.setCheckable(True)
                #cbox.setToolTip(flagdesc['explanation'])
                cbox.clicked.connect(lambda checked : self.flagButtonClicked())
            t.setLayout(tablayout)
            #tablayout.addStretch(1)
            tabObj.setWidgetResizable(True)
            tabObj.setWidget(t)


        tabVBoxLayout.addWidget(tabs)

        #----------- tabs done ----------------------------
        
        # this is the line in the layout that displays the string of selected flags
        #   and the button to save those flags
        widgetV = QWidget()
        widgetVBoxLayout = QVBoxLayout()
        widgetV.setLayout(widgetVBoxLayout)

        widgetVBoxLayout.addWidget(QLabel("Text-string of selected flags:"))

        self.flagString.setReadOnly(True)
        self.flagString.setStyleSheet("background:lightgrey;")
        widgetVBoxLayout.addWidget(self.flagString)

        saveButton = QPushButton("Save flags selection")
        saveButton.clicked.connect(lambda : self.saveSeed())
        widgetVBoxLayout.addWidget(saveButton)

        # This part makes a group box and adds the selected-flags display
        #   and a button to clear the UI
        flagTextWidget = QGroupBox()
        flagTextHBox = QHBoxLayout()
        flagTextHBox.addWidget(widgetV)
        clearUiButton = QPushButton("Reset")
        clearUiButton.setStyleSheet("font-size:12px; height:60px")
        clearUiButton.clicked.connect(lambda: self.clearUI())
        flagTextHBox.addWidget(clearUiButton)
        flagTextWidget.setLayout(flagTextHBox)

        tabVBoxLayout.addWidget(flagTextWidget)
        middleRightGroupBox.setLayout(tabVBoxLayout)
        # ------------- Part two (right) end ---------------------------------------



        # add widgets to HBoxLayout and assign to middle groupbox layout
        middleHBox.addWidget(self.middleLeftGroupBox)
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
        generateButton.clicked.connect(lambda: self.generateSeed())
        bottomHBox.addWidget(generateButton)

        bottomGroupBox.setLayout(bottomHBox)
        return bottomGroupBox

    # --------------------------------------------------------------------------------
    # -------------- NO MORE LAYOUT DESIGN PAST THIS POINT ---------------------------
    # --------------------------------------------------------------------------------


    # opens input dialog to get a name to assign a desired seed flagset, then saves all dictionaries,
    #   selected mode, and rom file path to a text file under that flagset name. Checks that file
    #   doesn't already exist.
    # files saved in .pickle format. overwrite not implemented currently. future updates will allow this.
    def saveSeed(self):
        self.romText = self.romInput.text()

        text, okPressed = QInputDialog.getText(self, "Save Seed", "Enter a name for this flagset", QLineEdit.Normal, "")
        if okPressed and text != '':
            if os.path.exists(f"saved_flagsets/flagset_{text}.pickle"):
                QMessageBox.about(self, "Error", "That presets already exists!")
            else:
                #print(f"{text}.pickle saved!")

                with open(f"saved_flagsets/flagset_{text}.pickle", "wb") as handle:
                    pickle.dump(self.simple, handle, protocol=None)
                    pickle.dump(self.aesthetic, handle, protocol=None)
                    pickle.dump(self.major, handle, protocol=None)
                    pickle.dump(self.minor, handle, protocol=None)
                    pickle.dump(self.experimental, handle, protocol=None)
                    pickle.dump(self.gamebreaking, handle, protocol=None)
                    pickle.dump(self.mode, handle, protocol=None)
                    pickle.dump(self.romText, handle, protocol=None)

                self.savedPresets[text] = f"flagset_{text}.pickle"
                # update drop-down list with new preset
                self.comboBox.addItem(text)
                index = self.comboBox.findText(text)
                self.comboBox.setCurrentIndex(index)

    # delete preset. Dialog box confirms users choice to delete. check is done to ensure file
    #   exists before deletion is attempted.
    def deleteSeed(self):
        seed = self.comboBox.currentText()

        if not seed == "Select a preset":
            response = QMessageBox.question(self, 'Delete confimation', f"Do you want to delete \'{seed}\'?",
                                            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if response == QMessageBox.Yes:
                #print("You selected yes!")
                if os.path.exists(f"saved_flagsets/flagset_{seed}.pickle"):
                    os.remove(f"saved_flagsets/flagset_{seed}.pickle")
                    del self.savedPresets[seed]
                    self.comboBox.removeItem(self.comboBox.findText(seed))
                    #print(f"{seed} deleted!")
            #else:
                #print("You selected no!")

    # when preset is selected from dropdown list, load the data into dictionaries
    #   and set the UI to reflect the settings stored in the preset.
    # if the only saved preset is deleted, or user selects initial value of
    #   'Select a preset' then the UI is reset (mainly to avoid runtime errors)
    def updatePresetDropdown(self):
        if (self.comboBox.currentIndex() != 0): # text = "Select a preset"
            selectedPreset = self.comboBox.currentText()
            #print(selectedPreset + " selected")
            self.loadPreset(selectedPreset)
        else:
            self.clearUI()

    # clear/reset UI and clear window object variables. Then reset data dictionaries
    #   to the default state of unset/unchecked flags and mode
    def clearUI(self):
        self.mode = ""
        self.seed = ""
        self.flags = ""
        self.seedInput.setText(self.seed)
        self.flagString.setText(self.flags)

        for i in self.middleLeftGroupBox.findChildren((QRadioButton)):
            if (i.mode == 'normal'):
                i.setProperty('checked', True)
                break
            #print(i)

        self.comboBox.setCurrentIndex(0)

        self.initCodes()
        self.updateDictionaries()
        # for j in self.dictionaries:
        #     print(j)
        self.updateFlagString()
        self.updateFlagCheckboxes()

    # when flag UI button is checked, update corresponding dictionary values
    def flagButtonClicked(self):
        for t, d in zip(self.tablist, self.dictionaries):
            children = t.findChildren(FlagCheckBox)
            for c in children:
                if (c.isChecked()):
                    d[c.value]['checked'] = True
                else:
                    d[c.value]['checked'] = False
        self.updateDictionaries()
        self.updateFlagString()


    # Opens file dialog to select rom file and assigns it to value in parent/Window class
    def openFileChooser(self):
        file_path = QFileDialog.getOpenFileName(self, 'Open File', './', filter="All Files(*.*);;Text Files(*.txt)")
        #if file_path[0]:
            #print(str(file_path[0]))

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

    # -------------------- Not currently in use -----------------------------------
    # Open second window and display list of flags and their descriptions
    # (CLEAN THIS UP)
    # def showFlagHelp(self):
    #     dia = QDialog()
    #     dia.setWindowTitle("Flag Descriptions")
    #     dia.setGeometry(300, 300, 600, 550)
    #
    #     tab = QTabWidget()#
    #
    #     tab1 = QScrollArea() #tabObj
    #     tab1wid = QWidget()# from self.tabs
    #     tab.addTab(tab1, "Simple")#
    #     tab1layout = QVBoxLayout()#
    #     for flagname, flagdesc in self.simple.items():#
    #         tab1layout.addWidget(QCheckBox(f"{flagname}  -  {flagdesc['explanation']}"))#
    #     tab1layout.addStretch(1)#
    #     tab1wid.setLayout(tab1layout)#
    #     tab1.setWidgetResizable(True)#
    #     tab1.setWidget(tab1wid)
    #
    #     tab2 = QScrollArea()
    #     tab2wid = QWidget()
    #     tab.addTab(tab2, "Aesthetic")
    #     tab2layout = QVBoxLayout()
    #     for flagname, flagdesc in self.aesthetic.items():
    #         tab2layout.addWidget(QCheckBox(f"{flagname}  -  {flagdesc['explanation']}"))
    #     tab2layout.addStretch(1)
    #     tab2wid.setLayout(tab2layout)
    #     tab2.setWidgetResizable(True)
    #     tab2.setWidget(tab2wid)
    #
    #     tab3 = QScrollArea()
    #     tab3wid = QWidget()
    #     tab.addTab(tab3, "Major")
    #     tab3layout = QVBoxLayout()
    #     for flagname, flagdesc in self.major.items():
    #         tab3layout.addWidget(QCheckBox(f"{flagname}  -  {flagdesc['explanation']}"))
    #     tab3layout.addStretch(1)
    #     tab3wid.setLayout(tab3layout)
    #     tab3.setWidgetResizable(True)
    #     tab3.setWidget(tab3wid)
    #
    #     tab4 = QScrollArea()
    #     tab4wid = QWidget()
    #     tab.addTab(tab4, "Minor")
    #     tab4layout = QVBoxLayout()
    #     for flagname, flagdesc in self.minor.items():
    #         tab4layout.addWidget(QCheckBox(f"{flagname}  -  {flagdesc['explanation']}"))
    #     tab4layout.addStretch(1)
    #     tab4wid.setLayout(tab4layout)
    #     tab4.setWidgetResizable(True)
    #     tab4.setWidget(tab4wid)
    #
    #     tab5 = QScrollArea()
    #     tab5wid = QWidget()
    #     tab.addTab(tab5, "Experimental")
    #     tab5layout = QVBoxLayout()
    #     for flagname, flagdesc in self.experimental.items():
    #         tab5layout.addWidget(QCheckBox(f"{flagname}  -  {flagdesc['explanation']}"))
    #     tab5layout.addStretch(1)
    #     tab5wid.setLayout(tab5layout)
    #     tab5.setWidgetResizable(True)
    #     tab5.setWidget(tab5wid)
    #
    #     tab6 = QScrollArea()
    #     tab6wid = QWidget()
    #     tab.addTab(tab6, "Gamebreaking")
    #     tab6layout = QVBoxLayout()
    #     for flagname, flagdesc in self.gamebreaking.items():
    #         tab6layout.addWidget(QCheckBox(f"{flagname}  -  {flagdesc['explanation']}"))
    #     tab6layout.addStretch(1)
    #     tab6wid.setLayout(tab6layout)
    #     tab6.setWidgetResizable(True)
    #     tab6.setWidget(tab6wid)
    #
    #     tablayout = QVBoxLayout()
    #     tablayout.addWidget(tab)
    #     dia.setLayout(tablayout)
    #     dia.exec()

    # reads files from save directory and puts them in a list
    # files are in the format of .pickle
    def compilePresets(self):
        for file in os.listdir('./saved_flagsets'):
            if re.match(r'flagset_(.*).pickle$', file):
                #print(file)
                temp = list(re.split('[_.]', file))
                self.savedPresets[temp[1]] = file
                #print(self.savedPresets)

    # Reads dictionary data from text file and populates class dictionaries
    def loadPreset(self, flagdict):
        with open(f"saved_flagsets/flagset_{flagdict}.pickle", "rb") as handle:
            #print("this works2")

            # load line by line from .pickle file into each dictionary
            self.simple = pickle.load(handle)
            self.aesthetic = pickle.load(handle)
            self.major = pickle.load(handle)
            self.minor = pickle.load(handle)
            self.experimental = pickle.load(handle)
            self.gamebreaking = pickle.load(handle)
            self.mode = pickle.load(handle)
            self.romText = pickle.load(handle)

        # update 'dictionaries' list with updated/populated data dictionaries
        self.updateDictionaries()

        ### print each dictionary for testing
        #for i in self.dictionaries:
            #print(i)

        # call functions to update UI based upon preset data loaded from file
        self.romInput.setText(self.romText)
        self.updateFlagString()
        self.updateFlagCheckboxes()
        self.updateModeSelection()

    # get seed generation parameters from UI to prepare for seed generation
    # This will only show a confirmation dialog for now, will not actually generate a seed
    def generateSeed(self):

        self.romText = self.romInput.text()
        if self.romText == "":
            QMessageBox.about(self, "Error", "You need to select a FFVI rom!")
        else:
            self.seed = self.seedInput.text()

            displaySeed = self.seed
            if self.seed == "":
                displaySeed = "(none)"

            flags = (self.flags).strip().replace(" ", "\n----")

            # This makes the flag string more readable in the confirm dialog
            message = ((f"Rom: {self.romText}\n"
                            f"Seed: {displaySeed}\n"
                            f"Mode: {self.mode}\n"
                            f"Flags: \n----{flags}\n"
                            f"(Hyphens are not actually used in seed generation)"))
            messBox = QMessageBox.question(self, "Confirm Seed Generation?", message, QMessageBox.Yes| QMessageBox.Cancel)
            if messBox == 16384:
                finalFlags = self.flags.replace(" ", "")
                bundle = f"{self.version}.{self.mode}.{finalFlags}.{self.seed}"

                # call(["python", "tester.py"])
                call(["python", "randomizer.py", self.romText, bundle, "test"])

    # read each dictionary and update text field showing flag codes based upon
    #    flags denoted as 'True'
    def updateFlagString(self):
        temp = ""
        space = False
        for d in self.dictionaries:
            for flagname, flagdesc in d.items():
                if space:
                    temp += " "
                    space = False

                if flagdesc['checked']:
                    temp += flagname
                    space = True


        self.flags = temp
        self.flagString.setText(self.flags)

    # read through dictionaries and set flag checkboxes as 'checked'
    def updateFlagCheckboxes(self):
        for t, d in zip(self.tablist, self.dictionaries):
            # create a list of all checkbox objects from the current QTabWidget
            children = t.findChildren(FlagCheckBox)

            # enumerate checkbox objects and set them to 'checked' if corresponding
            #   flag value is true
            for c in children:
                value = c.value
                #print(value + str(d[value]['checked']))
                if d[value]['checked']:
                    c.setProperty('checked',True)
                else:
                    c.setProperty('checked', False)

    # when radio button is checked, update the main class variable
    def updateRadioSelection(self, mode):
        self.mode = mode
        # print(self.mode)

    # enumerate radio button objects and set them to the currently set mode variable
    def updateModeSelection(self):
        for i in self.middleLeftGroupBox.findChildren((QRadioButton)):
            if (i.mode == self.mode):
                i.setProperty('checked', True)
                break

    # update list variable with data from currently loaded dictionaries
    def updateDictionaries(self):
        self.dictionaries = [self.simple, self.aesthetic, self.major,
                             self.minor, self.experimental, self.gamebreaking]



if __name__ == "__main__":
    App = QApplication(sys.argv)
    window = Window()
    sys.exit(App.exec())
