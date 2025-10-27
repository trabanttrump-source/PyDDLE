# PyDDLE - Python Development IDE

A comprehensive Python Integrated Development Environment built with PyQt5, featuring advanced code editing, debugging, and executable compilation capabilities.

## Features

### Code Editing
- **Syntax Highlighting**: Advanced Python syntax highlighting with multiple color themes
- **Line Numbers**: Interactive line number area with click navigation
- **Auto-Completion**: Intelligent code completion with Python keywords and functions
- **Code Folding**: Collapsible code blocks for better organization
- **Multiple Cursors**: Support for multiple cursor editing
- **Bracket Matching**: Automatic bracket completion and matching

### Advanced Editing Features
- **Code Formatting**: Support for autopep8 and Black formatting
- **Smart Indentation**: Automatic indentation management
- **Comment Management**: Easy comment/uncomment functionality
- **Advanced Find/Replace**: Regex support, case sensitivity, and scope selection
- **Code Structure Viewer**: Tree view of classes, functions, and imports

### Execution & Debugging
- **Code Execution**: Run Python scripts with real-time output
- **Integrated Debugger**: Step-by-step debugging with breakpoints
- **Variable Inspector**: Real-time variable monitoring during execution
- **Call Stack Viewer**: Track function calls and execution flow
- **Test Mode**: Special testing execution environment

### Compilation & Distribution
- **EXE Compilation**: Convert Python scripts to standalone executables using PyInstaller
- **Multiple Build Options**: One-file or one-directory distribution
- **Icon Support**: Custom application icons
- **Dependency Management**: Automatic handling of hidden imports
- **Additional Files**: Include data files and binary dependencies

### AI Integration
- **Code Suggestions**: AI-powered code generation and completion
- **Smart Prompts**: Context-aware coding assistance
- **Code Improvement**: AI-driven code optimization suggestions

### Project Management
- **Multi-Window Support**: Cascade, tile, and manage multiple windows
- **File Management**: New, open, save, and save as functionality
- **Project Navigation**: Easy navigation between different code sections
- **Import Management**: Automatic detection and installation of missing packages

## Installation

### Prerequisites
- Python 3.7 or higher
- PyQt5
- Required Python packages (automatically handled)

### Required Packages
```bash
pip install PyQt5 pyqtgraph networkx matplotlib requests psutil
```

### Optional Packages for Enhanced Features
```bash
pip install autopep8 black pyflakes
```

### Running the Application
```bash
python PyDDLE v1.0.py
```

## Usage

### Basic Code Editing
1. **Creating New Files**: Use `File → New` or `Ctrl+N`
2. **Opening Files**: Use `File → Open` or `Ctrl+O`
3. **Saving Files**: Use `File → Save` or `Ctrl+S`

### Code Execution
- **Run Code**: Press `F5` or click the "Run" button
- **Test Mode**: Press `F9` for testing execution
- **Debug Mode**: Press `F10` to start debugging

### Code Formatting
- **Auto-format**: `Ctrl+Shift+F` for automatic code formatting
- **Comment/Uncomment**: `Ctrl+/` and `Ctrl+Shift+/`
- **Indentation**: Use Tab and Shift+Tab for indentation control

### Compilation to EXE
1. **Access Compiler**: `Tools → Compile to EXE`
2. **Configure Settings**: Select build options, icons, and dependencies
3. **Build**: Click "Convert to EXE" to create standalone executable

### Debugging Features
- **Step Through Code**: Use step into, step over, and step out buttons
- **Breakpoints**: Set breakpoints by clicking line numbers
- **Variable Inspection**: Monitor variables in real-time during execution
- **Call Stack**: View the current execution stack

## Project Structure

```
PyDDLE/
├── Main Editor Window
├── Code Structure Panel
├── Execution Panel
├── Debugger Window
└── Compiler Interface
```

## Key Components

### Editor Features
- **EnhancedCodeEditor**: Advanced text editor with syntax highlighting
- **PythonHighlighter**: Custom Python syntax highlighter
- **LineNumberArea**: Interactive line number display

### Execution Management
- **CodeExecutionManager**: Handles code execution and debugging
- **VariableInspector**: Displays current variables and their values
- **OutputConsole**: Shows program output and error messages

### Compilation System
- **PyInstallerDialog**: Comprehensive EXE compilation interface
- **CompilationProgressDialog**: Real-time compilation progress monitoring
- **ImportChecker**: Verifies and installs required dependencies

### AI Integration
- **AISuggestionDialog**: AI-powered code generation interface
- **Smart completion**: Context-aware code suggestions

## System Requirements

### Minimum Requirements
- **OS**: Windows 10/11, macOS 10.14+, or Linux with X11
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 500MB free space
- **Python**: 3.7 or higher

### Recommended Requirements
- **RAM**: 16GB for large projects
- **CPU**: Multi-core processor
- **GPU**: Hardware acceleration support

## Troubleshooting

### Common Issues

1. **Missing Dependencies**
   - Use the built-in import checker to install missing packages
   - Run `pip install -r requirements.txt` manually if needed

2. **Compilation Errors**
   - Ensure PyInstaller is installed: `pip install pyinstaller`
   - Check that all required imports are properly declared
   - Verify file paths and working directory settings

3. **Debugging Not Working**
   - Ensure the code has no syntax errors before debugging
   - Check that breakpoints are set on executable lines
   - Verify variable scope in the inspector

### Performance Tips

- Close unused editor windows to free memory
- Use code folding for large files
- Enable only necessary panels in the view menu
- Regular code formatting improves readability and performance

## License

This project is licensed under the GNU General Public License v3.0. See the LICENSE file for details.

## Support

For issues and feature requests, please contact: m_goral@interia.pl

## Disclaimer

This application is provided 'as is' without warranty of any kind, either expressed or implied. The author does not take any responsibility for faulty or erroneous operation of the application nor for any consequences resulting from its use.

Users assume all risk associated with the use of this software.

---

**PyDDLE** - Empowering Python Development with Advanced IDE Features
