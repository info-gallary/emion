import sys
import traceback
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel, 
                             QComboBox, QGroupBox, QFormLayout, QSpinBox, 
                             QDoubleSpinBox)
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush
from PyQt5.QtCore import Qt, QPoint

from emion import Node

class NodeWidget(QWidget):
    def __init__(self, node_id, x, y):
        super().__init__()
        self.node_id = node_id
        self.x = x
        self.y = y
        self.radius = 30

    def paint(self, painter):
        painter.setBrush(QBrush(QColor(100, 150, 255)))
        painter.setPen(QPen(Qt.black, 2))
        painter.drawEllipse(QPoint(self.x, self.y), self.radius, self.radius)
        painter.drawText(QPoint(self.x - 5, self.y + 5), str(self.node_id))

class TopologyView(QWidget):
    def __init__(self, nodes):
        super().__init__()
        self.nodes = nodes # list of NodeWidget
        self.setMinimumSize(400, 300)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw connections (mock)
        painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
        # Draw all-to-all potential links
        for i in range(len(self.nodes)):
            for j in range(i+1, len(self.nodes)):
                n1 = self.nodes[i]
                n2 = self.nodes[j]
                painter.drawLine(n1.x, n1.y, n2.x, n2.y)

        # Draw Nodes
        for node in self.nodes:
            node.paint(painter)

class SimulationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ION-DTN Simulation (4 Nodes)")
        self.resize(1000, 700)

        self.ion_node = Node() # This simulation wrapper represents functionality available on *this* host.
                               # In a real sim, we might control remote nodes via RPC. 
                               # Here we assume we are configuring local ION stack to talk to others.

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left Panel: Controls
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)
        control_panel.setFixedWidth(300)
        
        # Status
        self.lbl_status = QLabel("Status: Detached")
        self.lbl_status.setStyleSheet("font-weight: bold; color: red;")
        control_layout.addWidget(self.lbl_status)

        # Attach/Detach
        self.btn_attach = QPushButton("Attach ION")
        self.btn_attach.clicked.connect(self.toggle_attach)
        control_layout.addWidget(self.btn_attach)

        # Linear Demo
        self.btn_linear = QPushButton("Setup Linear Demo (1-2-3-4)")
        self.btn_linear.clicked.connect(self.setup_linear_demo)
        control_layout.addWidget(self.btn_linear)

        # CGR Controls
        group_cgr = QGroupBox("Contact Graph Routing")
        layout_cgr = QFormLayout()
        
        self.cb_from_node = QComboBox()
        self.cb_to_node = QComboBox()
        for i in range(1, 5):
            self.cb_from_node.addItem(str(i))
            self.cb_to_node.addItem(str(i))
        self.cb_to_node.setCurrentIndex(1)
        
        layout_cgr.addRow("From Node:", self.cb_from_node)
        layout_cgr.addRow("To Node:", self.cb_to_node)
        
        self.spin_rate = QSpinBox()
        self.spin_rate.setRange(100, 10000000)
        self.spin_rate.setValue(100000)
        self.spin_rate.setSuffix(" B/s")
        layout_cgr.addRow("Rate:", self.spin_rate)
        
        self.btn_add_contact = QPushButton("Add Contact (+1h)")
        self.btn_add_contact.clicked.connect(self.add_contact)
        layout_cgr.addRow(self.btn_add_contact)

        group_cgr.setLayout(layout_cgr)
        control_layout.addWidget(group_cgr)

        # Bundle Controls
        group_bp = QGroupBox("Bundle Protocol")
        layout_bp = QFormLayout()
        
        self.cb_src = QComboBox()
        self.cb_dest = QComboBox()
        # Use valid endpoints from host.rc (1.1, 1.2)
        self.cb_src.addItem("ipn:1.1")
        self.cb_src.addItem("ipn:1.2")
        
        for i in range(1, 5):
             self.cb_dest.addItem(f"ipn:{i}.1")
        self.cb_dest.setCurrentIndex(1)

        layout_bp.addRow("Source:", self.cb_src)
        layout_bp.addRow("Dest:", self.cb_dest)
        
        self.btn_send = QPushButton("Send Bundle")
        self.btn_send.clicked.connect(self.send_bundle)
        layout_bp.addRow(self.btn_send)
        
        group_bp.setLayout(layout_bp)
        control_layout.addWidget(group_bp)

        control_layout.addStretch()

        # Center/Right: Visuals and Logs
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Visuals
        # 4 Nodes in a square
        nodes = [
            NodeWidget(1, 100, 100),
            NodeWidget(2, 300, 100),
            NodeWidget(3, 300, 300),
            NodeWidget(4, 100, 300)
        ]
        self.topo_view = TopologyView(nodes)
        right_layout.addWidget(self.topo_view, 2)

        # Logs
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        right_layout.addWidget(QLabel("Logs:"))
        right_layout.addWidget(self.log_area, 1)

        main_layout.addWidget(control_panel)
        main_layout.addWidget(right_panel)

        self.log("Simulation initialized. Please 'Attach ION' if you have a running ION node.")
        # Attempt auto-attach on startup to avoid button click handler issues
        # self.toggle_attach()

    def log(self, message):
        self.log_area.append(message)

    def toggle_attach(self):
        # Use a deferred call to move out of the button click stack frame potentially
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(10, self._do_attach_toggle)

    def _do_attach_toggle(self):
        try:
            if "Attach" in self.btn_attach.text():
                self.ion_node.attach()
                self.btn_attach.setText("Detach ION")
                self.lbl_status.setText("Status: Attached")
                self.lbl_status.setStyleSheet("font-weight: bold; color: green;")
                self.log("[SUCCESS] Attached to ION.")
            else:
                self.ion_node.detach()
                self.btn_attach.setText("Attach ION")
                self.lbl_status.setText("Status: Detached")
                self.lbl_status.setStyleSheet("font-weight: bold; color: red;")
                self.log("[SUCCESS] Detached from ION.")
        except Exception as e:
            self.log(f"[ERROR] Attach/Detach failed: {e}")
            self.log("Ensure you have started ION locally using the provided 'start_ion.sh' script.")

    def setup_linear_demo(self):
        try:
            self.log("Setting up Linear Topology (1-2-3-4)...")
            now = int(time.time())
            end = now + 3600
            rate = 1000000
            
            links = [(1, 2), (2, 3), (3, 4)]
            for (n1, n2) in links:
                self.ion_node.add_contact(1, now, end, n1, n2, rate)
                self.ion_node.add_contact(1, now, end, n2, n1, rate)
                self.ion_node.add_range(now, end, n1, n2, 1)
                self.ion_node.add_range(now, end, n2, n1, 1)
                self.log(f"[TOPO] Added {n1}<->{n2}")
            self.log("[SUCCESS] Linear demo setup complete.")
        except Exception as e:
            self.log(f"[ERROR] Setup failed: {e}")

    def add_contact(self):
        try:
            f = int(self.cb_from_node.currentText())
            t = int(self.cb_to_node.currentText())
            rate = self.spin_rate.value()
            
            # Add contact from now to +3600s
            now = int(time.time())
            self.log(f"Adding contact {f} -> {t} @ {rate} B/s...")
            self.ion_node.add_contact(
                region=1, 
                from_time=now, 
                to_time=now+3600, 
                from_node=f,
                to_node=t, 
                rate=rate
            )
            self.log("[SUCCESS] Contact added.")
            # Also add range for connectivity
            self.ion_node.add_range(
                 from_time=now, 
                 to_time=now+3600, 
                 from_node=f, 
                 to_node=t, 
                 owlt=1
            )
            self.log("[SUCCESS] Range added (Assumed 1s OWLT).")
        except Exception as e:
             self.log(f"[ERROR] Failed to add contact: {e}")

    def send_bundle(self):
        try:
            src = self.cb_src.currentText()
            dst = self.cb_dest.currentText()
            payload = b"Simulation Data Payload"
            
            self.log(f"Sending bundle {src} -> {dst}...")
            self.ion_node.send(src, dst, payload)
            self.log("[SUCCESS] Bundle sent.")
        except Exception as e:
             self.log(f"[ERROR] Failed to send bundle: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SimulationWindow()
    window.show()
    sys.exit(app.exec_())
