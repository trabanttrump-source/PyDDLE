import sys
import os
import subprocess
import threading
import time
import ast
import inspect
import tempfile
import shutil
from pathlib import Path
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import pyqtgraph as pg
from pyqtgraph import PlotWidget
import webbrowser
import importlib.metadata
import importlib.util
import json
from datetime import datetime
import re
import io
import contextlib
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon, FancyBboxPatch, Arrow
import matplotlib
matplotlib.use('Agg')
from matplotlib import patches
import requests
import psutil
from PyQt5.QtWebEngineWidgets import QWebEngineView
import urllib.request
import urllib.parse

# Nowe importy dla funkcjonalności poprawy kodu
try:
    import autopep8
    AUTOPEP8_AVAILABLE = True
except ImportError:
    AUTOPEP8_AVAILABLE = False

try:
    import black
    BLACK_AVAILABLE = True
except ImportError:
    BLACK_AVAILABLE = False

try:
    import pyflakes
    import pyflakes.api
    import pyflakes.reporter
    PYFLAKES_AVAILABLE = True
except ImportError:
    PYFLAKES_AVAILABLE = False

class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        
        self.highlightingRules = []
        
        # Keyword format
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("#0078D4"))  # Windows 11 blue
        keywordFormat.setFontWeight(QFont.Bold)
        keywords = [
            'and', 'as', 'assert', 'break', 'class', 'continue', 'def',
            'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda',
            'None', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
            'True', 'try', 'while', 'with', 'yield'
        ]
        for word in keywords:
            pattern = QRegExp("\\b" + word + "\\b")
            rule = (pattern, keywordFormat)
            self.highlightingRules.append(rule)
        
        # Class format
        classFormat = QTextCharFormat()
        classFormat.setForeground(QColor("#107C10"))  # Windows 11 green
        classFormat.setFontWeight(QFont.Bold)
        pattern = QRegExp("\\bclass\\s+(\\w+)")
        rule = (pattern, classFormat)
        self.highlightingRules.append(rule)
        
        # Function format
        functionFormat = QTextCharFormat()
        functionFormat.setForeground(QColor("#D83B01"))  # Windows 11 orange
        pattern = QRegExp("\\bdef\\s+(\\w+)")
        rule = (pattern, functionFormat)
        self.highlightingRules.append(rule)
        
        # String format
        stringFormat = QTextCharFormat()
        stringFormat.setForeground(QColor("#A80000"))  # Dark red
        pattern = QRegExp("\".*\"|'.*'")
        rule = (pattern, stringFormat)
        self.highlightingRules.append(rule)
        
        # Comment format
        commentFormat = QTextCharFormat()
        commentFormat.setForeground(QColor("#008000"))  # Green
        pattern = QRegExp("#[^\n]*")
        rule = (pattern, commentFormat)
        self.highlightingRules.append(rule)
        
        # Number format
        numberFormat = QTextCharFormat()
        numberFormat.setForeground(QColor("#AF00DB"))  # Purple
        pattern = QRegExp("\\b[0-9]+\\b")
        rule = (pattern, numberFormat)
        self.highlightingRules.append(rule)

    def highlightBlock(self, text):
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)
        
        self.setCurrentBlockState(0)

