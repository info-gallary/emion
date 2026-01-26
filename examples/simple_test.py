import sys
from PyQt5.QtWidgets import QApplication, QWidget, QLabel

def window():
    # 1. Create the application instance
    app = QApplication(sys.argv)
    
    # 2. Create a basic widget (window)
    widget = QWidget()
    
    # 3. Create a label and set its text
    textLabel = QLabel(widget)
    textLabel.setText("Hello World!")
    textLabel.move(110, 85) # Position the label within the window
    
    # 4. Configure the window
    widget.setGeometry(50, 50, 320, 200) # (x_pos, y_pos, width, height)
    widget.setWindowTitle("PyQt5 Simple App")
    
    # 5. Show the window
    widget.show()
    
    # 6. Start the application's event loop
    sys.exit(app.exec_())

if __name__ == '__main__':
    window()
