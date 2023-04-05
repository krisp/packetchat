import sys
import asyncio
import re
import agwpe
import struct

from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow, QMessageBox
from PyQt6.QtCore import QSettings
from PyQt6.uic import loadUi
from qasync import QEventLoop, asyncSlot
from serial.tools import list_ports

from main_window_ui import Ui_MainWindow
from settings_ui import Ui_Dialog as UI_Settings

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
            self.client = agwpe.client()
            await self.client.connect()          

            await self.client.write_packet(agwpe.packet(datakind=b'X',callfrom=self.MYCALL))                  
            await self.client.write_packet(agwpe.packet(datakind=b'm'))
            await self.client.write_packet(agwpe.packet(datakind=b'G'))            
            pkt = await self.client.read_packet() # read the "X" packet response

            while True:
                pkt = await self.client.read_packet()
                if pkt.datakind in [b'U',b'S',b'I']:
                    pkt.data = pkt.data[:len(pkt.data)-2]
                    self.tbMonitor.append(pkt.data)
                if pkt.datakind == b'U' and pkt.callto == "CHAT":
                    print("data:" + pkt.data)
                    pkt.data = pkt.data[:len(pkt.data)-2]
                    m = re.search(r"Len=([0-9]+)",pkt.data)                    
                    if m:                        
                        l = int(m.group(1))
                        if pkt.callfrom != self.MYCALL:                                  
                            self.tbChat.append(f"<{pkt.callfrom}> {pkt.data[l*-1:]}")

        except Exception as e:
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
    
    @asyncSlot()
    async def lineEditReturnPressed(self):
        self.tbChat.append(f"<{self.MYCALL}> {self.lineEdit.text()}")

        txt = self.lineEdit.text().encode()
        if self.DIGIPETER:
            data = struct.pack(f"c10s{len(txt)}s",b'\x01',self.DIGIPETER.encode(),txt)
            pkt = agwpe.packet(agwpe_port=b'\x01',datakind=b'V',callfrom=self.MYCALL,callto="CHAT",data=data,datalen=len(data))        
            await self.client.write_packet(pkt)       
        else:
            pkt = agwpe.packet(agwpe_port=b'\x01',datakind=b'M',callfrom=self.MYCALL,callto="CHAT",data=txt,datalen=len(txt))        
            await self.client.write_packet(pkt)       
        
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