class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.codeEditor = editor

    def sizeHint(self):
        return QSize(self.codeEditor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.codeEditor.lineNumberAreaPaintEvent(event)

class CodeEditor(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        
        self.setFont(QFont("Cascadia Code", 10))
        self.highlighter = PythonHighlighter(self.document())
        
        # Ustawienia dla autouzupełniania
        self.completer = QCompleter([])
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insertCompletion)
        
        # Słownik dla podpowiedzi AI
        self.ai_suggestions = {}

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        space = 3 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#F3F3F3"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor("#666666"))
                painter.drawText(0, int(top), self.lineNumberArea.width(), self.fontMetrics().height(),
                                Qt.AlignRight, number)

            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor("#E8F4FD")
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
        self.setExtraSelections(extraSelections)

    def keyPressEvent(self, event):
        # Autouzupełnianie nawiasów
        if event.key() in [Qt.Key_ParenLeft, Qt.Key_BraceLeft, Qt.Key_BracketLeft]:
            super().keyPressEvent(event)
            cursor = self.textCursor()
            if event.key() == Qt.Key_ParenLeft:
                cursor.insertText(")")
            elif event.key() == Qt.Key_BraceLeft:
                cursor.insertText("}")
            elif event.key() == Qt.Key_BracketLeft:
                cursor.insertText("]")
            cursor.movePosition(QTextCursor.Left)
            self.setTextCursor(cursor)
        # Automatyczne wcięcie po dwukropku
        elif event.key() == Qt.Key_Colon:
            super().keyPressEvent(event)
            cursor = self.textCursor()
            cursor.insertText("\n    ")
        # Automatyczne wcięcie po Enter
        elif event.key() == Qt.Key_Return:
            cursor = self.textCursor()
            current_block = cursor.block()
            current_text = current_block.text()
            
            # Sprawdź czy poprzednia linia kończy się dwukropkiem
            if current_text.strip().endswith(':'):
                super().keyPressEvent(event)
                cursor.insertText("    ")
            else:
                # Sprawdź wcięcie poprzedniej linii
                indent_match = re.match(r'^(\s*)', current_text)
                if indent_match:
                    indent = indent_match.group(1)
                    super().keyPressEvent(event)
                    cursor.insertText(indent)
                else:
                    super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def insertCompletion(self, completion):
        tc = self.textCursor()
        tc.select(QTextCursor.WordUnderCursor)
        tc.removeSelectedText()
        tc.insertText(completion)
        self.setTextCursor(tc)

    def updateCompleter(self, words):
        """Aktualizuje listę słów dla autouzupełniania"""
        self.completer.model().setStringList(words)

class SyntaxChecker(QThread):
    error_found = pyqtSignal(int, str, str)  # line, message, type
    
    def __init__(self, code):
        super().__init__()
        self.code = code
        
    def run(self):
        try:
            # Sprawdzanie składni za pomocą ast
            ast.parse(self.code)
        except SyntaxError as e:
            self.error_found.emit(e.lineno, e.msg, "Syntax Error")

class VariableInspector(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setHeaderLabels(["Variable", "Value", "Type"])
        self.setColumnCount(3)

class AISuggestionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("AI Suggestions")
        self.setGeometry(200, 200, 600, 400)
        
        layout = QVBoxLayout()
        
        # Prompt input field
        self.promptEdit = QTextEdit()
        self.promptEdit.setPlaceholderText("Describe what you want to achieve or what code you need...")
        layout.addWidget(QLabel("Prompt:"))
        layout.addWidget(self.promptEdit)
        
        # Buttons
        btnLayout = QHBoxLayout()
        self.btnGenerate = QPushButton("Generate code")
        self.btnInsert = QPushButton("Insert code")
        self.btnCancel = QPushButton("Cancel")
        
        btnLayout.addWidget(self.btnGenerate)
        btnLayout.addWidget(self.btnInsert)
        btnLayout.addWidget(self.btnCancel)
        
        # Result field
        self.resultEdit = QTextEdit()
        self.resultEdit.setReadOnly(True)
        layout.addWidget(QLabel("Generated code:"))
        layout.addWidget(self.resultEdit)
        layout.addLayout(btnLayout)
        
        self.setLayout(layout)
        
        # Connections
        self.btnGenerate.clicked.connect(self.generateCode)
        self.btnInsert.clicked.connect(self.insertCode)
        self.btnCancel.clicked.connect(self.reject)

    def generateCode(self):
        prompt = self.promptEdit.toPlainText()
        if not prompt:
            QMessageBox.warning(self, "Error", "Enter AI prompt")
            return
            
        # Simple AI simulation - in real implementation this would connect to AI API
        suggestions = {
            "function": "def my_function():\n    \"\"\"Function documentation\"\"\"\n    pass",
            "class": "class MyClass:\n    def __init__(self):\n        pass",
            "loop": "for i in range(10):\n    print(i)",
            "condition": "if condition:\n    # code\nelse:\n    # alternative code"
        }
        
        # Simple matching based on keywords
        generated_code = "# AI generated code\n"
        if "function" in prompt.lower():
            generated_code += suggestions["function"]
        elif "class" in prompt.lower():
            generated_code += suggestions["class"]
        elif "loop" in prompt.lower():
            generated_code += suggestions["loop"]
        elif "condition" in prompt.lower() or "if" in prompt.lower():
            generated_code += suggestions["condition"]
        else:
            generated_code += "# No specific request recognized\n# Here would be AI generated code"
            
        self.resultEdit.setPlainText(generated_code)

    def insertCode(self):
        code = self.resultEdit.toPlainText()
        if code:
            self.parent().editor.insertPlainText(code)
        self.accept()

class CompilationProgressDialog(QDialog):
    progress_updated = pyqtSignal(int, str)
    compilation_finished = pyqtSignal(bool, str)
    log_updated = pyqtSignal(str)  # unified log message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("PyDDLE - Compilation in progress...")
        self.setGeometry(400, 400, 800, 600)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Progress bar
        self.progressBar = QProgressBar()
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        layout.addWidget(QLabel("Compilation progress:"))
        layout.addWidget(self.progressBar)
        
        # Current operation label
        self.currentOperation = QLabel("Preparing compilation...")
        layout.addWidget(self.currentOperation)
        
        # Single log output
        layout.addWidget(QLabel("Compilation log:"))
        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        self.logText.setFont(QFont("Consolas", 9))
        layout.addWidget(self.logText)
        
        # Buttons
        btnLayout = QHBoxLayout()
        self.cancelBtn = QPushButton("Cancel")
        self.closeBtn = QPushButton("Close")
        self.openFolderBtn = QPushButton("Open output folder")
        self.closeBtn.setEnabled(False)
        self.openFolderBtn.setEnabled(False)
        
        btnLayout.addWidget(self.cancelBtn)
        btnLayout.addWidget(self.openFolderBtn)
        btnLayout.addWidget(self.closeBtn)
        
        layout.addLayout(btnLayout)
        
        self.setLayout(layout)
        
        # Connections
        self.cancelBtn.clicked.connect(self.cancelCompilation)
        self.closeBtn.clicked.connect(self.accept)
        self.openFolderBtn.clicked.connect(self.openOutputFolder)
        self.progress_updated.connect(self.updateProgress)
        self.compilation_finished.connect(self.finishCompilation)
        self.log_updated.connect(self.updateLog)
        
        self.is_cancelled = False
        self.compilation_process = None
        self.output_dir = None
        
    def updateProgress(self, value, operation):
        self.progressBar.setValue(value)
        self.currentOperation.setText(operation)
        
    def updateLog(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {message}"
        self.logText.append(formatted_message)
        # Auto-scroll to bottom
        self.logText.verticalScrollBar().setValue(self.logText.verticalScrollBar().maximum())
        
    def finishCompilation(self, success, message):
        if success:
            self.progressBar.setValue(100)
            self.currentOperation.setText("✓ Compilation completed successfully")
            self.log_updated.emit("Compilation completed successfully!")
            self.openFolderBtn.setEnabled(True)
        else:
            self.progressBar.setValue(0)
            self.currentOperation.setText("✗ Compilation error")
            self.log_updated.emit(f"Error: {message}")
            
        self.cancelBtn.setEnabled(False)
        self.closeBtn.setEnabled(True)
        
    def cancelCompilation(self):
        self.is_cancelled = True
        if self.compilation_process:
            self.compilation_process.terminate()
        self.currentOperation.setText("❌ Compilation cancelled by user")
        self.log_updated.emit("Compilation cancelled by user")
        self.closeBtn.setEnabled(True)
        self.cancelBtn.setEnabled(False)
        
    def openOutputFolder(self):
        if self.output_dir and os.path.exists(self.output_dir):
            # Use QDesktopServices to open folder - more reliable
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_dir))
        else:
            QMessageBox.warning(self, "Error", "Output folder doesn't exist")

class PyInstallerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("PyDDLE - Convert to EXE")
        self.setGeometry(100, 100, 900, 700)
        
        layout = QVBoxLayout()
        
        # Create tab widget for different sections
        self.tabs = QTabWidget()
        
        # Script Location Tab
        self.script_tab = QWidget()
        self.setup_script_tab()
        self.tabs.addTab(self.script_tab, "Script Location")
        
        # Build Options Tab
        self.build_tab = QWidget()
        self.setup_build_tab()
        self.tabs.addTab(self.build_tab, "Build Options")
        
        # Additional Files Tab
        self.files_tab = QWidget()
        self.setup_files_tab()
        self.tabs.addTab(self.files_tab, "Additional Files")
        
        # Settings Tab
        self.settings_tab = QWidget()
        self.setup_settings_tab()
        self.tabs.addTab(self.settings_tab, "Settings")
        
        layout.addWidget(self.tabs)
        
        # Buttons
        btnLayout = QHBoxLayout()
        self.convertBtn = QPushButton("Convert to EXE")
        self.cancelBtn = QPushButton("Cancel")
        
        btnLayout.addWidget(self.convertBtn)
        btnLayout.addWidget(self.cancelBtn)
        
        layout.addLayout(btnLayout)
        
        self.setLayout(layout)
        
        # Connections
        self.convertBtn.clicked.connect(self.convertToExe)
        self.cancelBtn.clicked.connect(self.reject)
        
    def setup_script_tab(self):
        layout = QVBoxLayout()
        
        # Script file selection
        script_group = QGroupBox("Script Location")
        script_layout = QVBoxLayout()
        
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("Script path:"))
        self.script_path = QLineEdit()
        self.script_path.setText(self.parent.current_file or "")
        file_layout.addWidget(self.script_path)
        self.browse_script_btn = QPushButton("Browse")
        file_layout.addWidget(self.browse_script_btn)
        script_layout.addLayout(file_layout)
        
        # Working directory
        workdir_layout = QHBoxLayout()
        workdir_layout.addWidget(QLabel("Working directory:"))
        self.workdir_path = QLineEdit()
        workdir_layout.addWidget(self.workdir_path)
        self.browse_workdir_btn = QPushButton("Browse")
        workdir_layout.addWidget(self.browse_workdir_btn)
        script_layout.addLayout(workdir_layout)
        
        script_group.setLayout(script_layout)
        layout.addWidget(script_group)
        
        # Output directory
        output_group = QGroupBox("Output Directory")
        output_layout = QVBoxLayout()
        
        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(QLabel("Output path:"))
        self.output_path = QLineEdit()
        self.output_path.setText(os.path.join(os.path.expanduser("~"), "PyDDLE_Output"))
        output_path_layout.addWidget(self.output_path)
        self.browse_output_btn = QPushButton("Browse")
        output_path_layout.addWidget(self.browse_output_btn)
        output_layout.addLayout(output_path_layout)
        
        # Create output directory if it doesn't exist
        self.create_output_btn = QPushButton("Create Output Directory")
        output_layout.addWidget(self.create_output_btn)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        layout.addStretch()
        self.script_tab.setLayout(layout)
        
        # Connections for script tab
        self.browse_script_btn.clicked.connect(self.browse_script)
        self.browse_workdir_btn.clicked.connect(self.browse_workdir)
        self.browse_output_btn.clicked.connect(self.browse_output)
        self.create_output_btn.clicked.connect(self.create_output_dir)
        
    def setup_build_tab(self):
        layout = QVBoxLayout()
        
        # Build mode
        mode_group = QGroupBox("Build Mode")
        mode_layout = QVBoxLayout()
        
        self.onefile_radio = QRadioButton("One file (--onefile)")
        self.onefile_radio.setChecked(True)
        self.onedir_radio = QRadioButton("One directory (--onedir)")
        
        mode_layout.addWidget(self.onefile_radio)
        mode_layout.addWidget(self.onedir_radio)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)
        
        # Console window
        console_group = QGroupBox("Console Window")
        console_layout = QVBoxLayout()
        
        self.console_radio = QRadioButton("Console based (--console)")
        self.console_radio.setChecked(True)
        self.windowed_radio = QRadioButton("Window based (--windowed)")
        
        console_layout.addWidget(self.console_radio)
        console_layout.addWidget(self.windowed_radio)
        console_group.setLayout(console_layout)
        layout.addWidget(console_group)
        
        # Icon
        icon_group = QGroupBox("Icon")
        icon_layout = QVBoxLayout()
        
        icon_path_layout = QHBoxLayout()
        icon_path_layout.addWidget(QLabel("Icon file:"))
        self.icon_path = QLineEdit()
        icon_path_layout.addWidget(self.icon_path)
        self.browse_icon_btn = QPushButton("Browse")
        icon_path_layout.addWidget(self.browse_icon_btn)
        icon_layout.addLayout(icon_path_layout)
        
        icon_group.setLayout(icon_layout)
        layout.addWidget(icon_group)
        
        # Additional options
        options_group = QGroupBox("Additional Options")
        options_layout = QVBoxLayout()
        
        self.clean_checkbox = QCheckBox("Clean build (--clean)")
        self.clean_checkbox.setChecked(True)
        self.noconfirm_checkbox = QCheckBox("No confirm (--noconfirm)")
        self.noconfirm_checkbox.setChecked(True)
        self.strip_checkbox = QCheckBox("Strip executable (--strip)")
        self.upx_checkbox = QCheckBox("Use UPX (--upx-dir)")
        self.debug_checkbox = QCheckBox("Debug mode (--debug)")
        
        options_layout.addWidget(self.clean_checkbox)
        options_layout.addWidget(self.noconfirm_checkbox)
        options_layout.addWidget(self.strip_checkbox)
        options_layout.addWidget(self.upx_checkbox)
        options_layout.addWidget(self.debug_checkbox)
        
        options_group.setLayout(options_layout)
        layout.addWidget(options_group)
        
        layout.addStretch()
        self.build_tab.setLayout(layout)
        
        # Connections for build tab
        self.browse_icon_btn.clicked.connect(self.browse_icon)
        
    def setup_files_tab(self):
        layout = QVBoxLayout()
        
        # Additional files
        files_group = QGroupBox("Additional Files and Data")
        files_layout = QVBoxLayout()
        
        files_help = QLabel("Add files or folders that your script needs (e.g., images, data files)")
        files_help.setWordWrap(True)
        files_layout.addWidget(files_help)
        
        # Additional files list
        self.additional_files_list = QListWidget()
        files_layout.addWidget(self.additional_files_list)
        
        # Buttons for managing files
        files_buttons_layout = QHBoxLayout()
        self.add_file_btn = QPushButton("Add File")
        self.add_folder_btn = QPushButton("Add Folder")
        self.remove_file_btn = QPushButton("Remove Selected")
        
        files_buttons_layout.addWidget(self.add_file_btn)
        files_buttons_layout.addWidget(self.add_folder_btn)
        files_buttons_layout.addWidget(self.remove_file_btn)
        files_layout.addLayout(files_buttons_layout)
        
        files_group.setLayout(files_layout)
        layout.addWidget(files_group)
        
        # Binary dependencies
        binary_group = QGroupBox("Binary Dependencies")
        binary_layout = QVBoxLayout()
        
        binary_help = QLabel("Add binary files that need to be included")
        binary_help.setWordWrap(True)
        binary_layout.addWidget(binary_help)
        
        self.binary_files_list = QListWidget()
        binary_layout.addWidget(self.binary_files_list)
        
        binary_buttons_layout = QHBoxLayout()
        self.add_binary_btn = QPushButton("Add Binary")
        self.remove_binary_btn = QPushButton("Remove Selected")
        
        binary_buttons_layout.addWidget(self.add_binary_btn)
        binary_buttons_layout.addWidget(self.remove_binary_btn)
        binary_layout.addLayout(binary_buttons_layout)
        
        binary_group.setLayout(binary_layout)
        layout.addWidget(binary_group)
        
        layout.addStretch()
        self.files_tab.setLayout(layout)
        
        # Connections for files tab
        self.add_file_btn.clicked.connect(self.add_file)
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.remove_file_btn.clicked.connect(self.remove_selected_file)
        self.add_binary_btn.clicked.connect(self.add_binary)
        self.remove_binary_btn.clicked.connect(self.remove_selected_binary)
        
    def setup_settings_tab(self):
        layout = QVBoxLayout()
        
        # Hidden imports
        imports_group = QGroupBox("Hidden Imports")
        imports_layout = QVBoxLayout()
        
        imports_help = QLabel("Specify modules that PyInstaller might not detect automatically")
        imports_help.setWordWrap(True)
        imports_layout.addWidget(imports_help)
        
        imports_input_layout = QHBoxLayout()
        imports_input_layout.addWidget(QLabel("Module names:"))
        self.hidden_imports = QLineEdit()
        self.hidden_imports.setPlaceholderText("comma separated, e.g., pygame,requests,pandas")
        imports_input_layout.addWidget(self.hidden_imports)
        imports_layout.addLayout(imports_input_layout)
        
        imports_group.setLayout(imports_layout)
        layout.addWidget(imports_group)
        
        # Exclude modules
        exclude_group = QGroupBox("Exclude Modules")
        exclude_layout = QVBoxLayout()
        
        exclude_help = QLabel("Exclude modules that are not needed to reduce file size")
        exclude_help.setWordWrap(True)
        exclude_layout.addWidget(exclude_help)
        
        exclude_input_layout = QHBoxLayout()
        exclude_input_layout.addWidget(QLabel("Exclude modules:"))
        self.exclude_modules = QLineEdit()
        self.exclude_modules.setPlaceholderText("comma separated, e.g., tkinter,matplotlib")
        exclude_input_layout.addWidget(self.exclude_modules)
        exclude_layout.addLayout(exclude_input_layout)
        
        exclude_group.setLayout(exclude_layout)
        layout.addWidget(exclude_group)
        
        # Advanced options
        advanced_group = QGroupBox("Advanced Options")
        advanced_layout = QVBoxLayout()
        
        self.optimize_checkbox = QCheckBox("Optimize generated bytecode (-O)")
        self.no_precompress_checkbox = QCheckBox("Disable pre-compression (--no-pre-compress)")
        
        advanced_layout.addWidget(self.optimize_checkbox)
        advanced_layout.addWidget(self.no_precompress_checkbox)
        
        # Runtime hooks
        hooks_layout = QHBoxLayout()
        hooks_layout.addWidget(QLabel("Runtime hooks:"))
        self.runtime_hooks = QLineEdit()
        hooks_layout.addWidget(self.runtime_hooks)
        self.browse_hooks_btn = QPushButton("Browse")
        hooks_layout.addWidget(self.browse_hooks_btn)
        advanced_layout.addLayout(hooks_layout)
        
        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)
        
        layout.addStretch()
        self.settings_tab.setLayout(layout)
        
        # Connections for settings tab
        self.browse_hooks_btn.clicked.connect(self.browse_hooks)
        
    def browse_script(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Python Script", "", "Python Files (*.py)")
        if file_path:
            self.script_path.setText(file_path)
            # Auto-set working directory to script directory
            self.workdir_path.setText(os.path.dirname(file_path))
            
    def browse_workdir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Working Directory")
        if dir_path:
            self.workdir_path.setText(dir_path)
            
    def browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if dir_path:
            self.output_path.setText(dir_path)
            
    def create_output_dir(self):
        output_dir = self.output_path.text()
        if not output_dir:
            output_dir = os.path.join(os.path.expanduser("~"), "PyDDLE_Output")
            self.output_path.setText(output_dir)
            
        try:
            os.makedirs(output_dir, exist_ok=True)
            QMessageBox.information(self, "Success", f"Output directory created: {output_dir}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not create directory: {str(e)}")
            
    def browse_icon(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Icon File", "", "Icon Files (*.ico)")
        if file_path:
            self.icon_path.setText(file_path)
            
    def add_file(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Additional Files")
        for file_path in files:
            self.additional_files_list.addItem(file_path)
            
    def add_folder(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Additional Folder")
        if dir_path:
            self.additional_files_list.addItem(dir_path)
            
    def remove_selected_file(self):
        for item in self.additional_files_list.selectedItems():
            self.additional_files_list.takeItem(self.additional_files_list.row(item))
            
    def add_binary(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select Binary Files", "", "All Files (*)")
        for file_path in files:
            self.binary_files_list.addItem(file_path)
            
    def remove_selected_binary(self):
        for item in self.binary_files_list.selectedItems():
            self.binary_files_list.takeItem(self.binary_files_list.row(item))
            
    def browse_hooks(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Runtime Hook File", "", "Python Files (*.py)")
        if file_path:
            self.runtime_hooks.setText(file_path)
            
    def convertToExe(self):
        # Validate inputs
        script_path = self.script_path.text()
        if not script_path or not os.path.exists(script_path):
            QMessageBox.warning(self, "Error", "Please select a valid Python script")
            return
            
        output_dir = self.output_path.text()
        if not output_dir:
            QMessageBox.warning(self, "Error", "Please specify an output directory")
            return
            
        # Create output directory if it doesn't exist
        try:
            os.makedirs(output_dir, exist_ok=True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not create output directory: {str(e)}")
            return
            
        # Show progress dialog
        self.progress_dialog = CompilationProgressDialog(self)
        self.progress_dialog.output_dir = output_dir
        self.progress_dialog.show()
        
        # Run compilation in thread
        thread = threading.Thread(target=self.runCompilation, args=(script_path, output_dir))
        thread.daemon = True
        thread.start()
        
    def runCompilation(self, script_path, output_dir):
        try:
            # Step 1: Check/install PyInstaller
            self.progress_dialog.progress_updated.emit(5, "Checking PyInstaller...")
            self.progress_dialog.log_updated.emit("Checking PyInstaller availability...")
            
            try:
                import PyInstaller
            except ImportError:
                self.progress_dialog.progress_updated.emit(10, "Installing PyInstaller...")
                self.progress_dialog.log_updated.emit("PyInstaller not found, starting installation...")
                
                cmd = [sys.executable, "-m", "pip", "install", "pyinstaller"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    self.progress_dialog.log_updated.emit(f"PyInstaller installation error: {result.stderr}")
                    self.progress_dialog.compilation_finished.emit(False, f"PyInstaller installation error: {result.stderr}")
                    return
                self.progress_dialog.progress_updated.emit(15, "PyInstaller installed successfully")
                self.progress_dialog.log_updated.emit("PyInstaller installed successfully")
            
            # Step 2: Building PyInstaller command
            self.progress_dialog.progress_updated.emit(20, "Preparing compilation command...")
            self.progress_dialog.log_updated.emit("Preparing compilation parameters...")
            
            cmd = [sys.executable, "-m", "PyInstaller"]
            
            # Basic options
            if self.onefile_radio.isChecked():
                cmd.append("--onefile")
                self.progress_dialog.log_updated.emit("Build mode: One file (--onefile)")
            else:
                cmd.append("--onedir")
                self.progress_dialog.log_updated.emit("Build mode: One directory (--onedir)")
                
            if self.windowed_radio.isChecked():
                cmd.append("--windowed")
                self.progress_dialog.log_updated.emit("Console: Window based (--windowed)")
            else:
                cmd.append("--console")
                self.progress_dialog.log_updated.emit("Console: Console based (--console)")
                
            # Output paths
            cmd.extend(["--distpath", output_dir])
            cmd.extend(["--workpath", os.path.join(output_dir, "build")])
            cmd.extend(["--specpath", output_dir])
            
            # Working directory
            workdir = self.workdir_path.text()
            if workdir and os.path.exists(workdir):
                original_cwd = os.getcwd()
                os.chdir(workdir)
                self.progress_dialog.log_updated.emit(f"Working directory: {workdir}")
                
            # Icon
            icon_path = self.icon_path.text()
            if icon_path and os.path.exists(icon_path):
                cmd.extend(["--icon", icon_path])
                self.progress_dialog.log_updated.emit(f"Icon: {icon_path}")
                
            # Additional files
            for i in range(self.additional_files_list.count()):
                file_path = self.additional_files_list.item(i).text()
                if os.path.exists(file_path):
                    if os.path.isfile(file_path):
                        dest_name = os.path.basename(file_path)
                        cmd.extend(["--add-data", f"{file_path}{os.pathsep}.{os.pathsep}{dest_name}"])
                        self.progress_dialog.log_updated.emit(f"Added file: {file_path}")
                    else:  # directory
                        dir_name = os.path.basename(file_path.rstrip(os.path.sep))
                        cmd.extend(["--add-data", f"{file_path}{os.pathsep}.{os.pathsep}{dir_name}"])
                        self.progress_dialog.log_updated.emit(f"Added directory: {file_path}")
                        
            # Binary files
            for i in range(self.binary_files_list.count()):
                file_path = self.binary_files_list.item(i).text()
                if os.path.exists(file_path):
                    cmd.extend(["--add-binary", f"{file_path}{os.pathsep}."])
                    self.progress_dialog.log_updated.emit(f"Added binary: {file_path}")
            
            # Hidden imports
            hidden_imports = self.hidden_imports.text()
            if hidden_imports:
                imports = [imp.strip() for imp in hidden_imports.split(',') if imp.strip()]
                for imp in imports:
                    cmd.extend(["--hidden-import", imp])
                    self.progress_dialog.log_updated.emit(f"Added hidden import: {imp}")
                    
            # Exclude modules
            exclude_modules = self.exclude_modules.text()
            if exclude_modules:
                excludes = [excl.strip() for excl in exclude_modules.split(',') if excl.strip()]
                for excl in excludes:
                    cmd.extend(["--exclude-module", excl])
                    self.progress_dialog.log_updated.emit(f"Excluded module: {excl}")
            
            # Advanced options
            if self.clean_checkbox.isChecked():
                cmd.append("--clean")
                self.progress_dialog.log_updated.emit("Clean build enabled (--clean)")
                
            if self.noconfirm_checkbox.isChecked():
                cmd.append("--noconfirm")
                
            if self.strip_checkbox.isChecked():
                cmd.append("--strip")
                self.progress_dialog.log_updated.emit("Strip executable enabled (--strip)")
                
            if self.upx_checkbox.isChecked():
                cmd.append("--upx-dir")
                cmd.append("")
                self.progress_dialog.log_updated.emit("UPX compression enabled")
                
            if self.debug_checkbox.isChecked():
                cmd.append("--debug")
                self.progress_dialog.log_updated.emit("Debug mode enabled")
                
            if self.optimize_checkbox.isChecked():
                cmd.append("--optimize=1")
                self.progress_dialog.log_updated.emit("Bytecode optimization enabled")
                
            if self.no_precompress_checkbox.isChecked():
                cmd.append("--no-pre-compress")
                self.progress_dialog.log_updated.emit("Pre-compression disabled")
                
            # Runtime hooks
            hooks_path = self.runtime_hooks.text()
            if hooks_path and os.path.exists(hooks_path):
                cmd.extend(["--runtime-hook", hooks_path])
                self.progress_dialog.log_updated.emit(f"Added runtime hook: {hooks_path}")
            
            # Add script name
            cmd.append(script_path)
            
            # Step 3: Start compilation
            self.progress_dialog.progress_updated.emit(30, "Starting compilation...")
            self.progress_dialog.log_updated.emit("Starting compilation...")
            self.progress_dialog.log_updated.emit("Command: " + " ".join(cmd))
            
            # Run process with timeout
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                     text=True, bufsize=1, universal_newlines=True)
            self.progress_dialog.compilation_process = process
            
            # Function to read output in separate thread
            def read_output(pipe, is_stderr=False):
                try:
                    for line in iter(pipe.readline, ''):
                        if self.progress_dialog.is_cancelled:
                            break
                        if line:
                            # Color code errors
                            if is_stderr or "error" in line.lower():
                                self.progress_dialog.log_updated.emit(f"ERROR: {line.strip()}")
                            else:
                                self.progress_dialog.log_updated.emit(line.strip())
                    pipe.close()
                except Exception as e:
                    self.progress_dialog.log_updated.emit(f"Error reading output: {e}")
            
            # Start threads to read stdout and stderr
            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, False))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, True))
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()
            
            # Track progress
            current_progress = 30
            max_progress = 95
            start_time = time.time()
            timeout = 600  # 10 minutes timeout
            
            while process.poll() is None:
                if self.progress_dialog.is_cancelled:
                    process.terminate()
                    break
                    
                # Gradually increase progress every second
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self.progress_dialog.log_updated.emit("Compilation timeout - process taking too long")
                    process.terminate()
                    break
                    
                # Update progress every second
                time.sleep(1)
                current_progress = min(max_progress, current_progress + 1)
                self.progress_dialog.progress_updated.emit(int(current_progress), "Compilation in progress...")
                
            # Wait for process completion
            returncode = process.wait()
            
            # Restore original working directory if changed
            if 'original_cwd' in locals():
                os.chdir(original_cwd)
            
            if self.progress_dialog.is_cancelled:
                self.progress_dialog.compilation_finished.emit(False, "Compilation cancelled")
                return
                
            if returncode == 0:
                self.progress_dialog.progress_updated.emit(98, "Finalizing...")
                self.progress_dialog.log_updated.emit("Finalizing compilation...")
                
                # Show completion message
                script_name = os.path.splitext(os.path.basename(script_path))[0]
                if self.onefile_radio.isChecked():
                    exe_path = os.path.join(output_dir, f"{script_name}.exe")
                    self.progress_dialog.log_updated.emit(f"Single executable created: {exe_path}")
                else:
                    exe_dir = os.path.join(output_dir, script_name)
                    self.progress_dialog.log_updated.emit(f"Executable directory created: {exe_dir}")
                
                self.progress_dialog.log_updated.emit("Compilation completed successfully!")
                self.progress_dialog.compilation_finished.emit(True, "Compilation completed successfully!")
            else:
                self.progress_dialog.log_updated.emit(f"Compilation error (exit code: {returncode})")
                self.progress_dialog.compilation_finished.emit(False, f"Compilation error (code: {returncode})")
                
        except Exception as e:
            self.progress_dialog.log_updated.emit(f"Unexpected error: {e}")
            self.progress_dialog.compilation_finished.emit(False, f"Error: {e}")

class ImportChecker:
    @staticmethod
    def find_missing_imports(code):
        """Find missing imports in code"""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []  # Don't check imports if code has syntax errors
        
        imports = set()
        
        # Find all imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])  # Only main module
            elif isinstance(node, ast.ImportFrom):
                if node.module:  # from module import something
                    imports.add(node.module.split('.')[0])
        
        # Check which imports are available
        missing = []
        for imp in imports:
            try:
                __import__(imp)
            except ImportError:
                missing.append(imp)
        
        return missing
    
    @staticmethod
    def install_package(package_name):
        """Install package using pip"""
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except subprocess.CalledProcessError:
            return False

class ImportCheckDialog(QDialog):
    def __init__(self, missing_imports, parent=None):
        super().__init__(parent)
        self.missing_imports = missing_imports
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Missing Libraries")
        self.setGeometry(300, 300, 500, 400)
        
        layout = QVBoxLayout()
        
        # Information
        info_label = QLabel("Missing libraries detected in code. Select which ones to install:")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # List of missing libraries
        self.imports_list = QListWidget()
        for imp in self.missing_imports:
            item = QListWidgetItem(imp)
            item.setCheckState(Qt.Checked)
            self.imports_list.addItem(item)
        layout.addWidget(self.imports_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.install_btn = QPushButton("Install selected")
        self.skip_btn = QPushButton("Skip")
        self.cancel_btn = QPushButton("Cancel")
        
        btn_layout.addWidget(self.install_btn)
        btn_layout.addWidget(self.skip_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
        
        # Connections
        self.install_btn.clicked.connect(self.install_selected)
        self.skip_btn.clicked.connect(self.skip_installation)
        self.cancel_btn.clicked.connect(self.reject)
        
    def install_selected(self):
        """Install selected libraries"""
        selected_imports = []
        for i in range(self.imports_list.count()):
            item = self.imports_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_imports.append(item.text())
        
        if not selected_imports:
            QMessageBox.warning(self, "No selection", "No libraries selected for installation.")
            return
        
        # Show progress dialog
        progress = QProgressDialog("Installing libraries...", "Cancel", 0, len(selected_imports), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        success_count = 0
        for i, package in enumerate(selected_imports):
            progress.setValue(i)
            progress.setLabelText(f"Installing {package}...")
            QApplication.processEvents()
            
            if progress.wasCanceled():
                break
                
            if ImportChecker.install_package(package):
                success_count += 1
            else:
                QMessageBox.warning(self, "Installation error", f"Failed to install: {package}")
        
        progress.setValue(len(selected_imports))
        
        if success_count > 0:
            QMessageBox.information(self, "Success", f"Successfully installed {success_count}/{len(selected_imports)} libraries.")
        self.accept()
        
    def skip_installation(self):
        """Skip installation and accept dialog"""
        self.accept()

class CodeFormatter:
    @staticmethod
    def format_code(code):
        """Format code using available libraries"""
        # First try autopep8
        if AUTOPEP8_AVAILABLE:
            try:
                return autopep8.fix_code(code, options={'aggressive': 1})
            except:
                pass
        
        # Then try black
        if BLACK_AVAILABLE:
            try:
                return black.format_str(code, mode=black.FileMode())
            except:
                pass
        
        # Fallback to basic formatting
        return CodeFormatter.basic_format(code)
    
    @staticmethod
    def basic_format(code):
        """Safe code formatting - only basic indentation"""
        lines = code.split('\n')
        formatted_lines = []
        indent_level = 0
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:  # Empty line
                formatted_lines.append('')
                continue
                
            # Preserve original indentation for comments and empty lines
            if stripped.startswith('#') or not stripped:
                formatted_lines.append(line)
                continue
                
            # Calculate correct indentation
            current_indent = indent_level
            
            # Add appropriate indentation
            formatted_line = '    ' * current_indent + stripped
            formatted_lines.append(formatted_line)
            
            # Increase indentation if line ends with colon
            if stripped.endswith(':') and not stripped.startswith('#'):
                indent_level += 1
            # Decrease indentation for some keywords
            elif stripped.startswith(('return', 'break', 'continue', 'pass')):
                indent_level = max(0, indent_level - 1)
                
        return '\n'.join(formatted_lines)
    
    @staticmethod
    def comment_selection(code):
        """Comment selected lines"""
        lines = code.split('\n')
        commented_lines = ['# ' + line for line in lines]
        return '\n'.join(commented_lines)
    
    @staticmethod
    def uncomment_selection(code):
        """Uncomment selected lines"""
        lines = code.split('\n')
        uncommented_lines = []
        for line in lines:
            if line.strip().startswith('# '):
                uncommented_lines.append(line[2:])
            elif line.strip().startswith('#'):
                uncommented_lines.append(line[1:])
            else:
                uncommented_lines.append(line)
        return '\n'.join(uncommented_lines)
    
    @staticmethod
    def indent_selection(code):
        """Increase indentation of selected lines"""
        lines = code.split('\n')
        indented_lines = ['    ' + line for line in lines]
        return '\n'.join(indented_lines)
    
    @staticmethod
    def dedent_selection(code):
        """Decrease indentation of selected lines"""
        lines = code.split('\n')
        dedented_lines = []
        for line in lines:
            if line.startswith('    '):
                dedented_lines.append(line[4:])
            elif line.startswith('\t'):
                dedented_lines.append(line[1:])
            else:
                dedented_lines.append(line)
        return '\n'.join(dedented_lines)

class StatusBarWithButtons(QStatusBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        
    def initUI(self):
        # Add buttons to statusbar
        self.quickAccessLayout = QHBoxLayout()
        
        # Quick access buttons
        self.runBtn = QPushButton("▶ Run")
        self.runBtn.setMaximumWidth(100)
        self.runBtn.clicked.connect(self.parent.runCode)
        
        self.testBtn = QPushButton("🧪 Test")
        self.testBtn.setMaximumWidth(100)
        self.testBtn.clicked.connect(self.parent.testApplication)
        
        self.debugBtn = QPushButton("🐞 Debug")
        self.debugBtn.setMaximumWidth(100)
        self.debugBtn.clicked.connect(self.parent.showDebugger)
        
        self.stopBtn = QPushButton("⏹ Stop")
        self.stopBtn.setMaximumWidth(80)
        self.stopBtn.clicked.connect(self.parent.stopExecution)
        
        self.compileBtn = QPushButton("⚙ Compile")
        self.compileBtn.setMaximumWidth(100)
        self.compileBtn.clicked.connect(self.parent.showCompilerDialog)
        
        # Add buttons to layout
        self.quickAccessLayout.addWidget(self.runBtn)
        self.quickAccessLayout.addWidget(self.testBtn)
        self.quickAccessLayout.addWidget(self.debugBtn)
        self.quickAccessLayout.addWidget(self.stopBtn)
        self.quickAccessLayout.addWidget(self.compileBtn)
        self.quickAccessLayout.addStretch()
        
        # Create widget to hold layout
        quickAccessWidget = QWidget()
        quickAccessWidget.setLayout(self.quickAccessLayout)
        
        # Add widget to statusbar
        self.addPermanentWidget(quickAccessWidget)

class AdvancedFindReplaceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Advanced Find and Replace")
        self.setGeometry(300, 300, 600, 500)
        
        layout = QVBoxLayout()
        
        # Find
        findLayout = QVBoxLayout()
        findLayout.addWidget(QLabel("Find:"))
        self.findEdit = QLineEdit()
        findLayout.addWidget(self.findEdit)
        
        # Replace
        replaceLayout = QVBoxLayout()
        replaceLayout.addWidget(QLabel("Replace with:"))
        self.replaceEdit = QLineEdit()
        replaceLayout.addWidget(self.replaceEdit)
        
        # Options
        optionsGroup = QGroupBox("Options")
        optionsLayout = QVBoxLayout()
        
        self.caseSensitive = QCheckBox("Case sensitive")
        self.wholeWords = QCheckBox("Whole words only")
        self.regex = QCheckBox("Regular expressions")
        self.preserveCase = QCheckBox("Preserve case when replacing")
        
        optionsLayout.addWidget(self.caseSensitive)
        optionsLayout.addWidget(self.wholeWords)
        optionsLayout.addWidget(self.regex)
        optionsLayout.addWidget(self.preserveCase)
        optionsGroup.setLayout(optionsLayout)
        
        # Scope
        scopeGroup = QGroupBox("Scope")
        scopeLayout = QVBoxLayout()
        
        self.scopeSelection = QRadioButton("Selection only")
        self.scopeWholeDocument = QRadioButton("Whole document")
        self.scopeWholeDocument.setChecked(True)
        
        scopeLayout.addWidget(self.scopeSelection)
        scopeLayout.addWidget(self.scopeWholeDocument)
        scopeGroup.setLayout(scopeLayout)
        
        # Search results
        resultsGroup = QGroupBox("Search Results")
        resultsLayout = QVBoxLayout()
        
        self.resultsList = QListWidget()
        self.resultsList.itemDoubleClicked.connect(self.goToResult)
        resultsLayout.addWidget(self.resultsList)
        
        self.resultsCount = QLabel("Found: 0")
        resultsLayout.addWidget(self.resultsCount)
        
        resultsGroup.setLayout(resultsLayout)
        
        # Buttons
        btnLayout = QHBoxLayout()
        
        self.findAllBtn = QPushButton("Find all")
        self.replaceBtn = QPushButton("Replace")
        self.replaceAllBtn = QPushButton("Replace all")
        self.closeBtn = QPushButton("Close")
        
        btnLayout.addWidget(self.findAllBtn)
        btnLayout.addWidget(self.replaceBtn)
        btnLayout.addWidget(self.replaceAllBtn)
        btnLayout.addWidget(self.closeBtn)
        
        layout.addLayout(findLayout)
        layout.addLayout(replaceLayout)
        layout.addWidget(optionsGroup)
        layout.addWidget(scopeGroup)
        layout.addWidget(resultsGroup)
        layout.addLayout(btnLayout)
        
        self.setLayout(layout)
        
        # Connections
        self.findAllBtn.clicked.connect(self.findAll)
        self.replaceBtn.clicked.connect(self.replace)
        self.replaceAllBtn.clicked.connect(self.replaceAll)
        self.closeBtn.clicked.connect(self.accept)
        self.findEdit.textChanged.connect(self.clearResults)
        
        self.search_results = []
        
    def findAll(self):
        self.resultsList.clear()
        self.search_results = []
        
        search_text = self.findEdit.text()
        if not search_text:
            return
            
        document = self.parent.editor.document()
        cursor = QTextCursor(document)
        
        # Set search options
        options = QTextDocument.FindFlags()
        if self.caseSensitive.isChecked():
            options |= QTextDocument.FindCaseSensitively
        if self.wholeWords.isChecked():
            options |= QTextDocument.FindWholeWords
            
        # Determine scope
        if self.scopeSelection.isChecked():
            cursor = self.parent.editor.textCursor()
            if not cursor.hasSelection():
                QMessageBox.warning(self, "Error", "No text selected")
                return
        else:
            cursor.movePosition(QTextCursor.Start)
            
        count = 0
        while True:
            if self.regex.isChecked():
                # Search using regular expressions
                cursor = document.find(QRegExp(search_text), cursor, options)
            else:
                cursor = document.find(search_text, cursor, options)
                
            if cursor.isNull():
                break
                
            # Save result
            block = cursor.block()
            line_number = block.blockNumber() + 1
            line_text = block.text()
            start_pos = cursor.position() - cursor.block().position()
            end_pos = start_pos + len(search_text)
            
            # Highlight found text
            extra_selection = QTextEdit.ExtraSelection()
            extra_selection.cursor = cursor
            extra_selection.format.setBackground(QColor(255, 255, 0))
            
            self.search_results.append({
                'cursor': QTextCursor(cursor),
                'line': line_number,
                'text': line_text,
                'start_pos': start_pos,
                'end_pos': end_pos
            })
            
            # Add to results list
            preview = line_text[max(0, start_pos-20):end_pos+20].replace('\n', ' ')
            item = QListWidgetItem(f"Line {line_number}: ...{preview}...")
            self.resultsList.addItem(item)
            
            count += 1
            
        self.resultsCount.setText(f"Found: {count}")
        
    def goToResult(self, item):
        index = self.resultsList.row(item)
        if 0 <= index < len(self.search_results):
            result = self.search_results[index]
            self.parent.editor.setTextCursor(result['cursor'])
            self.parent.editor.setFocus()
            
    def replace(self):
        if not self.search_results:
            self.findAll()
            
        if self.search_results:
            # Replace first occurrence
            cursor = self.search_results[0]['cursor']
            cursor.beginEditBlock()
            
            if self.preserveCase.isChecked():
                # Preserve case
                original_text = cursor.selectedText()
                replacement = self.preserveCaseReplacement(original_text, self.replaceEdit.text())
                cursor.insertText(replacement)
            else:
                cursor.insertText(self.replaceEdit.text())
                
            cursor.endEditBlock()
            
            # Refresh results
            self.findAll()
            
    def replaceAll(self):
        if not self.search_results:
            self.findAll()
            
        if self.search_results:
            cursor = self.parent.editor.textCursor()
            cursor.beginEditBlock()
            
            for result in reversed(self.search_results):  # From end to not change positions
                result_cursor = result['cursor']
                result_cursor.joinPreviousEditBlock()
                
                if self.preserveCase.isChecked():
                    original_text = result_cursor.selectedText()
                    replacement = self.preserveCaseReplacement(original_text, self.replaceEdit.text())
                    result_cursor.insertText(replacement)
                else:
                    result_cursor.insertText(self.replaceEdit.text())
                    
            cursor.endEditBlock()
            
            self.resultsList.clear()
            self.resultsCount.setText("Found: 0")
            
    def preserveCaseReplacement(self, original, replacement):
        """Preserves original text case in replacement"""
        if original.isupper():
            return replacement.upper()
        elif original.islower():
            return replacement.lower()
        elif original.istitle():
            return replacement.title()
        else:
            return replacement
            
    def clearResults(self):
        self.resultsList.clear()
        self.resultsCount.setText("Found: 0")
        self.search_results = []

class CommentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("Add Comment")
        self.setGeometry(300, 300, 400, 300)
        
        layout = QVBoxLayout()
        
        # Comment type
        typeLayout = QHBoxLayout()
        typeLayout.addWidget(QLabel("Comment type:"))
        self.commentType = QComboBox()
        self.commentType.addItems(["Line comment (#)", "Block comment (''')", "Docstring (\"\"\")"])
        typeLayout.addWidget(self.commentType)
        layout.addLayout(typeLayout)
        
        # Comment text
        layout.addWidget(QLabel("Comment text:"))
        self.commentText = QTextEdit()
        layout.addWidget(self.commentText)
        
        # Preview
        layout.addWidget(QLabel("Preview:"))
        self.previewText = QTextEdit()
        self.previewText.setReadOnly(True)
        layout.addWidget(self.previewText)
        
        # Buttons
        btnLayout = QHBoxLayout()
        self.insertBtn = QPushButton("Insert comment")
        self.cancelBtn = QPushButton("Cancel")
        
        btnLayout.addWidget(self.insertBtn)
        btnLayout.addWidget(self.cancelBtn)
        
        layout.addLayout(btnLayout)
        
        self.setLayout(layout)
        
        # Connections
        self.commentType.currentIndexChanged.connect(self.updatePreview)
        self.commentText.textChanged.connect(self.updatePreview)
        self.insertBtn.clicked.connect(self.insertComment)
        self.cancelBtn.clicked.connect(self.reject)
        
        self.updatePreview()
        
    def updatePreview(self):
        comment_type = self.commentType.currentText()
        text = self.commentText.toPlainText()
        
        if "line" in comment_type.lower():
            lines = text.split('\n')
            preview = "\n".join(f"# {line}" for line in lines)
        elif "block" in comment_type.lower():
            preview = f"'''\n{text}\n'''"
        else:  # docstring
            preview = f'"""\n{text}\n"""'
            
        self.previewText.setPlainText(preview)
        
    def insertComment(self):
        preview = self.previewText.toPlainText()
        if preview:
            cursor = self.parent.editor.textCursor()
            
            # If there's selection, insert comment before selection
            if cursor.hasSelection():
                cursor.setPosition(cursor.selectionStart())
                
            cursor.insertText(preview + "\n")
            self.accept()

class EnhancedSyntaxChecker:
    @staticmethod
    def get_syntax_suggestions(error):
        """Returns fix suggestions for syntax errors"""
        suggestions = {
            "invalid syntax": "Check for missing brackets, quotes or commas",
            "unexpected indent": "Remove unexpected indentation or add missing colons",
            "expected ':'": "Add colon at the end of conditional/loop/function line",
            "unindent does not match any outer indentation level": "Make sure indentation is consistent (use only spaces or only tabs)",
            "eol while scanning string literal": "Add missing closing quote",
            "was never closed": "Add missing bracket/quote",
            "invalid character": "Remove invalid character (check special characters)",
            "assign to literal": "Cannot assign value to literal, use variable",
            "can't assign to function call": "Cannot assign value to function call",
        }
        
        for key, suggestion in suggestions.items():
            if key in str(error).lower():
                return suggestion
                
        return "Check syntax in Python documentation"
    
    @staticmethod
    def check_code_quality(code):
        """Checks code quality using pyflakes if available"""
        issues = []
        
        # Check syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error in line {e.lineno}: {e.msg}")
            return issues
        
        # Check code quality using pyflakes
        if PYFLAKES_AVAILABLE:
            try:
                # Create buffer to capture pyflakes output
                class Buffer:
                    def __init__(self):
                        self.lines = []
                    
                    def write(self, text):
                        if text.strip():
                            self.lines.append(text.strip())
                
                buffer = Buffer()
                
                # Run pyflakes
                pyflakes.api.check(code, "current_file.py", reporter=pyflakes.reporter.Reporter(buffer, buffer))
                
                # Add found issues
                issues.extend(buffer.lines)
            except Exception as e:
                issues.append(f"Error during code analysis: {e}")
        
        return issues

class CodeStructureTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setHeaderLabel("Code Structure")
        self.itemDoubleClicked.connect(self.onItemDoubleClicked)
        
    def updateStructure(self, code):
        """Updates code structure tree"""
        self.clear()
        
        try:
            tree = ast.parse(code)
            
            # Add main elements
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    self.addFunction(node)
                elif isinstance(node, ast.ClassDef):
                    self.addClass(node)
                elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    self.addImport(node)
                    
        except SyntaxError:
            # Ignore syntax errors during structure analysis
            pass
            
    def addFunction(self, func_node):
        """Adds function to tree"""
        # Use first line of function as position
        line_number = func_node.lineno
        func_item = QTreeWidgetItem([f"def {func_node.name}()"])
        func_item.setData(0, Qt.UserRole, line_number)  # Store line number
        self.addTopLevelItem(func_item)
        
        # Add arguments
        args = [arg.arg for arg in func_node.args.args]
        if args:
            args_item = QTreeWidgetItem([f"args: {', '.join(args)}"])
            func_item.addChild(args_item)
            
        # Add function body
        for node in func_node.body:
            if isinstance(node, ast.FunctionDef):
                self.addNestedFunction(node, func_item)
            elif isinstance(node, ast.ClassDef):
                self.addNestedClass(node, func_item)
                
    def addClass(self, class_node):
        """Adds class to tree"""
        line_number = class_node.lineno
        class_item = QTreeWidgetItem([f"class {class_node.name}"])
        class_item.setData(0, Qt.UserRole, line_number)  # Store line number
        self.addTopLevelItem(class_item)
        
        # Add class methods
        for node in class_node.body:
            if isinstance(node, ast.FunctionDef):
                self.addMethod(node, class_item)
                
    def addMethod(self, method_node, parent):
        """Adds method to class"""
        line_number = method_node.lineno
        method_item = QTreeWidgetItem([f"def {method_node.name}()"])
        method_item.setData(0, Qt.UserRole, line_number)  # Store line number
        parent.addChild(method_item)
        
    def addNestedFunction(self, func_node, parent):
        """Adds nested function"""
        line_number = func_node.lineno
        nested_item = QTreeWidgetItem([f"def {func_node.name}()"])
        nested_item.setData(0, Qt.UserRole, line_number)  # Store line number
        parent.addChild(nested_item)
        
    def addNestedClass(self, class_node, parent):
        """Adds nested class"""
        line_number = class_node.lineno
        nested_item = QTreeWidgetItem([f"class {class_node.name}"])
        nested_item.setData(0, Qt.UserRole, line_number)  # Store line number
        parent.addChild(nested_item)
        
    def addImport(self, import_node):
        """Adds import to tree"""
        line_number = import_node.lineno
        if isinstance(import_node, ast.Import):
            for alias in import_node.names:
                import_item = QTreeWidgetItem([f"import {alias.name}"])
                import_item.setData(0, Qt.UserRole, line_number)  # Store line number
                self.addTopLevelItem(import_item)
        else:  # ImportFrom
            module = import_node.module or ""
            names = ", ".join(alias.name for alias in import_node.names)
            import_item = QTreeWidgetItem([f"from {module} import {names}"])
            import_item.setData(0, Qt.UserRole, line_number)  # Store line number
            self.addTopLevelItem(import_item)
            
    def onItemDoubleClicked(self, item, column):
        """Goes to exact code line on double click"""
        line_number = item.data(0, Qt.UserRole)
        if line_number:
            cursor = self.parent.editor.textCursor()
            # Go to exact line (numbering from 0)
            block = self.parent.editor.document().findBlockByLineNumber(line_number - 1)
            if block.isValid():
                cursor.setPosition(block.position())
                # Move cursor to line start
                cursor.movePosition(QTextCursor.StartOfLine)
                self.parent.editor.setTextCursor(cursor)
                self.parent.editor.setFocus()
                # Highlight entire line
                self.parent.editor.highlightCurrentLine()

class DebuggerWindow(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Debugger", parent)
        self.parent = parent
        self.initUI()
        
    def initUI(self):
        self.setAllowedAreas(Qt.AllDockWidgetAreas)
        
        debug_widget = QWidget()
        layout = QVBoxLayout()
        
        # Debug controls
        controls_layout = QHBoxLayout()
        
        self.step_btn = QPushButton("Step Into")
        self.step_over_btn = QPushButton("Step Over")
        self.step_out_btn = QPushButton("Step Out")
        self.continue_btn = QPushButton("Continue")
        self.pause_btn = QPushButton("Pause")
        self.stop_btn = QPushButton("Stop")
        
        controls_layout.addWidget(self.step_btn)
        controls_layout.addWidget(self.step_over_btn)
        controls_layout.addWidget(self.step_out_btn)
        controls_layout.addWidget(self.continue_btn)
        controls_layout.addWidget(self.pause_btn)
        controls_layout.addWidget(self.stop_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Debug info area
        self.debug_tabs = QTabWidget()
        
        # Call stack
        self.call_stack = QListWidget()
        self.debug_tabs.addTab(self.call_stack, "Call Stack")
        
        # Variables
        self.variables_tree = QTreeWidget()
        self.variables_tree.setHeaderLabels(["Variable", "Value", "Type"])
        self.debug_tabs.addTab(self.variables_tree, "Variables")
        
        # Breakpoints
        self.breakpoints_list = QListWidget()
        self.debug_tabs.addTab(self.breakpoints_list, "Breakpoints")
        
        # Watches
        self.watches_list = QListWidget()
        self.debug_tabs.addTab(self.watches_list, "Watches")
        
        layout.addWidget(self.debug_tabs)
        
        # Current line highlight
        self.current_line_label = QLabel("Current line: -")
        layout.addWidget(self.current_line_label)
        
        debug_widget.setLayout(layout)
        self.setWidget(debug_widget)
        
        # Connections
        self.step_btn.clicked.connect(self.step_into)
        self.step_over_btn.clicked.connect(self.step_over)
        self.step_out_btn.clicked.connect(self.step_out)
        self.continue_btn.clicked.connect(self.continue_execution)
        self.pause_btn.clicked.connect(self.pause_execution)
        self.stop_btn.clicked.connect(self.stop_execution)
        
        # Track visibility for menu
        self.visibilityChanged.connect(self.onVisibilityChanged)
        
    def onVisibilityChanged(self, visible):
        """Update menu when visibility changes"""
        if hasattr(self.parent, 'window_menu'):
            for action in self.parent.window_menu.actions():
                if action.text() == "Debugger":
                    action.setChecked(visible)
                    break
        
    def step_into(self):
        if self.parent.execution_manager:
            self.parent.execution_manager.step_into()
            
    def step_over(self):
        if self.parent.execution_manager:
            self.parent.execution_manager.step_over()
            
    def step_out(self):
        if self.parent.execution_manager:
            self.parent.execution_manager.step_out()
            
    def continue_execution(self):
        if self.parent.execution_manager:
            self.parent.execution_manager.continue_execution()
            
    def pause_execution(self):
        if self.parent.execution_manager:
            self.parent.execution_manager.pause_execution()
            
    def stop_execution(self):
        if self.parent.execution_manager:
            self.parent.execution_manager.stop_execution()
            
    def update_call_stack(self, stack):
        """Update call stack display"""
        self.call_stack.clear()
        for frame in stack:
            self.call_stack.addItem(f"{frame.function} at line {frame.line}")
            
    def update_variables(self, variables):
        """Update variables display"""
        self.variables_tree.clear()
        for name, value in variables.items():
            item = QTreeWidgetItem([name, str(value), type(value).__name__])
            self.variables_tree.addTopLevelItem(item)
            
    def update_current_line(self, line_number):
        """Update current line display"""
        self.current_line_label.setText(f"Current line: {line_number}")

class EnhancedCodeEditor(CodeEditor):
    def __init__(self):
        super().__init__()
        self.code_structure_tree = None
        
    def setCodeStructureTree(self, tree):
        """Sets code structure tree"""
        self.code_structure_tree = tree
        
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        
        # Update structure tree after changes
        if self.code_structure_tree:
            QTimer.singleShot(100, lambda: self.code_structure_tree.updateStructure(self.toPlainText()))

class CompilerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("PyDDLE - Compile to Executable")
        self.setGeometry(300, 300, 500, 300)
        
        layout = QVBoxLayout()
        
        # Compiler selection
        compilerGroup = QGroupBox("Select Compiler")
        compilerLayout = QVBoxLayout()
        
        self.pyinstallerRadio = QRadioButton("PyInstaller")
        self.pyinstallerRadio.setChecked(True)
        
        compilerLayout.addWidget(self.pyinstallerRadio)
        compilerGroup.setLayout(compilerLayout)
        layout.addWidget(compilerGroup)
        
        # Compiler information
        infoGroup = QGroupBox("Information")
        infoLayout = QVBoxLayout()
        
        self.infoLabel = QLabel("PyInstaller: Creates standalone executables\n- Single file or directory distribution\n- Easy configuration\n- Supports Windows, macOS, Linux")
        infoLayout.addWidget(self.infoLabel)
        infoGroup.setLayout(infoLayout)
        layout.addWidget(infoGroup)
        
        # Buttons
        btnLayout = QHBoxLayout()
        self.continueBtn = QPushButton("Continue")
        self.cancelBtn = QPushButton("Cancel")
        
        btnLayout.addWidget(self.continueBtn)
        btnLayout.addWidget(self.cancelBtn)
        layout.addLayout(btnLayout)
        
        self.setLayout(layout)
        
        # Connections
        self.continueBtn.clicked.connect(self.continueToCompiler)
        self.cancelBtn.clicked.connect(self.reject)
        
    def continueToCompiler(self):
        """Goes to appropriate compiler dialog"""
        dialog = PyInstallerDialog(self.parent)
        self.accept()
        dialog.exec_()

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        
    def initUI(self):
        self.setWindowTitle("About PyDDLE")
        self.setGeometry(300, 300, 500, 400)
        self.setFixedSize(500, 400)
        
        layout = QVBoxLayout()
        
        # Application icon and title
        title_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(64, 64))
        title_layout.addWidget(title_icon)
        
        title_text = QLabel("PyDDLE - Python Development IDE")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_text.setFont(title_font)
        title_layout.addWidget(title_text)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Version information
        version_label = QLabel("Version: 1.0")
        version_font = QFont()
        version_font.setPointSize(12)
        version_label.setFont(version_font)
        layout.addWidget(version_label)
        
        # License information
        license_label = QLabel("License: GNU General Public License v3.0")
        license_label.setFont(version_font)
        layout.addWidget(license_label)
        
        # Author information
        author_label = QLabel("Author: m_goral@interia.pl")
        author_label.setFont(version_font)
        layout.addWidget(author_label)
        
        # Disclaimer
        disclaimer_label = QLabel(
            "Disclaimer:\n\n"
            "This application is provided 'as is' without warranty of any kind, "
            "either expressed or implied. The author does not take any responsibility "
            "for faulty or erroneous operation of the application nor for any "
            "consequences resulting from its use.\n\n"
            "Users assume all risk associated with the use of this software."
        )
        disclaimer_label.setWordWrap(True)
        disclaimer_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(disclaimer_label)
        
        # OK button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)

class PythonEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.debug_lines = []
        self.breakpoints = set()
        self.current_line = 0
        self.syntax_errors = {}
        self.code_formatter = CodeFormatter()
        self.execution_manager = CodeExecutionManager(self)
        self.enhanced_syntax_checker = EnhancedSyntaxChecker()
        self.debugger_window = None
        self.open_windows = []  # Lista otwartych okien
        self.initUI()
        
        # Immediately refresh code structure after initialization
        QTimer.singleShot(100, self.updateCodeStructure)
        
    def initUI(self):
        self.setWindowTitle('PyDDLE - Python Development IDE')
        self.setGeometry(100, 100, 1400, 900)
        
        # Set application style - Windows 11 inspired
        self.setStyleSheet("""
            QMainWindow {
                background-color: #FFFFFF;
                color: #000000;
            }
            QMenuBar {
                background-color: #FFFFFF;
                color: #000000;
                border-bottom: 1px solid #E1E1E1;
            }
            QMenuBar::item {
                padding: 5px 10px;
                background-color: transparent;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: #E1E1E1;
            }
            QMenu {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #E1E1E1;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 5px 20px 5px 20px;
            }
            QMenu::item:selected {
                background-color: #0078D4;
                color: #FFFFFF;
            }
            QToolBar {
                background-color: #F8F8F8;
                border: none;
                spacing: 3px;
                padding: 3px;
            }
            QToolButton {
                background-color: transparent;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 5px;
                color: #000000;
            }
            QToolButton:hover {
                background-color: #E1E1E1;
            }
            QToolButton:pressed {
                background-color: #CCCCCC;
            }
            QDockWidget {
                background-color: #FFFFFF;
                border: 1px solid #E1E1E1;
                color: #000000;
                border-radius: 4px;
            }
            QDockWidget::title {
                background-color: #F8F8F8;
                padding: 5px;
                text-align: center;
                color: #000000;
                border-bottom: 1px solid #E1E1E1;
            }
            QTabWidget::pane {
                border: 1px solid #E1E1E1;
                background-color: #FFFFFF;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #F8F8F8;
                padding: 8px 12px;
                margin-right: 2px;
                border: 1px solid #E1E1E1;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: #000000;
            }
            QTabBar::tab:selected {
                background-color: #FFFFFF;
                border-bottom: 1px solid #FFFFFF;
            }
            QStatusBar {
                background-color: #0078D4;
                color: white;
                border-top: 1px solid #E1E1E1;
            }
            QPlainTextEdit, QTextEdit {
                background-color: #FFFFFF;
                color: #000000;
                selection-background-color: #0078D4;
                border: 1px solid #E1E1E1;
                border-radius: 4px;
            }
            QTreeWidget {
                background-color: #FFFFFF;
                color: #000000;
                alternate-background-color: #F8F8F8;
                border: 1px solid #E1E1E1;
                border-radius: 4px;
            }
            QListWidget {
                background-color: #FFFFFF;
                color: #000000;
                alternate-background-color: #F8F8F8;
                border: 1px solid #E1E1E1;
                border-radius: 4px;
            }
            QGroupBox {
                color: #000000;
                border: 1px solid #E1E1E1;
                margin-top: 10px;
                padding-top: 10px;
                border-radius: 4px;
                background-color: #F8F8F8;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                background-color: #F8F8F8;
            }
            QLineEdit, QComboBox {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #E1E1E1;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton {
                background-color: #0078D4;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
            QPushButton:disabled {
                background-color: #CCCCCC;
                color: #666666;
            }
        """)

        # Main editor
        self.editor = EnhancedCodeEditor()
        self.setCentralWidget(self.editor)
        
        # Create menus
        self.createMenus()
        self.createToolbars()
        
        # Output console
        self.outputConsole = QTextEdit()
        self.outputConsole.setReadOnly(True)
        
        # Variable inspector
        self.variableInspector = VariableInspector()
        
        # Code structure tree
        self.codeStructureTree = CodeStructureTree(self)
        self.editor.setCodeStructureTree(self.codeStructureTree)
        
        # Side panel
        self.createSidePanel()
        
        # Status bar with buttons
        self.statusBar = StatusBarWithButtons(self)
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage('Ready')
        
        # Timer for UI updates
        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.updateUI)
        self.updateTimer.start(100)
        
        # Timer for syntax checking
        self.syntaxTimer = QTimer()
        self.syntaxTimer.timeout.connect(self.delayedSyntaxCheck)
        self.syntaxTimer.setSingleShot(True)
        
    def createToolbars(self):
        # Main toolbar
        mainToolbar = self.addToolBar('Main')
        mainToolbar.setMovable(False)
        mainToolbar.setIconSize(QSize(16, 16))
        
        newAction = QAction(QApplication.style().standardIcon(QStyle.SP_FileIcon), 'New', self)
        newAction.setShortcut('Ctrl+N')
        newAction.triggered.connect(self.newFile)
        mainToolbar.addAction(newAction)
        
        openAction = QAction(QApplication.style().standardIcon(QStyle.SP_DirOpenIcon), 'Open', self)
        openAction.setShortcut('Ctrl+O')
        openAction.triggered.connect(self.openFile)
        mainToolbar.addAction(openAction)
        
        saveAction = QAction(QApplication.style().standardIcon(QStyle.SP_DialogSaveButton), 'Save', self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.triggered.connect(self.saveFile)
        mainToolbar.addAction(saveAction)
        
        mainToolbar.addSeparator()
        
        runAction = QAction('▶ Run', self)
        runAction.setShortcut('F5')
        runAction.triggered.connect(self.runCode)
        mainToolbar.addAction(runAction)
        
        testAction = QAction('🧪 Test', self)
        testAction.setShortcut('F9')
        testAction.triggered.connect(self.testApplication)
        mainToolbar.addAction(testAction)
        
        debugAction = QAction('🐞 Debug', self)
        debugAction.setShortcut('F10')
        debugAction.triggered.connect(self.showDebugger)
        mainToolbar.addAction(debugAction)
        
        stopAction = QAction('⏹ Stop', self)
        stopAction.setShortcut('F7')
        stopAction.triggered.connect(self.stopExecution)
        mainToolbar.addAction(stopAction)
        
        mainToolbar.addSeparator()
        
        formatAction = QAction('🔧 Format', self)
        formatAction.setShortcut('Ctrl+Shift+F')
        formatAction.triggered.connect(self.formatCode)
        mainToolbar.addAction(formatAction)

    def createSidePanel(self):
        # Main dock widget
        mainDock = QDockWidget("Execution Panel", self)
        mainDock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Quick access buttons in side panel
        quickPanelLayout = QHBoxLayout()
        
        quickRunBtn = QPushButton("▶ Run")
        quickRunBtn.clicked.connect(self.runCode)
        quickPanelLayout.addWidget(quickRunBtn)
        
        quickTestBtn = QPushButton("🧪 Test")
        quickTestBtn.clicked.connect(self.testApplication)
        quickPanelLayout.addWidget(quickTestBtn)
        
        quickDebugBtn = QPushButton("🐞 Debug")
        quickDebugBtn.clicked.connect(self.showDebugger)
        quickPanelLayout.addWidget(quickDebugBtn)
        
        quickStopBtn = QPushButton("⏹ Stop")
        quickStopBtn.clicked.connect(self.stopExecution)
        quickPanelLayout.addWidget(quickStopBtn)
        
        layout.addLayout(quickPanelLayout)
        
        # Tabs
        tabs = QTabWidget()
        tabs.addTab(self.outputConsole, "📊 Console")
        tabs.addTab(self.variableInspector, "🔍 Variables")
        
        layout.addWidget(tabs)
        widget.setLayout(layout)
        mainDock.setWidget(widget)
        self.addDockWidget(Qt.RightDockWidgetArea, mainDock)
        
        # Dock widget for code structure
        structure_dock = QDockWidget("Code Structure", self)
        structure_dock.setWidget(self.codeStructureTree)
        structure_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.LeftDockWidgetArea, structure_dock)

    def createMenus(self):
        menubar = self.menuBar()
        
        # File Menu
        fileMenu = menubar.addMenu('&File')
        newAction = QAction('&New', self)
        newAction.setShortcut('Ctrl+N')
        newAction.triggered.connect(self.newFile)
        fileMenu.addAction(newAction)
        
        openAction = QAction('&Open...', self)
        openAction.setShortcut('Ctrl+O')
        openAction.triggered.connect(self.openFile)
        fileMenu.addAction(openAction)
        
        saveAction = QAction('&Save', self)
        saveAction.setShortcut('Ctrl+S')
        saveAction.triggered.connect(self.saveFile)
        fileMenu.addAction(saveAction)
        
        saveAsAction = QAction('Save &As...', self)
        saveAsAction.setShortcut('Ctrl+Shift+S')
        saveAsAction.triggered.connect(self.saveAsFile)
        fileMenu.addAction(saveAsAction)
        
        fileMenu.addSeparator()
        
        compileAction = QAction('Compile to &EXE...', self)
        compileAction.triggered.connect(self.showCompilerDialog)
        fileMenu.addAction(compileAction)
        
        fileMenu.addSeparator()
        
        exitAction = QAction('E&xit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.triggered.connect(self.close)
        fileMenu.addAction(exitAction)
        
        # Edit Menu
        editMenu = menubar.addMenu('&Edit')
        undoAction = QAction('&Undo', self)
        undoAction.setShortcut('Ctrl+Z')
        undoAction.triggered.connect(self.editor.undo)
        editMenu.addAction(undoAction)
        
        redoAction = QAction('&Redo', self)
        redoAction.setShortcut('Ctrl+Y')
        redoAction.triggered.connect(self.editor.redo)
        editMenu.addAction(redoAction)
        
        editMenu.addSeparator()
        cutAction = QAction('Cu&t', self)
        cutAction.setShortcut('Ctrl+X')
        cutAction.triggered.connect(self.editor.cut)
        editMenu.addAction(cutAction)
        
        copyAction = QAction('&Copy', self)
        copyAction.setShortcut('Ctrl+C')
        copyAction.triggered.connect(self.editor.copy)
        editMenu.addAction(copyAction)
        
        pasteAction = QAction('&Paste', self)
        pasteAction.setShortcut('Ctrl+V')
        pasteAction.triggered.connect(self.editor.paste)
        editMenu.addAction(pasteAction)
        
        selectAllAction = QAction('Select &All', self)
        selectAllAction.setShortcut('Ctrl+A')
        selectAllAction.triggered.connect(self.editor.selectAll)
        editMenu.addAction(selectAllAction)
        
        editMenu.addSeparator()
        
        # Formatting
        formatAction = QAction('&Format Code', self)
        formatAction.setShortcut('Ctrl+Shift+F')
        formatAction.triggered.connect(self.formatCode)
        editMenu.addAction(formatAction)
        
        commentAction = QAction('&Comment Selection', self)
        commentAction.setShortcut('Ctrl+/')
        commentAction.triggered.connect(self.commentCode)
        editMenu.addAction(commentAction)
        
        uncommentAction = QAction('&Uncomment Selection', self)
        uncommentAction.setShortcut('Ctrl+Shift+/')
        uncommentAction.triggered.connect(self.uncommentCode)
        editMenu.addAction(uncommentAction)
        
        editMenu.addSeparator()
        findAction = QAction('&Find...', self)
        findAction.setShortcut('Ctrl+F')
        findAction.triggered.connect(self.findText)
        editMenu.addAction(findAction)
        
        replaceAction = QAction('&Replace...', self)
        replaceAction.setShortcut('Ctrl+H')
        replaceAction.triggered.connect(self.replaceText)
        editMenu.addAction(replaceAction)
        
        advancedFindAction = QAction('&Advanced Find...', self)
        advancedFindAction.setShortcut('Ctrl+Shift+F')
        advancedFindAction.triggered.connect(self.showAdvancedFindReplace)
        editMenu.addAction(advancedFindAction)
        
        # View Menu
        viewMenu = menubar.addMenu('&View')
        zoomInAction = QAction('Zoom &In', self)
        zoomInAction.setShortcut('Ctrl++')
        zoomInAction.triggered.connect(self.zoomIn)
        viewMenu.addAction(zoomInAction)
        
        zoomOutAction = QAction('Zoom &Out', self)
        zoomOutAction.setShortcut('Ctrl+-')
        zoomOutAction.triggered.connect(self.zoomOut)
        viewMenu.addAction(zoomOutAction)
        
        resetZoomAction = QAction('&Reset Zoom', self)
        resetZoomAction.setShortcut('Ctrl+0')
        resetZoomAction.triggered.connect(self.resetZoom)
        viewMenu.addAction(resetZoomAction)
        
        # Window Menu
        self.window_menu = menubar.addMenu('&Window')
        
        # Debugger visibility action
        self.debugger_action = QAction('Debugger', self)
        self.debugger_action.setCheckable(True)
        self.debugger_action.triggered.connect(self.toggleDebugger)
        self.window_menu.addAction(self.debugger_action)
        
        # Code structure visibility action
        self.structure_action = QAction('Code Structure', self)
        self.structure_action.setCheckable(True)
        self.structure_action.setChecked(True)
        self.structure_action.triggered.connect(self.toggleCodeStructure)
        self.window_menu.addAction(self.structure_action)
        
        # Execution panel visibility action
        self.execution_action = QAction('Execution Panel', self)
        self.execution_action.setCheckable(True)
        self.execution_action.setChecked(True)
        self.execution_action.triggered.connect(self.toggleExecutionPanel)
        self.window_menu.addAction(self.execution_action)
        
        self.window_menu.addSeparator()
        
        cascadeAction = QAction('&Cascade', self)
        cascadeAction.triggered.connect(self.cascadeWindows)
        self.window_menu.addAction(cascadeAction)
        
        tileAction = QAction('&Tile', self)
        tileAction.triggered.connect(self.tileWindows)
        self.window_menu.addAction(tileAction)
        
        self.window_menu.addSeparator()
        
        nextAction = QAction('&Next', self)
        nextAction.setShortcut('Ctrl+F6')
        nextAction.triggered.connect(self.nextWindow)
        self.window_menu.addAction(nextAction)
        
        previousAction = QAction('&Previous', self)
        previousAction.setShortcut('Ctrl+Shift+F6')
        previousAction.triggered.connect(self.previousWindow)
        self.window_menu.addAction(previousAction)
        
        self.window_menu.addSeparator()
        
        closeAllAction = QAction('Close &All', self)
        closeAllAction.triggered.connect(self.closeAllWindows)
        self.window_menu.addAction(closeAllAction)
        
        # Run Menu
        runMenu = menubar.addMenu('&Run')
        runAction = QAction('&Run', self)
        runAction.setShortcut('F5')
        runAction.triggered.connect(self.runCode)
        runMenu.addAction(runAction)
        
        testAction = QAction('&Test', self)
        testAction.setShortcut('F9')
        testAction.triggered.connect(self.testApplication)
        runMenu.addAction(testAction)
        
        debugAction = QAction('&Debug', self)
        debugAction.setShortcut('F10')
        debugAction.triggered.connect(self.showDebugger)
        runMenu.addAction(debugAction)
        
        stopAction = QAction('&Stop', self)
        stopAction.setShortcut('F7')
        stopAction.triggered.connect(self.stopExecution)
        runMenu.addAction(stopAction)
        
        syntaxAction = QAction('Check &Syntax', self)
        syntaxAction.setShortcut('F8')
        syntaxAction.triggered.connect(self.checkSyntax)
        runMenu.addAction(syntaxAction)
        
        # Tools Menu
        toolsMenu = menubar.addMenu('&Tools')
        aiAction = QAction('&AI Suggestions', self)
        aiAction.setShortcut('Ctrl+I')
        aiAction.triggered.connect(self.showAISuggestion)
        toolsMenu.addAction(aiAction)
        
        toolsMenu.addSeparator()
        compileMenuAction = QAction('Compile to &EXE...', self)
        compileMenuAction.triggered.connect(self.showCompilerDialog)
        toolsMenu.addAction(compileMenuAction)
        
        # Help Menu
        helpMenu = menubar.addMenu('&Help')
        aboutAction = QAction('&About', self)
        aboutAction.triggered.connect(self.showAboutDialog)
        helpMenu.addAction(aboutAction)

    def toggleDebugger(self, checked):
        """Toggle debugger visibility"""
        if checked:
            self.showDebugger()
        else:
            self.hideDebugger()

    def toggleCodeStructure(self, checked):
        """Toggle code structure visibility"""
        for child in self.children():
            if isinstance(child, QDockWidget) and child.windowTitle() == "Code Structure":
                child.setVisible(checked)
                break

    def toggleExecutionPanel(self, checked):
        """Toggle execution panel visibility"""
        for child in self.children():
            if isinstance(child, QDockWidget) and child.windowTitle() == "Execution Panel":
                child.setVisible(checked)
                break

    def cascadeWindows(self):
        """Cascade all windows - improved version"""
        widgets = [w for w in QApplication.allWidgets() if w.isWindow() and w != self and w.isVisible()]
        if not widgets:
            return
            
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        x = screen_geometry.x()
        y = screen_geometry.y()
        width = screen_geometry.width() // 2
        height = screen_geometry.height() // 2
        
        for i, widget in enumerate(widgets):
            widget.setGeometry(x + i * 30, y + i * 30, width, height)
            widget.raise_()
            widget.activateWindow()

    def tileWindows(self):
        """Tile all windows - improved version"""
        widgets = [w for w in QApplication.allWidgets() if w.isWindow() and w != self and w.isVisible()]
        if not widgets:
            return
            
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        count = len(widgets)
        cols = int(count ** 0.5)
        rows = (count + cols - 1) // cols
        
        width = screen_geometry.width() // cols
        height = screen_geometry.height() // rows
        
        for i, widget in enumerate(widgets):
            row = i // cols
            col = i % cols
            widget.setGeometry(
                screen_geometry.x() + col * width,
                screen_geometry.y() + row * height,
                width,
                height
            )
            widget.raise_()
            widget.activateWindow()

    def nextWindow(self):
        """Activate next window - improved version"""
        widgets = [w for w in QApplication.allWidgets() if w.isWindow() and w != self and w.isVisible()]
        if not widgets:
            return
            
        current = QApplication.activeWindow()
        if current in widgets:
            index = widgets.index(current)
            next_index = (index + 1) % len(widgets)
            widgets[next_index].activateWindow()
        else:
            widgets[0].activateWindow()

    def previousWindow(self):
        """Activate previous window - improved version"""
        widgets = [w for w in QApplication.allWidgets() if w.isWindow() and w != self and w.isVisible()]
        if not widgets:
            return
            
        current = QApplication.activeWindow()
        if current in widgets:
            index = widgets.index(current)
            next_index = (index - 1) % len(widgets)
            widgets[next_index].activateWindow()
        else:
            widgets[-1].activateWindow()

    def closeAllWindows(self):
        """Close all windows except main - improved version"""
        for widget in QApplication.allWidgets():
            if widget.isWindow() and widget != self and widget.isVisible():
                widget.close()

    def newFile(self):
        self.editor.clear()
        self.current_file = None
        self.statusBar.showMessage('New file created')
        self.updateCodeStructure()

    def openFile(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Open Python File", "", "Python Files (*.py);;All Files (*)")
        if fileName:
            with open(fileName, 'r', encoding='utf-8') as file:
                self.editor.setPlainText(file.read())
            self.current_file = fileName
            self.statusBar.showMessage(f'Loaded: {fileName}')
            self.updateCodeStructure()

    def saveFile(self):
        if self.current_file:
            with open(self.current_file, 'w', encoding='utf-8') as file:
                file.write(self.editor.toPlainText())
            self.statusBar.showMessage(f'Saved: {self.current_file}')
        else:
            self.saveAsFile()

    def saveAsFile(self):
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File", "", "Python Files (*.py);;All Files (*)")
        if fileName:
            with open(fileName, 'w', encoding='utf-8') as file:
                file.write(self.editor.toPlainText())
            self.current_file = fileName
            self.statusBar.showMessage(f'Saved as: {fileName}')

    def findText(self):
        text, ok = QInputDialog.getText(self, 'Find', 'Enter text:')
        if ok and text:
            if not self.editor.find(text):
                self.statusBar.showMessage('Text not found')

    def replaceText(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Replace Text')
        dialog.setModal(True)
        layout = QVBoxLayout()
        
        findLayout = QHBoxLayout()
        findLayout.addWidget(QLabel('Find:'))
        self.findEdit = QLineEdit()
        findLayout.addWidget(self.findEdit)
        
        replaceLayout = QHBoxLayout()
        replaceLayout.addWidget(QLabel('Replace with:'))
        self.replaceEdit = QLineEdit()
        replaceLayout.addWidget(self.replaceEdit)
        
        btnLayout = QHBoxLayout()
        btnFind = QPushButton('Find Next')
        btnReplace = QPushButton('Replace')
        btnReplaceAll = QPushButton('Replace All')
        
        btnLayout.addWidget(btnFind)
        btnLayout.addWidget(btnReplace)
        btnLayout.addWidget(btnReplaceAll)
        
        layout.addLayout(findLayout)
        layout.addLayout(replaceLayout)
        layout.addLayout(btnLayout)
        dialog.setLayout(layout)
        
        def findNext():
            if not self.editor.find(self.findEdit.text()):
                self.statusBar.showMessage('Text not found')
                
        def replace():
            cursor = self.editor.textCursor()
            if cursor.hasSelection() and cursor.selectedText() == self.findEdit.text():
                cursor.insertText(self.replaceEdit.text())
            findNext()
            
        def replaceAll():
            text = self.editor.toPlainText()
            new_text = text.replace(self.findEdit.text(), self.replaceEdit.text())
            self.editor.setPlainText(new_text)
            
        btnFind.clicked.connect(findNext)
        btnReplace.clicked.connect(replace)
        btnReplaceAll.clicked.connect(replaceAll)
        dialog.exec_()

    def zoomIn(self):
        font = self.editor.font()
        font.setPointSize(font.pointSize() + 1)
        self.editor.setFont(font)

    def zoomOut(self):
        font = self.editor.font()
        if font.pointSize() > 6:
            font.setPointSize(font.pointSize() - 1)
            self.editor.setFont(font)

    def resetZoom(self):
        font = self.editor.font()
        font.setPointSize(10)
        self.editor.setFont(font)

    def formatCode(self):
        """Formats entire code or selection"""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            # Format only selection
            selected_text = cursor.selectedText()
            formatted_text = self.code_formatter.format_code(selected_text)
            cursor.insertText(formatted_text)
        else:
            # Format entire code
            code = self.editor.toPlainText()
            formatted_code = self.code_formatter.format_code(code)
            self.editor.setPlainText(formatted_code)
        
        self.statusBar.showMessage("Code formatted")
        self.updateCodeStructure()

    def commentCode(self):
        """Comments selected lines"""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            commented_text = self.code_formatter.comment_selection(selected_text)
            cursor.insertText(commented_text)
        else:
            # If no selection, comment current line
            cursor.select(QTextCursor.LineUnderCursor)
            selected_text = cursor.selectedText()
            commented_text = self.code_formatter.comment_selection(selected_text)
            cursor.insertText(commented_text)

    def uncommentCode(self):
        """Uncomments selected lines"""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            uncommented_text = self.code_formatter.uncomment_selection(selected_text)
            cursor.insertText(uncommented_text)
        else:
            # If no selection, uncomment current line
            cursor.select(QTextCursor.LineUnderCursor)
            selected_text = cursor.selectedText()
            uncommented_text = self.code_formatter.uncomment_selection(selected_text)
            cursor.insertText(uncommented_text)

    def showCommentDialog(self):
        """Shows comment dialog"""
        dialog = CommentDialog(self)
        dialog.exec_()

    def indentCode(self):
        """Increases indentation of selected lines"""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            indented_text = self.code_formatter.indent_selection(selected_text)
            cursor.insertText(indented_text)
        else:
            # If no selection, increase indentation of current line
            cursor.insertText("    ")

    def dedentCode(self):
        """Decreases indentation of selected lines"""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            selected_text = cursor.selectedText()
            dedented_text = self.code_formatter.dedent_selection(selected_text)
            cursor.insertText(dedented_text)
        else:
            # If no selection, decrease indentation of current line
            current_pos = cursor.position()
            cursor.select(QTextCursor.LineUnderCursor)
            line_text = cursor.selectedText()
            
            # Remove 4 spaces or 1 tab
            if line_text.startswith('    '):
                new_text = line_text[4:]
            elif line_text.startswith('\t'):
                new_text = line_text[1:]
            else:
                new_text = line_text
                
            cursor.insertText(new_text)
            # Restore cursor to correct position
            if len(new_text) < len(line_text):
                cursor.setPosition(current_pos - (len(line_text) - len(new_text)))
                self.editor.setTextCursor(cursor)

    def updateCodeStructure(self):
        """Updates code structure tree"""
        if hasattr(self, 'codeStructureTree'):
            self.codeStructureTree.updateStructure(self.editor.toPlainText())

    def scheduleSyntaxCheck(self):
        """Schedules syntax check after short delay"""
        self.syntaxTimer.stop()
        self.syntaxTimer.start(500)  # 500ms delay

    def delayedSyntaxCheck(self):
        """Performs syntax check after delay"""
        self.checkSyntax()
        self.updateCodeStructure()

    def checkSyntax(self):
        """Checks code syntax and marks errors"""
        code = self.editor.toPlainText()
        self.syntax_errors.clear()
        
        try:
            # Syntax checking using ast
            ast.parse(code)
            self.clearErrorMarks()
            self.statusBar.showMessage("Syntax correct")
            
            # Check code quality if pyflakes is available
            if PYFLAKES_AVAILABLE:
                issues = self.enhanced_syntax_checker.check_code_quality(code)
                if issues:
                    self.outputConsole.setPlainText("Code quality issues:\n" + "\n".join(issues))
                    self.statusBar.showMessage(f"Found {len(issues)} code quality issues")
                else:
                    self.outputConsole.setPlainText("Code correct - no quality issues")
                    
        except SyntaxError as e:
            line = e.lineno
            message = e.msg
            suggestion = self.enhanced_syntax_checker.get_syntax_suggestions(e)
            
            self.syntax_errors[line] = f"{message} | Suggestion: {suggestion}"
            self.highlightErrorLine(line, f"{message}\nSuggestion: {suggestion}")
            self.statusBar.showMessage(f"Syntax error in line {line}: {message} | {suggestion}")

    def highlightErrorLine(self, line, message):
        """Highlights line with syntax error"""
        # Create extra selection for error line
        extra_selections = []
        
        # Error line highlighting
        selection = QTextEdit.ExtraSelection()
        line_color = QColor(255, 200, 200)  # Light red
        selection.format.setBackground(line_color)
        selection.format.setProperty(QTextFormat.FullWidthSelection, True)
        
        # Set cursor on error line
        cursor = QTextCursor(self.editor.document().findBlockByLineNumber(line - 1))
        selection.cursor = cursor
        selection.cursor.clearSelection()
        
        extra_selections.append(selection)
        self.editor.setExtraSelections(extra_selections)
        
        # Add message to output
        self.outputConsole.setPlainText(f"SYNTAX ERROR in line {line}:\n{message}")

    def clearErrorMarks(self):
        """Clears syntax error marks"""
        self.editor.setExtraSelections([])

    def check_missing_imports(self):
        """Checks for missing imports and offers installation"""
        code = self.editor.toPlainText()
        missing_imports = ImportChecker.find_missing_imports(code)
        
        if missing_imports:
            dialog = ImportCheckDialog(missing_imports, self)
            result = dialog.exec_()
            return result == QDialog.Accepted
        return True

    def runCode(self):
        """Runs code without live preview"""
        # First check syntax
        self.checkSyntax()
        if self.syntax_errors:
            reply = QMessageBox.question(self, "Syntax Errors", 
                                       "Code contains syntax errors. Do you want to run it anyway?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
        
        # Check missing imports
        if not self.check_missing_imports():
            return
        
        code = self.editor.toPlainText()
        self.outputConsole.clear()
        
        # Save code to temporary file
        with open('temp_script.py', 'w', encoding='utf-8') as f:
            f.write(code)
        
        def execute():
            try:
                process = subprocess.Popen([sys.executable, '-u', 'temp_script.py'],
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE,
                                         text=True,
                                         bufsize=1,
                                         universal_newlines=True)
                
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        QMetaObject.invokeMethod(self.outputConsole, "append", 
                                              Qt.QueuedConnection, Q_ARG(str, output.strip()))
                
                # Check for any errors
                stderr_output = process.stderr.read()
                if stderr_output:
                    QMetaObject.invokeMethod(self.outputConsole, "append", 
                                          Qt.QueuedConnection, Q_ARG(str, f"ERROR: {stderr_output.strip()}"))
                
                process.wait()
                
            except Exception as e:
                QMetaObject.invokeMethod(self.outputConsole, "append", 
                                      Qt.QueuedConnection, Q_ARG(str, f"Execution error: {str(e)}"))
        
        # Run in separate thread
        thread = threading.Thread(target=execute)
        thread.daemon = True
        thread.start()
        
        self.statusBar.showMessage("Program running...")

    def testApplication(self):
        """Runs code with execution preview"""
        self.checkSyntax()
        if self.syntax_errors:
            reply = QMessageBox.question(self, "Syntax Errors", 
                                       "Code contains syntax errors. Do you want to run test anyway?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.No:
                return
                
        if not self.check_missing_imports():
            return
            
        code = self.editor.toPlainText()
        self.outputConsole.clear()
        
        # Run with execution preview
        self.execution_manager.execute_code(code, test_mode=True)
        self.statusBar.showMessage("Testing application...")

    def showDebugger(self):
        """Shows debugger window as dock widget"""
        if not self.debugger_window:
            self.debugger_window = DebuggerWindow(self)
            self.addDockWidget(Qt.BottomDockWidgetArea, self.debugger_window)
            self.debugger_action.setChecked(True)
        else:
            self.debugger_window.show()
            self.debugger_window.raise_()
            self.debugger_action.setChecked(True)

    def hideDebugger(self):
        """Hides debugger window"""
        if self.debugger_window:
            self.debugger_window.hide()
            self.debugger_action.setChecked(False)

    def stopExecution(self):
        """Stops currently executing code"""
        self.execution_manager.stop_execution()
        self.statusBar.showMessage("Execution stopped")

    def showAISuggestion(self):
        """Shows AI suggestions dialog"""
        dialog = AISuggestionDialog(self)
        dialog.exec_()

    def showAdvancedFindReplace(self):
        """Shows advanced find and replace dialog"""
        dialog = AdvancedFindReplaceDialog(self)
        dialog.exec_()

    def showCompilerDialog(self):
        """Shows compiler selection dialog"""
        dialog = CompilerDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # Continue in appropriate compiler dialog
            pass

    def showAboutDialog(self):
        """Shows about dialog"""
        dialog = AboutDialog(self)
        dialog.exec_()

    def updateUI(self):
        """Updates user interface"""
        # Update status bar
        line = self.editor.textCursor().blockNumber() + 1
        col = self.editor.textCursor().columnNumber() + 1
        self.statusBar.showMessage(f'Line: {line}, Column: {col} | Ready')

        # Check if code changed and schedule syntax check
        current_text = self.editor.toPlainText()
        if hasattr(self, 'last_checked_text') and self.last_checked_text != current_text:
            self.scheduleSyntaxCheck()
        self.last_checked_text = current_text

class CodeExecutionManager:
    def __init__(self, parent):
        self.parent = parent
        self.execution_process = None
        self.is_testing = False
        self.is_debugging = False
        self.current_line = 0
        self.code_lines = []
        self._stop_requested = False
        
    def execute_code(self, code, test_mode=False, debug_mode=False):
        """Executes Python code"""
        if self.execution_process and self.execution_process.poll() is None:
            self.stop_execution()
            
        self._stop_requested = False
        self.is_testing = test_mode
        self.is_debugging = debug_mode
        self.code_lines = code.split('\n')
        self.current_line = 0
        
        # Save code to temporary file
        with open('temp_execution.py', 'w', encoding='utf-8') as f:
            f.write(code)
            
        # Run program
        self.execution_process = subprocess.Popen(
            [sys.executable, 'temp_execution.py'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Start thread to monitor output
        thread = threading.Thread(target=self.monitor_execution, daemon=True)
        thread.start()
        
        if test_mode:
            # Start timer to track execution
            self.execution_timer = QTimer()
            self.execution_timer.timeout.connect(self.highlight_current_execution_line)
            self.execution_timer.start(100)  # Update every 100ms
        
    def monitor_execution(self):
        """Monitors program execution"""
        try:
            while (self.execution_process and 
                   self.execution_process.poll() is None and 
                   not self._stop_requested):
                
                # Read stdout
                stdout_line = self.execution_process.stdout.readline()
                if stdout_line and hasattr(self.parent, 'outputConsole'):
                    QMetaObject.invokeMethod(self.parent.outputConsole, "append", 
                                          Qt.QueuedConnection, Q_ARG(str, f"[OUT] {stdout_line.strip()}"))
                
                # Read stderr
                stderr_line = self.execution_process.stderr.readline()
                if stderr_line and hasattr(self.parent, 'outputConsole'):
                    QMetaObject.invokeMethod(self.parent.outputConsole, "append", 
                                          Qt.QueuedConnection, Q_ARG(str, f"[ERR] {stderr_line.strip()}"))
                    
                if self.is_testing:
                    self.current_line += 1
                    
        except Exception as e:
            print(f"Monitoring error: {e}")
        
        # Safe termination
        if not self._stop_requested:
            try:
                QMetaObject.invokeMethod(self.parent.outputConsole, "append",
                                      Qt.QueuedConnection, Q_ARG(str, "Execution completed"))
            except RuntimeError:
                pass  # Object might have been deleted
            
    def highlight_current_execution_line(self):
        """Highlights currently executing code line"""
        if self._stop_requested or not hasattr(self.parent, 'editor'):
            return
            
        if self.current_line < len(self.code_lines):
            # Scroll to current line
            cursor = self.parent.editor.textCursor()
            block = self.parent.editor.document().findBlockByLineNumber(self.current_line)
            if block.isValid():
                cursor.setPosition(block.position())
                self.parent.editor.setTextCursor(cursor)
                self.parent.editor.centerCursor()
                
            # Highlight line
            extra_selections = []
            selection = QTextEdit.ExtraSelection()
            line_color = QColor(230, 243, 255)  # Light blue
            selection.format.setBackground(line_color)
            selection.format.setProperty(QTextFormat.FullWidthSelection, True)
            
            cursor = QTextCursor(self.parent.editor.document().findBlockByLineNumber(self.current_line))
            selection.cursor = cursor
            selection.cursor.clearSelection()
            extra_selections.append(selection)
            
            self.parent.editor.setExtraSelections(extra_selections)
            
    def stop_execution(self):
        """Stops code execution"""
        self._stop_requested = True
        
        if self.execution_process:
            try:
                self.execution_process.terminate()
                # Wait a bit for closure
                for _ in range(10):
                    if self.execution_process.poll() is not None:
                        break
                    time.sleep(0.1)
                else:
                    self.execution_process.kill()
                self.execution_process = None
            except Exception as e:
                print(f"Error while stopping: {e}")
            
        if hasattr(self, 'execution_timer'):
            self.execution_timer.stop()
            
        self.is_testing = False

def main():
    app = QApplication(sys.argv)
    
    # Set application style
    app.setStyle('Fusion')
    
    # Set font
    font = QFont()
    font.setFamily("Segoe UI")
    font.setPointSize(10)
    app.setFont(font)
    
    editor = PythonEditor()
    editor.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()