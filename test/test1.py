import numpy as np, h5py, pyqtgraph as pg
from PyQt6.QtCore import QThread, pyqtSignal
from pyqtgraph.Qt import QtCore, QtWidgets
# ---------- 全局启用 OpenGL ----------
pg.setConfigOptions(useOpenGL=True)   # 关键就在这一行

# ---------- 采集线程 ----------
class Capture(QThread):
    data_ready = pyqtSignal(np.ndarray)
    def run(self):
        rate = 1e6          # 1 MS/s 举例
        chunk = 10_000      # 每 10 ms 一帧
        while True:
            buf = np.random.normal(size=chunk).astype(np.float32)
            self.data_ready.emit(buf)

# ---------- GUI ----------
app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget(show=True)
plt = win.addPlot()
curve = plt.plot(pen='g')

# h5 = h5py.File('trace.h5', 'w')
# dset = h5.create_dataset('ch0', shape=(0,), maxshape=(None,), dtype='float32')

cap = Capture()
ptr = 0
def update(buf):
    global ptr
    curve.setData(buf)              # 10 k 点，GPU 直接画
    # new_len = dset.shape[0] + buf.size
    # dset.resize((new_len,))
    # dset[ptr:ptr+buf.size] = buf
    # ptr += buf.size
cap.data_ready.connect(update)
cap.start()

pg.exec()