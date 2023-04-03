import sys
import asyncio
import serial_asyncio

from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox
from PyQt6.QtCore import QSettings
from PyQt6.uic import loadUi
from qasync import QEventLoop, asyncSlot
from serial.tools import list_ports
from serial.serialutil import SerialException

from main_window_ui import Ui_MainWindow
from settings_ui import Ui_Dialog as UI_Settings

class SerialProtocol(asyncio.Protocol):    
    def __init__(self, data_recieved_callback=None):
        self.data = str()
        self.data_ready = False
        self.connection_ready = False

    def connection_made(self, transport: serial_asyncio.SerialTransport) -> None:
        self.transport = transport
        self.pause_reading()  
        self.transport.write(b'\x03')
        self.connection_ready = True       

    def data_received(self, data: bytes):
        self.data += data.decode()
        if '\n' in self.data:
            self.data_ready = True
            self.pause_reading()
        
    def connection_lost(self, exc):
        raise exc
    
    def pause_reading(self) -> None:
        self.transport.pause_reading()
    
    def resume_reading(self) -> None:
        self.data_ready = False
        self.data = str()
        self.transport.resume_reading()

class Window(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None, loop=None):
        super().__init__(parent)        
        self.loadSettings()        
        self.setupUi(self)        
        self.lineEdit.setFocus()        
        self.connectSignalsSlots()
        self.loop = loop or asyncio.get_event_loop()
        self.serial_read()

    @asyncSlot()
    async def serial_read(self):
        try:
            self.s_transport, self.s_protocol = await serial_asyncio.create_serial_connection(self.loop, SerialProtocol, self.SERIALPORT, baudrate=9600)                        

            p = self.s_protocol
            t = self.s_transport

            while not p.connection_ready:
                await asyncio.sleep(0.5)                    

            t.write(f'ECHO OFF\r\n'.encode())
            t.write(f'MYCALL {self.MYCALL}\r\n'.encode())
            if not self.DIGIPETER:
                t.write(f'UNPROTO CHAT\r\n'.encode())
            else:
                t.write(f'UNPROTO CHAT via {self.DIGIPETER}\r\n'.encode())
            t.write(f'CONV\r\n'.encode())

            p.resume_reading()
            while True:
                await asyncio.sleep(1)
                if p.data_ready:
                    self.tbMonitor.append(p.data)
                    p.resume_reading()

        except SerialException as e:
            self.tbMonitor.append('Exception:' + str(e))

    def loadSettings(self):
        self.settings = QSettings("K1FSY", "PacketChat")
        self.MYCALL = self.settings.value("MYCALL") if self.settings.contains("MYCALL") else "NOCALL"
        self.DIGIPETER = self.settings.value("DIGIPETER") if self.settings.contains("DIGIPETER") else None
        self.SERIALPORT = self.settings.value("SERIALPORT") if self.settings.contains("SERIALPORT") else None

    def connectSignalsSlots(self):        
        self.lineEdit.returnPressed.connect(self.lineEditReturnPressed)
        self.actionSettings.triggered.connect(self.settingsClicked)
        self.actionExit.triggered.connect(self.exit)        

    def exit(self):
        self.close()        

    def lineEditReturnPressed(self):
        self.tbChat.append(f"<{self.MYCALL}> {self.lineEdit.text()}")
        self.s_transport.write(f"{self.lineEdit.text()}\r\n".encode())
        self.lineEdit.clear()        

    def settingsClicked(self):        
        self.settings_dialog = QDialog(self)
        self.UI_settings = UI_Settings()
        self.UI_settings.setupUi(self.settings_dialog)
        self.UI_settings.retranslateUi(self.settings_dialog)
        self.UI_settings.comboBox.addItems([x.device for x in list_ports.comports()])

        if hasattr(self, 'MYCALL'):
            self.UI_settings.leMycall.setText(self.MYCALL)
        if hasattr(self, 'DIGIPETER'):
            self.UI_settings.leDigipeter.setText(self.DIGIPETER)
        if hasattr(self, 'SERIALPORT'):
            self.UI_settings.comboBox.setCurrentIndex(self.UI_settings.comboBox.findText(self.SERIALPORT))
        
        self.settings_dialog.accepted.connect(self.settings_accepted)
        self.settings_dialog.show()        

    def settings_accepted(self):
        print("MYCALL:" + self.UI_settings.leMycall.text())
        print("COMBO:" + self.UI_settings.comboBox.currentText())
        self.MYCALL = self.UI_settings.leMycall.text()
        self.DIGIPETER = self.UI_settings.leDigipeter.text()
        self.SERIALPORT = self.UI_settings.comboBox.currentText()
        self.settings.setValue('MYCALL', self.MYCALL)
        self.settings.setValue('DIGIPETER', self.DIGIPETER)
        self.settings.setValue('SERIALPORT', self.SERIALPORT)

    def about(self):
        QMessageBox.about(
            self,
            "PacketChat<p>By K1FSY"
        )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    win = Window(loop=loop)
    win.show()

    app.aboutToQuit.connect(sys.exit)

    with loop:
        loop.run_forever()

    sys.exit(app.exec())