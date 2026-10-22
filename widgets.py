from PySide6 import QtGui, QtCore, QtWidgets
from datetime import datetime

import webbrowser, os, math, tempfile
import utils, SVG, text_editor, models

# https://doc.qt.io/qtforpython-6/examples/example_widgets_layouts_flowlayout.html
class FlowLayout(QtWidgets.QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)

        if parent is not None:
            self.setContentsMargins(QtCore.QMargins(0, 0, 0, 0))

        self._item_list = []

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]

        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)

        return None

    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        height = self._do_layout(QtCore.QRect(0, 0, width, 0), True)
        return height

    def setGeometry(self, rect):
        super(FlowLayout, self).setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QtCore.QSize()

        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())

        size += QtCore.QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._item_list:
            style = item.widget().style()
            layout_spacing_x = style.layoutSpacing(
                QtWidgets.QSizePolicy.ControlType.PushButton, QtWidgets.QSizePolicy.ControlType.PushButton,
                QtCore.Qt.Orientation.Horizontal
            )
            layout_spacing_y = style.layoutSpacing(
                QtWidgets.QSizePolicy.ControlType.PushButton, QtWidgets.QSizePolicy.ControlType.PushButton,
                QtCore.Qt.Orientation.Vertical
            )
            space_x = spacing + layout_spacing_x
            space_y = spacing + layout_spacing_y
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + margins.bottom()

# credit: 
# (eyllanesc) https://stackoverflow.com/questions/48441863/is-there-a-way-to-implement-a-circular-waiting-indicator-using-pyqt
# (snowwlex) https://github.com/snowwlex/QtWaitingSpinner
 
class QtWaitingSpinner(QtWidgets.QWidget):
    mColor = QtGui.QColor(QtCore.Qt.GlobalColor.gray)
    mRoundness = 100.0
    mMinimumTrailOpacity = 31.4159265358979323846
    mTrailFadePercentage = 50.0
    mRevolutionsPerSecond = 1.57079632679489661923
    mNumberOfLines = 20
    mLineLength = 4 # default 10
    mLineWidth = 2
    mInnerRadius = 4 # default 20
    mCurrentCounter = 0
    mIsSpinning = False

    def __init__(self, centerOnParent=True, disableParentWhenSpinning=True, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        self.mCenterOnParent = centerOnParent
        self.mDisableParentWhenSpinning = disableParentWhenSpinning
        self.initialize()

    def initialize(self):
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.updateSize()
        self.updateTimer()
        self.hide()

    def rotate(self):
        self.mCurrentCounter += 1
        if self.mCurrentCounter > self.numberOfLines():
            self.mCurrentCounter = 0
        self.update()

    def updateSize(self):
        size = (self.mInnerRadius + self.mLineLength) * 2
        self.setFixedSize(size, size)

    def updateTimer(self):
        self.timer.setInterval(1000 / (self.mNumberOfLines * self.mRevolutionsPerSecond))

    def updatePosition(self):
        if self.parentWidget() and self.mCenterOnParent:
            self.move(self.parentWidget().width() / 2 - self.width() / 2,
                      self.parentWidget().height() / 2 - self.height() / 2)

    def lineCountDistanceFromPrimary(self, current, primary, totalNrOfLines):
        distance = primary - current
        if distance < 0:
            distance += totalNrOfLines
        return distance

    def currentLineColor(self, countDistance, totalNrOfLines, trailFadePerc, minOpacity, color):
        if countDistance == 0:
            return color

        minAlphaF = minOpacity / 100.0

        distanceThreshold = math.ceil((totalNrOfLines - 1) * trailFadePerc / 100.0)
        if countDistance > distanceThreshold:
            color.setAlphaF(minAlphaF)

        else:
            alphaDiff = self.mColor.alphaF() - minAlphaF
            gradient = alphaDiff / distanceThreshold + 1.0
            resultAlpha = color.alphaF() - gradient * countDistance
            resultAlpha = min(1.0, max(0.0, resultAlpha))
            color.setAlphaF(resultAlpha)
        return color

    def paintEvent(self, event):
        self.updatePosition()
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(), QtCore.Qt.GlobalColor.transparent)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        if self.mCurrentCounter > self.mNumberOfLines:
            self.mCurrentCounter = 0
        painter.setPen(QtCore.Qt.NoPen)

        for i in range(self.mNumberOfLines):
            painter.save()
            painter.translate(self.mInnerRadius + self.mLineLength,
                              self.mInnerRadius + self.mLineLength)
            rotateAngle = 360.0 * i / self.mNumberOfLines
            painter.rotate(rotateAngle)
            painter.translate(self.mInnerRadius, 0)
            distance = self.lineCountDistanceFromPrimary(i, self.mCurrentCounter,
                                                         self.mNumberOfLines)
            color = self.currentLineColor(distance, self.mNumberOfLines,
                                          self.mTrailFadePercentage, self.mMinimumTrailOpacity, self.mColor)
            painter.setBrush(color)
            painter.drawRoundedRect(QtCore.QRect(0, -self.mLineWidth // 2, self.mLineLength, self.mLineLength),
                                    self.mRoundness, self.mRoundness, QtCore.Qt.RelativeSize)
            painter.restore()

    def start(self):
        self.updatePosition()
        self.mIsSpinning = True
        self.show()

        if self.parentWidget() and self.mDisableParentWhenSpinning:
            self.parentWidget().setEnabled(False)

        if not self.timer.isActive():
            self.timer.start()
            self.mCurrentCounter = 0

    def stop(self):
        self.mIsSpinning = False
        self.hide()

        if self.parentWidget() and self.mDisableParentWhenSpinning:
            self.parentWidget().setEnabled(True)

        if self.timer.isActive():
            self.timer.stop()
            self.mCurrentCounter = 0

    def setNumberOfLines(self, lines):
        self.mNumberOfLines = lines
        self.updateTimer()

    def setLineLength(self, length):
        self.mLineLength = length
        self.updateSize()

    def setLineWidth(self, width):
        self.mLineWidth = width
        self.updateSize()

    def setInnerRadius(self, radius):
        self.mInnerRadius = radius
        self.updateSize()

    def color(self):
        return self.mColor

    def roundness(self):
        return self.mRoundness

    def minimumTrailOpacity(self):
        return self.mMinimumTrailOpacity

    def trailFadePercentage(self):
        return self.mTrailFadePercentage

    def revolutionsPersSecond(self):
        return self.mRevolutionsPerSecond

    def numberOfLines(self):
        return self.mNumberOfLines

    def lineLength(self):
        return self.mLineLength

    def lineWidth(self):
        return self.mLineWidth

    def innerRadius(self):
        return self.mInnerRadius

    def isSpinning(self):
        return self.mIsSpinning

    def setRoundness(self, roundness):
        self.mRoundness = min(0.0, max(100, roundness))

    def setColor(self, color):
        self.mColor = color

    def setRevolutionsPerSecond(self, revolutionsPerSecond):
        self.mRevolutionsPerSecond = revolutionsPerSecond
        self.updateTimer()

    def setTrailFadePercentage(self, trail):
        self.mTrailFadePercentage = trail

    def setMinimumTrailOpacity(self, minimumTrailOpacity):
        self.mMinimumTrailOpacity = minimumTrailOpacity

# -------------------------------------------------- Common Widgets --------------------------------------------------

class ElideLabel(QtWidgets.QLabel):
    def __init__(self, text="", parent=None):
        super(ElideLabel, self).__init__(text, parent)
        self.elide_mode = QtCore.Qt.ElideNone

    def set_elide_mode(self, mode):
        self.elide_mode = mode
        self.update()

    def minimumSizeHint(self):
        if self.elide_mode != QtCore.Qt.ElideNone:
            font_metrics = self.fontMetrics()
            return QtCore.QSize(font_metrics.horizontalAdvance("..."), font_metrics.height())   # width was deprecated and changed to horizontalAdvance: it returned how far the cursor should advance horizontally after the text
        return super(ElideLabel, self).minimumSizeHint()

    def paintEvent(self, event=None):
        if self.elide_mode == QtCore.Qt.ElideNone:
            super(ElideLabel, self).paintEvent(event)
        else:
            painter = QtGui.QPainter(self)
            rect = self.contentsRect()
            elided_text = self.fontMetrics().elidedText(self.text(), self.elide_mode, rect.width()) 
            painter.drawText(rect, self.alignment(), elided_text)

class GraphicLabel(QtWidgets.QLabel):
    """simple class to display image in label, also is aware of dpr of the screen and handle screen dpr change event"""
    onScreenChanged = QtCore.Signal()
    def __init__(self, image=None, size=(32,32), edge_radius=0, parent=None):
        super(GraphicLabel, self).__init__(parent)

        self._image = image if isinstance(image, QtGui.QImage) else QtGui.QImage()
        self._image_size = size
        self.item_pixmap = QtGui.QPixmap()
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.edge_radius = edge_radius
        self._connected_window = None   # store the os window reference for connection to tracking the signal when screen changed

        self.initUI()

    def initUI(self):
        if self._image.isNull():
            return
        self._setup_pixmap(self._image, self._image_size)

    def showEvent(self, event):
        """triggered when widget is being displayed and connect screenChanged signal, when label is inside layout/window it will success return windowHandle"""
        super().showEvent(event)
        utils.setup_screenChanged_connection(self, self._connected_window, self._on_screen_changed)

    def change_icon(self, image, size=None):
        if not isinstance(image, QtGui.QImage): 
            raise ValueError("GraphicLabel only accept QImage as icon")
        if not image.isNull():
            self._image = image
        if size: 
            self._image_size = size

        self._setup_pixmap(self._image, self._image_size)

    def _setup_pixmap(self, image, size):
        """
        preparing the correct pixmap resolution/size by accounting for screen dpr       
        """
        _displayed_image = image

        current_dpr = self.devicePixelRatioF()
        converted_width = current_dpr * size[0]
        converted_height = current_dpr * size[1]
        
        _displayed_image = utils.scale_image(_displayed_image, (converted_width, converted_height))
        self.item_pixmap.convertFromImage(_displayed_image)
        self.item_pixmap.setDevicePixelRatio(current_dpr)  
        self.setPixmap(self.item_pixmap)

    def _on_screen_changed(self, event):
        if self._image.isNull():
            return
        self._setup_pixmap(self._image, self._image_size)
        self.onScreenChanged.emit()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        if self.edge_radius > 0:
            path = QtGui.QPainterPath()
            path.addRoundedRect(self.rect(), self.edge_radius, self.edge_radius)
            painter.setClipPath(path)
            painter.drawPixmap(self.rect(), self.item_pixmap) 
        else:
            super().paintEvent(event)

class GraphicButton(GraphicLabel):
    def __init__(self, image="", callback=None, color=QtGui.QColor('silver'), strength=0.25, size=(32,32), parent=None):
        self.callback = []
        if callback: self.callback.append(callback)
        self.color = color
        self.strength = strength
        
        super(GraphicButton, self).__init__(image=image, size=size, parent=parent)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)   # PySide2 need to specify this since graphic effect applied to transparent background
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)

    def initUI(self):
        super(GraphicButton, self).initUI()

        # set highlight mouse hover effect
        self.highlight = QtWidgets.QGraphicsColorizeEffect()
        self.highlight.setColor(self.color)
        self.highlight.setStrength(0.0)
        self.setGraphicsEffect(self.highlight)

    def mouseReleaseEvent(self, event):
        super(GraphicButton,self).mouseReleaseEvent(event)
        if not self.rect().contains(event.pos()): 
            return
        if event.button() == QtCore.Qt.LeftButton:
            for callback in self.callback: 
                try:
                    callback(event)
                except TypeError:
                    callback()
            event.accept()

    def enterEvent(self, event):
        super(GraphicButton,self).enterEvent(event)
        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.highlight.setStrength(self.strength)
        self.update()
        self.onEnter()

    def leaveEvent(self, event):
        super(GraphicButton,self).leaveEvent(event)
        self.highlight.setStrength(0.0)
        self.update()
        self.onLeave()

    def onEnter(self):
        """virtual function to override"""

    def onLeave(self):
        """virtual function to override"""

class ModernComboBox(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        self._hovered = False

        self._background_brush = QtGui.QBrush(QtGui.QColor("#e4e8f0"))
        self._arrow_pen = QtGui.QPen(QtGui.QColor("#768090"))
        self._arrow_pen.setWidth(2)
        self._left_pad = 3
        super().__init__(parent)

    def enterEvent(self, event):
        self._hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        super().leaveEvent(event)

    def paintEvent(self, e):
        option = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(option)

        option_rect = option.rect
        sub_ctrl_rect = self.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_ComboBox, option, QtWidgets.QStyle.SubControl.SC_ComboBoxArrow)
        edit_rect = self.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_ComboBox, option, QtWidgets.QStyle.SubControl.SC_ComboBoxEditField).adjusted(self._left_pad,0,0,0)    # Cheating a bit with adding manually padding on left side

        text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)

        # custom painting
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        font_metrics = QtGui.QFontMetrics(painter.font())

        # draw combo box main body
        if self._hovered and self.count():
            painter.setBrush(self._background_brush.color().lighter(105))
        else:
            painter.setBrush(self._background_brush)
        painter.setPen(self._background_brush.color().darker(200))
        painter.drawRoundedRect(option_rect, 5, 5)

        # draw text
        painter.setPen(text_color)
        elided_text = font_metrics.elidedText(self.currentText(), QtCore.Qt.TextElideMode.ElideRight, edit_rect.width())
        painter.drawText(edit_rect, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, elided_text)

        # draw arrow down
        painter.setPen(self._arrow_pen)
        width, height = sub_ctrl_rect.width(), sub_ctrl_rect.height()
        x = sub_ctrl_rect.x()
        
        painter.drawLine(x+width*0.25, height*0.4, x+width/2, height*0.6)
        painter.drawLine(x+width/2, height*0.6, x+width-width*0.25, height*0.4)

class StaticDisplayComboBox(QtWidgets.QComboBox):
    """Combo box with static label, modifiable padding and icon"""
    def __init__(self, display_text, icon:QtGui.QPixmap =None, parent=None):
        self._left_pad, self._top_pad, self._right_pad, self._bottom_pad = 10, 10, 10, 10
        self._icon_space = 5    # spacing from icon and text
        self._display_text = display_text
        self._icon = icon
        super().__init__(parent)

    def setPadding(self, left:int, top:int, right:int, bottom:int):
        self._left_pad, self._top_pad, self._right_pad, self._bottom_pad = left, top, right, bottom
        self.update()

    def showPopup(self):
        # credit: JonB (https://forum.qt.io/topic/105012/qcombobox-specify-width-less-than-content/2)
        
        # we only need to do work for this when the combo has had a maximum width specified
        maxWidth = self.maximumWidth()
        if maxWidth and self.count() and maxWidth < 16777215: # see https://doc.qt.io/qt-5/qwidget.html#maximumWidth-prop for the 16777215 value
            self.setPopupMinimumWidthForItems()

        super().showPopup()

    def setPopupMinimumWidthForItems(self):
        # we like the popup to always show the full contents, under Linux/GNOME popups always do this, but under Windows they get truncated/ellipsised
        # here we calculate the maximum width among the items and set QComboBox.view() to accomodate this, which makes items show full width under Windows
        view = self.view()
        fm = self.fontMetrics()
        maxWidth = max([fm.horizontalAdvance(self.itemText(i)) for i in range(self.count())]) + self.view().verticalScrollBar().sizeHint().width() + 10 # take consideration of scrollBar and extra 10 because i cant figure out what else cause truncation
        if maxWidth:
            view.setMinimumWidth(maxWidth)

    def sizeHint(self):
        # get arrow/sub ctrl width
        option = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(option)
        sub_ctrl_rect = self.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_ComboBox, option, QtWidgets.QStyle.SubControl.SC_ComboBoxArrow)

        text_size = self.fontMetrics().size(QtCore.Qt.TextFlag.TextSingleLine, self._display_text)
        new_height = text_size.height() + self._top_pad + self._bottom_pad
        new_width = self._left_pad + text_size.width() + self._right_pad + sub_ctrl_rect.width()
        if self._icon and isinstance(self._icon, QtGui.QPixmap):
            new_width += text_size.height() + self._icon_space  # add text_size.height because were using it in paintevent for icon square size
        
        return QtCore.QSize(new_width, new_height)

    def paintEvent(self, e):
        # draw native qt combo box controls
        style_painter = QtWidgets.QStylePainter(self)
        text_color = self.palette().color(QtGui.QPalette.ColorRole.Text)
        style_painter.setPen(text_color)
        option = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(option)
        style_painter.drawComplexControl(QtWidgets.QStyle.ComplexControl.CC_ComboBox, option)

        # custom painting
        painter = QtGui.QPainter(self)
        painter.setPen(text_color)
        draw_rect = option.rect.adjusted(self._left_pad, self._top_pad, -self._right_pad, -self._bottom_pad) # available space for custom drawing
        font_metrics = QtGui.QFontMetrics(painter.font())
        if self._icon:
            text_height = font_metrics.size(QtCore.Qt.TextFlag.TextSingleLine, self._display_text).height()
            icon_rect = QtCore.QRect(draw_rect.x(), draw_rect.y() + (draw_rect.height()-text_height)/2, text_height, text_height)  # draw icon to be as big as text height
            painter.drawPixmap(icon_rect, self._icon)
            text_rect = draw_rect.adjusted(icon_rect.width() + self._icon_space, 0, -icon_rect.width(), 0)
        else:
            text_rect = draw_rect

        elided_text = font_metrics.elidedText(self._display_text, QtCore.Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, elided_text)

class CustomComboDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, parent=None):
        super(CustomComboDelegate, self).__init__(parent)

        self.text_default = QtGui.QColor(199, 199, 199)
        self.text_hover = QtGui.QColor(255, 255, 255)
        self.cell_default = QtGui.QColor(67, 67, 67)
        self.cell_hover = QtGui.QColor(43, 43, 43)

    def paint(self, painter, option, index):
        # super().paint(painter, option, index)
        color = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        if color and isinstance(color, QtGui.QColor):
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            h, s, v, a = color.getHsv()
            bg_color = QtGui.QColor.fromHsv(h, 60, 240, a)
            painter.fillRect(option.rect, bg_color)
            painter.setBrush(QtGui.QBrush(color))
            painter.drawRect(0, option.rect.top(), 5, option.rect.height())
        value = index.data(QtCore.Qt.DisplayRole)
        painter.setPen(QtGui.QColor(10, 10, 10))
        painter.drawText(option.rect.adjusted(10,0,0,0), QtCore.Qt.AlignmentFlag.AlignLeft ,value)
        if option.state & QtWidgets.QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, self.cell_hover)
            painter.setPen(self.text_default)
            painter.drawText(option.rect.adjusted(10,0,0,0), QtCore.Qt.AlignmentFlag.AlignLeft ,value)

# -------------------------------------------------- Workflow Publish Widgets --------------------------------------------------

class ImageViewer(QtWidgets.QWidget):
    """
    simple headless UI to view the image, assign the parent argument so this widget can cover the parent rect dynamically
    currently this class is exclusive to workflow publisher, because its rely on the attachment obj (model.AttachmentObject) class to query name, preview, etc
    """
    def __init__(self, parent:QtWidgets.QWidget):
        super().__init__(parent)
        self._attachment_list = []
        self._current_preview_index = 0
        self._scale_factor = 1.0

        self._parent = parent
        self._parent.installEventFilter(self)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)  # set to true so we can use qss to style
        self.setObjectName("input-blocker")
        self.initUI()

    def eventFilter(self, obj, event):
        """listen when parent resize"""
        if obj == self._parent and event.type() == QtCore.QEvent.Type.Resize:
            if self._parent:
                self.setGeometry(self._parent.rect())
        return False # don't call super, prone to error upon deleting object

    def initUI(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(20,20,20,40)
        self.main_v_layout = QtWidgets.QVBoxLayout()
        self.header_layout = QtWidgets.QHBoxLayout()
        self._zoom_layout = QtWidgets.QHBoxLayout()

        self.previous_btn = GraphicButton(SVG.get("arrow-left-circle"), self.previous_preview, color=QtGui.QColor("white"), strength=1, size=(32,32))
        self.previous_btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,QtWidgets.QSizePolicy.Policy.Fixed)
        self.next_btn = GraphicButton(SVG.get("arrow-right-circle"), self.next_preview, color=QtGui.QColor("white"), strength=1, size=(32,32))
        self.next_btn.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,QtWidgets.QSizePolicy.Policy.Fixed)
        self.preview_name_lbl = ElideLabel("")
        self.preview_name_lbl.set_elide_mode(QtCore.Qt.TextElideMode.ElideRight)
        self.preview_name_lbl.setProperty("font-color", "white")
        self.preview_name_lbl.setProperty("heading", "h3")
        self.close_btn = GraphicButton(SVG.get("x-white"), self.hide, size=(28,28))
        self._preview_label = QtWidgets.QLabel()
        self._preview_label.setScaledContents(True) # let the pixmap fill available space/not cutted
        self._scroll_area = QtWidgets.QScrollArea()
        self._scroll_area.setStyleSheet("background-color:#252525")
        self._scroll_area.setWidget(self._preview_label)
        self._scroll_area.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.zoom_in_btn = QtWidgets.QPushButton("zoom in (+)")
        self.zoom_in_btn.clicked.connect(lambda: self._scale_image(1.25))
        self.zoom_out_btn = QtWidgets.QPushButton("zoom out (-)")
        self.zoom_out_btn.clicked.connect(lambda: self._scale_image(0.8))

        self.main_layout.addWidget(self.previous_btn)
        self.main_layout.addLayout(self.main_v_layout)
        self.main_layout.addWidget(self.next_btn)
        self.main_v_layout.addLayout(self.header_layout)
        self.header_layout.addWidget(self.preview_name_lbl)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.close_btn)
        self.main_v_layout.addWidget(self._scroll_area)
        self.main_v_layout.addLayout(self._zoom_layout)
        self._zoom_layout.addWidget(self.zoom_in_btn)
        self._zoom_layout.addWidget(self.zoom_out_btn)

    def _get_size_scale(self, preview):
        """get correct scaling from given preview and available scroll area space, multiplying the preview with returned scaled will fit the preview to the scroll area (fit to window)"""
        self.main_v_layout.activate()    # trigger lazy propagation of qt, to get correct width and height for scroll area
        width_factor = self._scroll_area.width()/(preview.width()+10)    
        height_factor = self._scroll_area.height()/(preview.height()+10)
        return min(width_factor, height_factor, 1) # add 1 so we never scale up, small image wont get pixelated

    def set_preview(self, attachment:models.AttachmentObject):
        """set image/movie preview while automatically fit to scroll area window"""
        self._preview = attachment.preview()

        if isinstance(self._preview, QtGui.QImage):
            # convert to SRgb color space if applicable
            if self._preview.colorSpace().isValid():
                color_space = QtGui.QColorSpace(QtGui.QColorSpace.NamedColorSpace.SRgb)
                self._preview.convertToColorSpace(color_space)
            else:
                self._preview.setColorSpace(QtGui.QColorSpace(QtGui.QColorSpace.NamedColorSpace.SRgb))  # Image has no profile, convert to sRGB for consistency
            self._preview_label.setPixmap(QtGui.QPixmap.fromImage(self._preview))
            self._preview_label.adjustSize()    # update to recalculate proper size
            self._preview_label.resize(self._preview_label.size()*self._get_size_scale(self._preview_label))

        elif isinstance(self._preview, QtGui.QMovie):
            self._preview_label.setMovie(self._preview)
            movie_image = utils.safe_load_image(self._preview.fileName())
            self._preview_label.resize(movie_image.size()*self._get_size_scale(movie_image))    # resize first to wake up the label size update
            self._preview.start()

        self._scale_factor = 1.0
        self.preview_name_lbl.setText(attachment.name())
        if attachment in self._attachment_list:
            self._current_preview_index = self._attachment_list.index(attachment)

    def show_preview(self, attachment:models.AttachmentObject, attachment_list=None):
        self.setGeometry(self._parent.rect())
        if attachment_list:
            self._attachment_list = attachment_list
        self.show()
        self.raise_()   # we need to bring the widget to top at z stack, this important if this widget shared same parent with others
        self.set_preview(attachment)    # set preview at the end after show and raise, so layout size is accurate

    def next_preview(self):
        if self._current_preview_index+1 < len(self._attachment_list):  # we already handle it in set_preview, but this is just additional safe guard
            self._current_preview_index += 1
            self.set_preview(self._attachment_list[self._current_preview_index])

    def previous_preview(self):
        if self._current_preview_index-1 >= 0:  # we already handle it in set_preview, but this is just additional safe guard
            self._current_preview_index -= 1
            self.set_preview(self._attachment_list[self._current_preview_index])

    def _adjust_scrollbar(self, scrollBar, factor):
        # looks like this make the zoom in and out centered
        pos = int(factor * scrollBar.value()+ ((factor - 1) * scrollBar.pageStep() / 2))
        scrollBar.setValue(pos)

    def _scale_image(self, factor):
        self._scale_factor *= factor
        new_size = factor * self._preview_label.size()
        self._preview_label.resize(new_size)

        self._adjust_scrollbar(self._scroll_area.horizontalScrollBar(), factor)
        self._adjust_scrollbar(self._scroll_area.verticalScrollBar(), factor)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.hide()
            #self.cleanup()
            event.accept()  # event handled, prevent propagate to other widget
        super().mouseReleaseEvent(event)

    def reset(self):
        """reset to default state"""
        self.hide()
        self._current_preview_index = 0
        self._attachment_list = []
        self._preview_label.setPixmap(QtGui.QPixmap())

    def cleanup(self):
        """call this when need to close/delete the blocker"""
        if self._parent:
            self._parent.removeEventFilter(self)
            self._parent = None
        self.deleteLater()  # temp add

# separator -------------------------------------------------- Sharing Widgets (CGTW & Slack) --------------------------------------------------

class TokenWidget(QtWidgets.QWidget):
    """designed to be use with TokenInputEdit class"""
    onDelete = QtCore.Signal(object)
    def __init__(self, text, color):
        super().__init__()
        self.text = text
        self.color = QtGui.QColor(color)
        
        self._bg_color =   QtGui.QColor.fromHsv(self.color.hue(), 40, 250)  # original 60, 240
        self._text_color = QtGui.QColor.fromHsv(self.color.hue(), 190, 150)
        self._brush = QtGui.QBrush(self._bg_color)

        self.initUI()

    def initUI(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(7,2,7,2)
        self.display_label = QtWidgets.QLabel(self.text)
        self.display_label.setStyleSheet(f"color:{self._text_color.name()}")
        self.display_label.setObjectName("token-label")
        self.close_btn = GraphicButton(SVG.get("x-dark"), self.remove, size=(16,16))

        self.main_layout.addWidget(self.display_label)
        self.main_layout.addWidget(self.close_btn)

    def remove(self):
        self.onDelete.emit(self)
        self.deleteLater()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(self._brush)
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(),self.height()/2,self.height()/2)

class TokenInputEdit(QtWidgets.QFrame):
    """simple class to manages token widgets under flow layout, also handle adding and remove each item"""
    #CustomUserRole = QtCore.Qt.ItemDataRole.UserRole + 1
    def __init__(self):
        self._token_list = []

        super().__init__()
        self.initUI()

    def get_all_token(self):
        return self._token_list

    def initUI(self):
        self.setFrameStyle(QtWidgets.QFrame.Shape.Box | QtWidgets.QFrame.Shadow.Plain)
        self.setLineWidth(1)

        self.flow_layout = FlowLayout(self)
        self.flow_layout.setSpacing(5)
        self.flow_layout.setContentsMargins(5,5,5,5)

    def insert_user_token(self, user_token:TokenWidget):
        user_token.onDelete.connect(self.on_user_removed)
        self._token_list.append(user_token)
        self.flow_layout.addWidget(user_token)
  
    def on_user_removed(self, obj):
        if obj in self._token_list:
            self._token_list.remove(obj)

    def clear(self):
        for obj in self._token_list:
            obj.deleteLater()
        self._token_list.clear()


# separator -------------------------------------------------- CGTW Widgets --------------------------------------------------

class TagToken(TokenWidget):
    def __init__(self, tag:models.CGTW_Tags):
        self.tag = tag
        super().__init__(tag.text, f"{tag.color}")

class TagTokenInputEdit(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # widgets
        
        self.tag_combo_box = StaticDisplayComboBox("Tags", QtGui.QPixmap.fromImage(SVG.get("tag")))
        utils.MouseWheelGuard.prevent(self.tag_combo_box)
        self.tag_combo_box.activated.connect(self.on_insert_tag)
        self.tag_combo_box.setPadding(10, 8, 10, 8)
        self.tag_combo_box.setFixedWidth(self.tag_combo_box.sizeHint().width())
        self.tag_input_edit = TokenInputEdit()

        # layouts
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.main_layout.setSpacing(0)
        self.tag_stretch_layout = QtWidgets.QVBoxLayout()   # retain tag btn to always at top (previously i tried using set alignment doesnt work withouth helper layout)
        self.tag_stretch_layout.setContentsMargins(0,0,0,0)

        self.main_layout.addLayout(self.tag_stretch_layout)
        self.tag_stretch_layout.addWidget(self.tag_combo_box)
        self.tag_stretch_layout.addStretch()
        self.main_layout.addWidget(self.tag_input_edit)

    def add_tag(self, tag_obj):
        self.tag_combo_box.addItem(tag_obj.text, tag_obj)

    def get_tags(self):
        tokens = self.tag_input_edit.get_all_token()
        return [token.tag.text for token in tokens]

    def on_insert_tag(self):
        data = self.tag_combo_box.currentData()
        if data:
            self.tag_input_edit.insert_user_token(TagToken(data))

    def clear(self):
        self.tag_combo_box.clear()
        self.tag_input_edit.clear()

class TaskStatusComboBox(ModernComboBox):
    """Combo box with vertical line color on the left side, please set the 'itemDataRole' for each item added with 'DecorationRole' to make it changing with current selection"""
    def __init__(self, parent=None):
        self._default_color = QtGui.QColor("#768090")
        self._colored_arrow_pen = QtGui.QPen()
        self._colored_arrow_pen.setWidth(2)
        self._color_hint_spacing = 10
        self._color_hint_radius = 5

        super().__init__(parent)

    def sizeHint(self):
        size = super().sizeHint()
        height = size.height() 
        width = size.width() + self._left_pad + self._color_hint_spacing + self._color_hint_radius*2
        
        return QtCore.QSize(width, height)

    def paintEvent(self, e):
        color = self.itemData(self.currentIndex(), QtCore.Qt.ItemDataRole.DecorationRole)
        if not color or not isinstance(color, QtGui.QColor):
            return super().paintEvent(e)

        # *some code is pasted from ModernComboBox class
        option = QtWidgets.QStyleOptionComboBox()
        self.initStyleOption(option)

        option_rect = option.rect
        sub_ctrl_rect = self.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_ComboBox, option, QtWidgets.QStyle.SubControl.SC_ComboBoxArrow)
        edit_rect = self.style().subControlRect(QtWidgets.QStyle.ComplexControl.CC_ComboBox, option, QtWidgets.QStyle.SubControl.SC_ComboBoxEditField).adjusted(self._left_pad,0,0,0)    # Cheating a bit with adding manually padding on left side

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        font_metrics = QtGui.QFontMetrics(painter.font())

        # determine color 
        h, s, v, a = color.getHsv()
        bg_color = QtGui.QColor.fromHsv(h, 40, 250, a)
        text_color = QtGui.QColor.fromHsv(h, 190, 150, a)
        painter.setPen(color)

        # draw combo box main body
        painter.setBrush(bg_color)
        painter.drawRoundedRect(option_rect, 5, 5)

        # draw circle color hint 
        painter.setBrush(color)
        color_hint_rect = QtCore.QRect(edit_rect.x(), edit_rect.height()/2-1, self._color_hint_radius*2, self._color_hint_radius*2) # for Y we substract by 1 to align to center, but a bit cheating because i stumble upon odd number divide by 2
        painter.drawRoundedRect(color_hint_rect, self._color_hint_radius, self._color_hint_radius)

        # draw text
        painter.setPen(text_color)
        elided_text = font_metrics.elidedText(self.currentText(), QtCore.Qt.TextElideMode.ElideRight, edit_rect.width()-color_hint_rect.width()-self._color_hint_spacing)
        painter.drawText(edit_rect.adjusted(color_hint_rect.x() + self._color_hint_spacing, 0, 0, 0), QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, elided_text)

        # draw arrow down
        self._colored_arrow_pen.setColor(color)
        painter.setPen(self._colored_arrow_pen)
        width, height = sub_ctrl_rect.width(), sub_ctrl_rect.height()
        x = sub_ctrl_rect.x()
        
        painter.drawLine(x+width*0.25, height*0.4, x+width/2, height*0.6)
        painter.drawLine(x+width/2, height*0.6, x+width-width*0.25, height*0.4)

# separator -------------------------------------------------- Slack Widgets --------------------------------------------------

class UserToken(TokenWidget):
    def __init__(self, user:models.SlackUser):
        self.user = user
        super().__init__(user.profile.username, f"#{user.color}")

class UserTokenLineEdit(QtWidgets.QLineEdit):
    onClicked = QtCore.Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Search Users...")
        self.setFrame(False)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.onClicked.emit()
        return super().mousePressEvent(event)

    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        key = event.key()
        if self.completer() and not self.completer().popup().isVisible():
            if key in (QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Return):
                self.clear()
                return
        if self.completer() and self.completer().completionCount() <= 0:
            global_pos = self.mapToGlobal(QtCore.QPoint(0, 5))  
            QtWidgets.QToolTip.showText(global_pos, "No User Found", self)
        else:
            QtWidgets.QToolTip.hideText()

class UserTokenInputEdit(QtWidgets.QWidget):
    CustomUserRole = QtCore.Qt.ItemDataRole.UserRole + 1
    def __init__(self, label):
        self.label = label

        super().__init__()
        self.initCompleter()
        self.initUI()
    
    def initCompleter(self):
        self.completer = QtWidgets.QCompleter()
        self.completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setMaxVisibleItems(3)
        self.completer_model = QtGui.QStandardItemModel()
        self.completer.setModel(self.completer_model)
        self.completer.activated[QtCore.QModelIndex].connect(self._insert_user_token)

    def on_input_clicked(self):
        self.completer.setCompletionPrefix(self.token_line_edit.text())
        self.completer.complete()

    def initUI(self):
        # widgets
        self.tag_people_lbl = QtWidgets.QLabel(self.label)
        self.token_input_edit = TokenInputEdit()
        self.token_line_edit = UserTokenLineEdit()
        self.token_line_edit.setCompleter(self.completer)
        self.token_line_edit.onClicked.connect(self.on_input_clicked)

        # layouts
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.main_layout.addWidget(self.tag_people_lbl)
        self.main_layout.addWidget(self.token_input_edit)

        self.token_input_edit.flow_layout.addWidget(self.token_line_edit)

    def get_user_id(self):
        return [token.user.id for token in self.token_input_edit._token_list]

    def _insert_user_token(self, model_index):
        user = model_index.data(self.CustomUserRole)
        self.token_input_edit.insert_user_token(UserToken(user))
        QtCore.QTimer.singleShot(0, self.token_line_edit.clear) # deferred action to let all event finish first and then clear it. we use qTimer instead of python timer to let UI threads not frozen

    def set_completer_model(self, data):
        if not data: 
            data = []
        sorted_usernames = sorted(data, key=str)
        self.completer_model.clear()
        for user in sorted_usernames:
            item = QtGui.QStandardItem(str(user))
            item.setData(user, self.CustomUserRole)
            self.completer_model.appendRow(item)

    def clear(self):
        self.token_input_edit.clear()

# separator -------------------------------------------------- Attachments Widgets --------------------------------------------------

class AttachmentWidget(QtWidgets.QWidget):
    onRemove = QtCore.Signal(object)
    onAttachmentClicked = QtCore.Signal(object)
    def __init__(self, attachment_obj:models.AttachmentObject, preview_length=60, remove_btn_size=22, parent=None):
        super(AttachmentWidget, self).__init__(parent)
        self.attachment_obj = attachment_obj
        self._connected_window = None
        self._thumbnail_movie = None    

        # widget paint and size settings
        self._preview_scaling = 1   # we set scaling as class variable, to let _setup_pixmap doesnt accept args and can be used as callback for screenChanged
        self._preview_length = preview_length
        self._remove_btn_size = remove_btn_size
        self._extended_space = self._remove_btn_size/3 
        self._widget_length = self._preview_length + self._extended_space
        self._file_div_widget_width = self._widget_length*3   # used when attachment is file, become rectangular instead of square
        self._radius = self._preview_length/8
        self._border_thickness = 2 # prefer even number because thickness will be divided by 2 for pixmap calculations
        self._text_padding = 5 

        self._border_pen = QtGui.QPen("#ebb904") 
        self._border_pen.setWidth(self._border_thickness)

        # hover effect
        self._hovered_effect_brush = QtGui.QBrush("#BFC7C9")
        self._mouse_hovered = False

        self._loading()
        self.initUI()
        self.initPreview()

    def _loading(self):
        """temporary show loading icon while file preview still loads"""
        self._is_loading_preview = True 
        self._thumbnail = SVG.get("hourglass")  # store raw image here before apply dpr scaling, so we can keep highest resolution
        self.set_thumbnail(self._thumbnail, 0.5) 
        self.setFixedSize(self._widget_length, self._widget_length)

    def initUI(self):
        self.main_layout = QtWidgets.QGridLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.remove_btn = GraphicButton(SVG.get("x-circle"), self.on_remove, QtGui.QColor("white"), 0.1, (self._remove_btn_size, self._remove_btn_size))
        self.remove_btn.hide()
        self.main_layout.addWidget(self.remove_btn, 0, 0, QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignRight)

    def initPreview(self):
        utils.ThreadManager.run_task(self.attachment_obj.get_thumbnail, success_cb=self.get_attachment_obj_thumbnail, error_cb=self._on_failed_get_thumbnail)

    def get_attachment_obj_thumbnail(self, thumbnail_img):
        if self.attachment_obj.preview():
            # take care if preview is gif/movie or static image
            if isinstance(self.attachment_obj.preview(), QtGui.QMovie):
                self._thumbnail_movie = QtGui.QMovie(str(self.attachment_obj.full_path()))   
                self._thumbnail_movie.frameChanged.connect(self.repaint) 
                factor = max(self._preview_length/(thumbnail_img.width()) , self._preview_length/(thumbnail_img.height())) # scale the gif to fill the space, if too big scale down, vice versa (same concept like imageViewer scale _get_size_scale)
                self._thumbnail_movie.setScaledSize(QtCore.QSize(thumbnail_img.width()*factor, thumbnail_img.height()*factor))
                self._thumbnail_movie.start()
            self.setFixedSize(self._widget_length, self._widget_length)
            self._is_loading_preview = False
            self.set_thumbnail(thumbnail_img)
        else:
            self.setFixedSize(self._file_div_widget_width, self._widget_length)
            self._is_loading_preview = False
            self.set_thumbnail(thumbnail_img, 0.7)
        
    def _on_failed_get_thumbnail(self):
        self.set_thumbnail(SVG.get("broken image"), 0.5)

    def set_thumbnail(self, thumbnail, scaling=1):
        self._preview_scaling = scaling
        self._thumbnail = thumbnail
        self._setup_pixmap()

    def _setup_pixmap(self):
        current_dpr = self.devicePixelRatioF()
        self._pixmap = QtGui.QPixmap.fromImage(utils.scale_image(self._thumbnail, 
                                                                 (self._preview_length*current_dpr*self._preview_scaling, self._preview_length*current_dpr*self._preview_scaling)))
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        utils.setup_screenChanged_connection(self, self._connected_window, self._setup_pixmap)

    def enterEvent(self, event=None):
        self._mouse_hovered = True
        if self.attachment_obj.preview():
            self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.remove_btn.show()
        self.update()

    def leaveEvent(self, event=None):
        self._mouse_hovered = False
        self.remove_btn.hide()
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.attachment_obj.preview():
                self.onAttachmentClicked.emit(self.attachment_obj)
        super().mouseReleaseEvent(event)

    def on_remove(self, event=None):
        self.onRemove.emit(self)

    def paintEvent(self, event):
        # border rect: is for calculating border display without it being cropped
        self.border_rect = QtCore.QRect(self._border_thickness/2, 
                                        self._extended_space + self._border_thickness/2, 
                                        self.width()-self._border_thickness-self._extended_space,    
                                        self.height()-self._border_thickness-self._extended_space)

        # calculate for available space 
        avail_width_pixmap = self.width() - self._extended_space - self._border_thickness*2
        if avail_width_pixmap > self._preview_length:    
            avail_width_pixmap = self._preview_length
        avail_height_pixmap = self.height() - self._extended_space - self._border_thickness*2
            
        self.pixmap_rect = QtCore.QRect(self.border_rect.left() + self._border_thickness/2,
                                        self.border_rect.top() + self._border_thickness/2,
                                        avail_width_pixmap,
                                        avail_height_pixmap)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        # ---  draw border ---
        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
        painter.setPen(self._border_pen)
        painter.drawRoundedRect(self.border_rect, self._radius, self._radius)

        # --- draw if contains movie ---
        if self._thumbnail_movie:
            # credit for painting qMovie (eyllanesc): https://stackoverflow.com/questions/41709464/python-pyqt-add-background-gif
            currentFrame  = self._thumbnail_movie.currentPixmap()
            frameRect = currentFrame.rect()
            frameRect.moveCenter(self.border_rect.center())

            if frameRect.intersects(event.rect()):
                path = QtGui.QPainterPath()
                path.addRoundedRect(self.pixmap_rect, self._radius, self._radius)
                painter.setClipPath(path)
                painter.drawPixmap(frameRect.left(), frameRect.top(), currentFrame)
                
        else:
            # --- draw pixmap ---  notes to myself: no need to do rect adjusted dpr, because we already tell pixmap to be dpr aware
            x = (self._pixmap.width() - self.pixmap_rect.width()) // 2      # crop image to center
            y = (self._pixmap.height() - self.pixmap_rect.height()) // 2
            source_rect = QtCore.QRect(x, y, self.pixmap_rect.width(), self.pixmap_rect.height()) 

            path = QtGui.QPainterPath()
            path.addRoundedRect(self.pixmap_rect, self._radius, self._radius)
            painter.setClipPath(path)
            painter.drawPixmap(self.pixmap_rect, self._pixmap, source_rect) # we do projection on target rect from source rect to center it

        # take care when file contains image
        if self._mouse_hovered and self.attachment_obj.preview():
            painter.setCompositionMode(QtGui.QPainter.CompositionMode.CompositionMode_Multiply)     # darken the image on hovering, this will give cue for user that image is pressable
            painter.setBrush(self._hovered_effect_brush)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.pixmap_rect, self._radius, self._radius)
        # draw text for file type (non image) attachment
        elif not self.attachment_obj.preview() and not self._is_loading_preview:
            painter.setClipping(False)  # turn off clipping so we can draw outside pixmap rect 
            self.info_rect = QtCore.QRect(QtCore.QPoint(self._preview_length + self._border_thickness,
                                                        self._extended_space + self._border_thickness),
                                          QtCore.QPoint(self.width() - self._extended_space - self._border_thickness - self._border_thickness/2,    # sorry, not sure about the substract by border thickness, i just find this works
                                                        self.height() - self._border_thickness*2)
                                          )
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor("#c6cfe3"))
            painter.drawRect(QtCore.QRect(self.info_rect.x(), self.info_rect.y(), self._radius, self.info_rect.height()))  
            painter.drawRoundedRect(self.info_rect, self._radius, self._radius)
            self.text_rect = self.info_rect.adjusted(self._text_padding, 0,-self._text_padding,0)
            painter.setPen(QtGui.QPen("#323232"))
            elided_text = self.fontMetrics().elidedText(self.attachment_obj.name(), QtCore.Qt.TextElideMode.ElideRight, self.text_rect.width()) 
            painter.drawText(self.text_rect, QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter, elided_text)

# separator -------------------------------------------------- Main Asset Widgets --------------------------------------------------
class APIStatusIcon(GraphicLabel):
    """simple ui class to show status indicator (red:error, green:no error)"""
    RED = QtGui.QBrush(QtGui.QColor("#d95448"))
    GREEN = QtGui.QBrush(QtGui.QColor("#3daa7c"))
    STATUS = [RED, GREEN]
    def __init__(self, image=None, size=(32, 32), edge_radius=0, initial_brush=GREEN, parent=None):
        self._indicator_brush = initial_brush
        super().__init__(image, size, edge_radius, parent)

    def change_status(self, status_brush):
        if status_brush not in self.STATUS:
            raise ValueError("trying to change the API Status Icon, but the given status is not a member of status list. See APIStatusIcon class for details")
        self._indicator_brush = status_brush
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._indicator_brush and isinstance(self._indicator_brush, QtGui.QBrush):
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

            painter.setPen(QtGui.QColor("#5D5D5D"))
            painter.setBrush(self._indicator_brush)
            painter.drawRoundedRect(QtCore.QRect(self.width()-10,self.height()-10,10,10), 10, 10)

class UserCardWidget(QtWidgets.QWidget):
    """small class handling user section for configuration"""
    user_icon_size = (42,42)

    def __init__(self, parent=None):
        super().__init__(parent)
        #self._background_brush = QtGui.QBrush(QtGui.QColor("#e1e1eb"))
        self.initUI()

    def initUI(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.user_info_layout = QtWidgets.QVBoxLayout()
        self.user_info_layout.setSpacing(0)

        self.user_profile_img = GraphicLabel(SVG.get("no account 1"), self.user_icon_size, self.user_icon_size[0]/4)
        self.user_profile_img.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,QtWidgets.QSizePolicy.Policy.Fixed)
        self.username_label = QtWidgets.QLabel("")
        self.user_email_label = QtWidgets.QLabel("")
        self.user_email_label.setObjectName("user-email-display")
        self.dropdown_icon = GraphicLabel(SVG.get("stat minus 1"))

        self.main_layout.addWidget(self.user_profile_img)
        self.main_layout.addLayout(self.user_info_layout)
        self.user_info_layout.addWidget(self.username_label)
        self.user_info_layout.addWidget(self.user_email_label)
        self.main_layout.addWidget(self.dropdown_icon)

    def change_user_icon(self, img):
        self.user_profile_img.change_icon(img, self.user_icon_size)

class UserSessionPanel(QtWidgets.QWidget):
    """pure UI Class: container widget for user related stuff. equipped with ui manager function"""
    icon_size = (36,36)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()

    def initUI(self):
        self.main_layout = QtWidgets.QHBoxLayout(self)
        self.main_layout.setContentsMargins(2,2,2,2)

        self.cgtw_icon = APIStatusIcon(SVG.get("cgtw"), self.icon_size)
        self.cgtw_icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,QtWidgets.QSizePolicy.Policy.Fixed) # prevent stretch
        self.slack_icon = APIStatusIcon(SVG.get("slack"), self.icon_size)
        self.slack_icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed,QtWidgets.QSizePolicy.Policy.Fixed)
        self.user_card = UserCardWidget()
    
        self.main_layout.addWidget(self.cgtw_icon)
        self.main_layout.addWidget(self.slack_icon)
        self.main_layout.addWidget(self.user_card)

    def load_user_img(self, image):
        self.user_card.change_user_icon(image)

class AssetPublishPanel(QtWidgets.QWidget):
    """placeholder widget for AssetPublishViewport, and will handle passing the data/manage the editor"""
    def __init__(self, core, parent=None):
        self.core = core
        self.asset_type = self.core.ASSET_TYPE
        self.current_asset = None

        self._drag_hovered = False
        self._hovered_pen = QtGui.QPen(QtGui.QColor("#ebb904"))
        self._hovered_pen.setWidth(4)
        self._hovered_brush = QtGui.QBrush(QtGui.QColor.fromRgba(QtGui.qRgba(172, 187, 191, 100)))
        self._dash_pen = QtGui.QPen("#9A9A9A")
        self._dash_pen.setDashPattern([10,2])

        super().__init__(parent)
        self.viewport = AssetPublishViewport(self)
        self._img_viewer = ImageViewer(self)
        self._img_viewer.hide() # hide it, we only construct it so we can call it later when viewing image

        self.setMinimumSize(200,200)
        self.setAcceptDrops(True)
        self.initUI()

    def initUI(self):
        # initialize the startup widget, showing when there is no asset to give user direction to start
        self.startup_widget = QtWidgets.QWidget()
        self.startup_bg_img = GraphicLabel(SVG.get("cube"), (48,48))
        self.startup_info_lbl = QtWidgets.QLabel("Drag maya file to start (*.ma *.mb)")
        self.startup_info_lbl.setProperty("font-color", "grey")
        self.startup_layout = QtWidgets.QVBoxLayout(self.startup_widget)
        self.startup_layout.addWidget(self.startup_bg_img)
        self.startup_layout.addWidget(self.startup_info_lbl)
        self.startup_info_lbl.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.startup_widget)
        self.main_layout.addWidget(self.viewport)
        self.viewport.hide()

    def set_current_asset(self, asset:models.FileOBJ):
        """set the current asset and displaying all the UI element from the asset info"""
        self.current_asset = asset
        self.reset_viewport()
        self.viewport.file_icon.change_icon(SVG.get(asset.extension, "file"))
        self.viewport.filename_label.setText(asset.basename)
        self.viewport.file_location_edit.setText(asset.full_path)
        self.viewport.file_size_label.setText(f"| ({utils.adapt_file_size_unit(asset.size_bytes)})")
        self.viewport.modified_info_label.setText("Modified: %s"%(asset.modified_time))
        self.startup_widget.hide()
        self.viewport.show()

    # --------------------------------------- viewport reset helper func (refactor) ---------------------------------------

    def remove_current_asset(self):
        if self.current_asset:
            self.current_asset = None
            self.startup_widget.show()
            self.viewport.hide()
    
    def reset_viewport(self):
        """revert all viewport changes back to default"""
        self.viewport.file_icon.change_icon(SVG.get("file"))
        self.viewport.filename_label.setText("Undefined")
        self.viewport.file_location_edit.setText("N/A")
        self.viewport.file_size_label.setText("| (0 B)")
        self.viewport.modified_info_label.setText("Modified: N/A")

        self.viewport.project_combo_box.setCurrentIndex(0)
        self.reset_cgtw_task_viewport()
        self.reset_slack_viewport()
        self._img_viewer.reset()

    def reset_cgtw_task_viewport(self):
        self.viewport.task_count_label.setText("|")
        self.viewport.task_combo_box.clear()
        self.reset_cgtw_task_data()

    def reset_cgtw_task_data(self):
        """reset only task data related widget not the task combobox itself, like task.status, task.tag and preview"""
        self.viewport.status_combo_box.clear()
        self.viewport.tag_edit.clear()
        self.viewport.task_preview.change_icon(SVG.get("photo"))

    def reset_slack_viewport(self):
        self.viewport.slack_channel_combo_box.setCurrentIndex(0)
        checked_btn = self.viewport.asset_type_btn_grp.checkedButton()
        if checked_btn:
            self.viewport.asset_type_btn_grp.setExclusive(False)    # toggle off to allow btn to be unchecked
            checked_btn.setChecked(False)
            self.viewport.asset_type_btn_grp.setExclusive(True)
        self.viewport.cc_users_edit.clear()
        self.viewport.mention_users_edit.clear()
        self.viewport.description_editor.clear()

    # --------------------------------------- CGTW section related funcs ---------------------------------------

    def on_cgtw_project_changed(self):
        self.reset_cgtw_task_viewport()
        current_project = self.viewport.project_combo_box.currentData()
        if current_project:
            self.viewport.task_combo_box.addItem("---Select Task---")
            self.core.thread_manager.run_task(self.core.cgtw_api.get_assigned_task, current_project.db, success_cb=self._on_get_assigned_task, error_cb=lambda: print("CGTW Error: can't get assigned task!"), message="get assigned task")

    def _on_get_assigned_task(self, task_payload):
            current_project = self.viewport.project_combo_box.currentData()
            
            if task_payload:
                all_tasks =  [task for task in task_payload if task.get("asset.entity")] 
            else:
                all_tasks = []
            for task in all_tasks:
                data = models.CGTW_Task(task.get("asset.entity"), current_project, task.get("task.id"))
                self.viewport.task_combo_box.addItem(str(data), data)
            self.viewport.task_combo_box.view().updateGeometry()
            self.viewport.task_count_label.setText(f"| {len(all_tasks)} item")  # update task count ui

    def on_cgtw_task_changed(self):
        self.reset_cgtw_task_data()
        current_task = self.viewport.task_combo_box.currentData()
        if current_task:
            self.viewport.status_combo_box.addItem("---Select Status---")

            # add status and tags object to combo box, append color data to ItemDataRole.UserRole
            for count, status in enumerate(self.core.cgtw_status, 1):   # start from 1 because we added "---select status---" item at the top
                self.viewport.status_combo_box.addItem(str(status))
                model_index = self.viewport.status_combo_box.model().index(count, 0)
                self.viewport.status_combo_box.setItemData(model_index.row(), QtGui.QColor(status.color), QtCore.Qt.ItemDataRole.DecorationRole)
            for tag in self.core.cgtw_tags:
                self.viewport.tag_edit.add_tag(tag)

            # check if current task have status assigned, and see if status is one of the options 
            self.core.thread_manager.run_task(self.core.cgtw_api.get_task_status, 
                                                self.viewport.project_combo_box.currentData().db, 
                                                current_task.id, 
                                                success_cb=self._on_get_task_status, 
                                                error_cb=lambda: print("CGTW Error: can't get selected task status!"),
                                                message="get task status")
            
            # download image and load it if the task contains img
            self.core.thread_manager.run_task(self.core.cgtw_api.is_task_has_image, 
                                                self.viewport.project_combo_box.currentData().db, 
                                                current_task.id, 
                                                success_cb=self._is_task_has_image, 
                                                error_cb=lambda: print("CGTW Error: can't check if task contains image or not!"),
                                                message="check task image availability")

    def _on_get_task_status(self, task_status):
        if task_status in [str(status) for status in self.core.cgtw_status]:
            self.viewport.status_combo_box.setCurrentText(task_status)

    def _is_task_has_image(self, has_image:bool):
        if has_image:
            self.core.thread_manager.run_task(self.load_task_image,
                                                self.viewport.project_combo_box.currentData().db, 
                                                self.viewport.task_combo_box.currentData().id, 
                                                success_cb=self.viewport.task_preview.change_icon, 
                                                error_cb=lambda: print("CGTW Error: can't load task image!"),
                                                message="load task image")  

    def load_task_image(self, db, task_id):
        with tempfile.TemporaryDirectory(prefix="Publisher_temp_task_img_") as temp_dir:
            image_dest_path = self.core.cgtw_api.download_task_image(db, task_id, True, temp_dir)
            image =  utils.safe_load_image(str(image_dest_path[0]["task.image"][0]))
            return image

    # --------------------------------------- attachment related funcs ---------------------------------------
    def on_attachment_clicked(self, attachment):
        """create a image viewer instance then show it and query all attachment with preview available in text editor"""
        attachment_list = [att for att in self.viewport.description_editor.get_attachment_with_preview()]
        self._img_viewer.show_preview(attachment, attachment_list)  

    # --------------------------------------- API callbacks for event listener / real time update ---------------------------------------
    def update_completer_model(self, data=None):
        """function called when finish receiving callback from slack api or slack event api, it will keep the completer suggestion updated"""
        if not data: 
            data = []
        self.viewport.description_editor.set_completer_model(data)
        self.viewport.mention_users_edit.set_completer_model(data)
        self.viewport.cc_users_edit.set_completer_model(data)

    def update_CGTW_projects(self, projects):
        self.viewport.project_combo_box.clear()
        self.viewport.project_combo_box.addItem("---Select Project---")
        for project in projects:
            self.viewport.project_combo_box.addItem(str(project), userData=project)   # passing the __str__ func of project class and the project itself

    def update_slack_channels(self, channels_data):
        self.viewport.slack_channel_combo_box.clear()
        self.viewport.slack_channel_combo_box.addItem("---Select Channel---")
        for channel in channels_data:
            self.viewport.slack_channel_combo_box.addItem(str(channel), userData=channel.id)

    # --------------------------------------- File Handler ---------------------------------------
    def on_browse_file(self):
        if os.path.exists(self.viewport.file_location_edit.text()):
            webbrowser.open(os.path.dirname(self.viewport.file_location_edit.text()))
        else:
            print("Path does not exists")

    def filterOutFile(self, files):
        """Acts as a filter of files path, add the file and return only accepted file path"""
        return [f for f in files if utils.get_file_extension(f) in self.core.ACCEPTED_FILE]

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls()]
            # if one of the file being drag is accepted we will pass it to publisher core to handle
            for name in files: 
                extension = utils.get_file_extension(name)
                if extension in self.core.ACCEPTED_FILE:
                    self._drag_hovered = True 
                    self.update()
                    event.accept()
                    break
            else:
                event.ignore()
                return
        else:
            event.ignore()
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        # override qlistwidget default dragMoveEvent, so we can still actively accept any data
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            self.update()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drag_hovered = False
        self.update()

    def dropEvent(self, event):
        mime_data = event.mimeData()
        self._drag_hovered = False
        self.update()

        if mime_data.hasUrls():
            files = [u.toLocalFile() for u in event.mimeData().urls()]
            accepted_file = self.filterOutFile(files)
            if accepted_file:
                self.core.handleAddFile(accepted_file[0])  # only take the first accepted file, since we dont support multiple asset
            event.acceptProposedAction()

    # --------------------------------------- Publish Handler ---------------------------------------

    def request_publish(self):
        if self.current_asset and isinstance(self.current_asset, models.FileOBJ):
            asset_info = self.get_current_asset_info()
            if not self.current_asset.exists:
                print("asset path not exists, it might get deleted or modified. Can't publish")
                return False
            if not asset_info.within_char_limit:
                print("can't publish because character count already exceed limit")
                return False

            self.viewport.publish_btn.setDisabled(True)
            self.core.thread_manager.run_task(self.core._exec_publish,
                                                self.current_asset,
                                                asset_info,
                                                success_cb=lambda: self.remove_current_asset(),
                                                finished_cb=lambda: self.viewport.publish_btn.setDisabled(False),
                                                error_cb=lambda e: print("Error during publish: ",e),
                                                message="publish")
        else:
            print("error, can't publish asset") # we shouldnt be able to publish without asset, since we already handle on/off visibility for this. This is just a safeguard

    def get_current_asset_info(self):
        """primary function to get all user editable info/input, wrap it as DTO for better readability"""
        asset_info = models.AssetInfo(
                                        project = self.viewport.project_combo_box.currentData(),
                                        task = self.viewport.task_combo_box.currentData(),
                                        channel = self.viewport.slack_channel_combo_box.currentData(),
                                        asset_type = self.viewport.asset_type_btn_grp.checkedButton().text(),
                                        mentioned_user = self.viewport.mention_users_edit.get_user_id(),
                                        CC_user = self.viewport.cc_users_edit.get_user_id(),
                                        cgtw_desc = self.viewport.description_editor.get_plain_text(),
                                        slack_desc = self.viewport.description_editor.parse_to_block_kit(),
                                        attachments = self.viewport.description_editor.get_attachments(),
                                        within_char_limit = self.viewport.description_editor.is_within_char_limit,
                                        status = self.viewport.status_combo_box.currentText(),
                                        task_tags = self.viewport.tag_edit.get_tags(),
                                    )
        return asset_info

    # --------------------------------------- Paint UI ---------------------------------------

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        # draw dashed border
        if not self._drag_hovered:
            painter.setPen(self._dash_pen)
            rect = self.rect().adjusted(1,1,-1,-1)   # adjust so the border is not clipped
            painter.drawRect(rect)
        if self._drag_hovered:
            painter.setPen(self._hovered_pen)
            painter.setBrush(self._hovered_brush)
            painter.drawRect(self.rect())

class AssetPublishViewport(QtWidgets.QScrollArea):
    """this class acts as a vieport for AssetPublishPanel, it is a brainless viewport every logic must be handled in AssetPublishPanel"""
    def __init__(self, panel:AssetPublishPanel, parent=None):
        super().__init__(parent)
        self.slack_type_radio_btn = []
        self.panel = panel
        self.initWidgets()
        self.initLayouts()

    def initWidgets(self):
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setProperty("bg","white")
        self.setWidget(self.main_widget)
        self.setWidgetResizable(True)

        # file info UI
        self.file_div_widget = QtWidgets.QWidget()
        self.file_div_widget.setObjectName("file-div")
        self.file_icon = GraphicLabel(SVG.get("file"), (48,48))
        self.file_icon.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.file_info_lbl = QtWidgets.QLabel("File Info")
        self.file_info_lbl.setProperty("heading", "h2")
        self.file_close_btn = GraphicButton(SVG.get("cancel"), self.panel.remove_current_asset)
        self.filename_label = ElideLabel("Undefined")
        self.filename_label.set_elide_mode(QtCore.Qt.TextElideMode.ElideRight)
        self.file_size_label = QtWidgets.QLabel("| (0 B)")
        self.file_size_label.setProperty("font-color", "grey")
        self.modified_info_label = QtWidgets.QLabel("Modified: N/A")
        self.modified_info_label.setProperty("font-color", "grey")
        self.file_location_edit = QtWidgets.QLineEdit("N/A")
        self.file_location_edit.home(False)
        self.file_location_edit.setReadOnly(True)
        self.file_location_edit.setFocusPolicy(QtCore.Qt.FocusPolicy.ClickFocus)
        self.file_browser_btn = GraphicButton(SVG.get("folder open"), self.panel.on_browse_file, size=(24,24))
        # show last updated info 
        font = QtGui.QFont()
        font.setItalic(True)
        font.setWeight(QtGui.QFont.Weight.Light)
        current_datetime = datetime.now()
        self.last_update_datetime_label = QtWidgets.QLabel("last updated: " + current_datetime.strftime("%a, %d %b %Y %H:%M:%S"))
        self.last_update_datetime_label.setProperty("font-color", "grey")
        self.last_update_datetime_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        self.last_update_datetime_label.setFont(font)

        # separator for clearer group divider
        self.cgtw_h_line = QtWidgets.QFrame()
        self.cgtw_h_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.cgtw_h_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.cgtw_h_line.setObjectName("cgtw-sep-line")
        self.cgtw_h_line.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.slack_h_line = QtWidgets.QFrame()
        self.slack_h_line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        self.slack_h_line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        self.slack_h_line.setObjectName("slack-sep-line")
        self.slack_h_line.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        # publish properties UI (user input)
        # --- CGTW widgets ---
        self.CGTW_icon = GraphicLabel(SVG.get("cgtw"), (36,36))
        self.CGTW_label = QtWidgets.QLabel("CGTW")
        self.CGTW_label.setProperty("heading", "h2")
        self.CGTW_collapse_btn = GraphicButton(SVG.get("arrow drop down"))

        self.project_label = QtWidgets.QLabel("Project")
        self.project_label.setProperty("heading", "h3")
        self.project_combo_box = ModernComboBox()
        utils.MouseWheelGuard.prevent(self.project_combo_box)
        self.project_combo_box.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.project_combo_box.activated.connect(self.panel.on_cgtw_project_changed)    # take care when user select same project

        self.task_label = QtWidgets.QLabel("Task")
        self.task_label.setProperty("heading", "h3")
        self.task_count_label = QtWidgets.QLabel("|")
        self.task_count_label.setProperty("font-color", "light-grey")
        self.task_combo_box = ModernComboBox()
        utils.MouseWheelGuard.prevent(self.task_combo_box)
        self.task_combo_box.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.task_combo_box.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.task_combo_box.activated.connect(self.panel.on_cgtw_task_changed) 
        self.status_combo_box = TaskStatusComboBox()
        utils.MouseWheelGuard.prevent(self.status_combo_box)
        self.status_combo_box.setItemDelegate(CustomComboDelegate(self.status_combo_box))
        self.status_combo_box.setMaximumWidth(150)
        self.task_preview = GraphicLabel(SVG.get("photo"), (72, 72))
        self.task_preview.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)

        self.tags_label = QtWidgets.QLabel("Add tags")
        self.tags_label.setProperty("heading", "h3")
        self.tags_help = GraphicLabel(SVG.get("help"), (22,22))
        self.tags_help.setToolTip("Add tags for current selected task to add more context on CGTW publish")
        self.tag_edit = TagTokenInputEdit()
        
        # --- slack widgets ---
        self.slack_icon = GraphicLabel(SVG.get("slack"), (36,36))
        self.slack_label = QtWidgets.QLabel("Slack")
        self.slack_label.setProperty("heading", "h2")
        self.slack_collapse_btn = GraphicButton(SVG.get("arrow drop down"))

        self.slack_channel_label = QtWidgets.QLabel("Channels")
        self.slack_channel_combo_box = ModernComboBox()
        utils.MouseWheelGuard.prevent(self.slack_channel_combo_box)
        self.slack_channel_combo_box.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)

        self.asset_type_label = QtWidgets.QLabel("Type")
        self.asset_type_btn_grp = QtWidgets.QButtonGroup()
        for type_name in self.panel.asset_type:             # even tho this class should be pure UI/mindless, for this special case we query it instead manually from panel.
            radio_btn = QtWidgets.QRadioButton(type_name)   # since for this project it will probably only not change in future
            self.slack_type_radio_btn.append(radio_btn)
            self.asset_type_btn_grp.addButton(radio_btn)

        self.mention_users_edit = UserTokenInputEdit("Mention User:")
        self.cc_users_edit = UserTokenInputEdit("CC User:")

        self.description_editor = text_editor.RichTextEdit(placeholder_text="Write Description Here...")
        self.description_editor.onAttachmentClicked.connect(self.panel.on_attachment_clicked)

        self.publish_btn = QtWidgets.QPushButton("Publish")
        self.publish_btn.setObjectName("publish-btn")
        self.publish_btn.clicked.connect(self.panel.request_publish)

    def initLayouts(self):
        # layouts
        self.main_layout = QtWidgets.QVBoxLayout(self.main_widget)
        self.main_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.file_layout = QtWidgets.QVBoxLayout(self.file_div_widget)
        self.file_header_layout = QtWidgets.QHBoxLayout()
        self.file_section_layout = QtWidgets.QHBoxLayout()
        self.file_section_layout.setSpacing(10)
        self.file_info_layout = QtWidgets.QVBoxLayout()
        self.filename_layout = QtWidgets.QHBoxLayout()
        self.filename_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.file_date_details_layout = QtWidgets.QHBoxLayout()
        self.file_browse_layout = QtWidgets.QHBoxLayout()

        self.CGTW_layout = QtWidgets.QVBoxLayout()
        self.CGTW_layout.setContentsMargins(10,10,10,0)
        self.CGTW_header_layout = QtWidgets.QHBoxLayout()
        self.CGTW_task_label_layout = QtWidgets.QHBoxLayout()
        self.CGTW_task_label_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.CGTW_task_section_layout = QtWidgets.QHBoxLayout()
        self.CGTW_task_left_layout = QtWidgets.QVBoxLayout()
        self.CGTW_tag_label_layout = QtWidgets.QHBoxLayout()
        
        self.slack_layout = QtWidgets.QVBoxLayout()
        self.slack_layout.setContentsMargins(10,10,10,0)
        self.slack_header_layout = QtWidgets.QHBoxLayout()
        self.slack_options_layout = QtWidgets.QHBoxLayout()
        self.slack_channel_options_layout = QtWidgets.QVBoxLayout()
        self.slack_type_options_layout = QtWidgets.QVBoxLayout()
        self.slack_type_radio_layout = QtWidgets.QHBoxLayout()
        self.slack_type_radio_layout.setSpacing(15)
        self.slack_type_radio_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)

        # arrange layout
        self.main_layout.addWidget(self.file_div_widget)
        self.file_layout.addLayout(self.file_header_layout)
        self.file_header_layout.addWidget(self.file_info_lbl)
        self.file_header_layout.addStretch()
        self.file_header_layout.addWidget(self.file_close_btn)
        self.file_layout.addLayout(self.file_section_layout)

        self.file_section_layout.addWidget(self.file_icon)
        self.file_section_layout.addLayout(self.file_info_layout)
        self.file_info_layout.addLayout(self.filename_layout)
        self.filename_layout.addWidget(self.filename_label)
        self.filename_layout.addWidget(self.file_size_label)
        self.file_info_layout.addLayout(self.file_date_details_layout)
        self.file_date_details_layout.addWidget(self.modified_info_label)
        self.file_layout.addLayout(self.file_browse_layout)
        self.file_browse_layout.addWidget(self.file_location_edit)
        self.file_browse_layout.addWidget(self.file_browser_btn)
        self.file_layout.addWidget(self.last_update_datetime_label)
        
        self.main_layout.addLayout(self.CGTW_layout)
        self.CGTW_layout.addLayout(self.CGTW_header_layout)
        self.CGTW_header_layout.addWidget(self.CGTW_icon)
        self.CGTW_header_layout.addWidget(self.CGTW_label)
        self.CGTW_header_layout.addSpacing(10)
        self.CGTW_header_layout.addWidget(self.cgtw_h_line)
        self.CGTW_header_layout.addWidget(self.CGTW_collapse_btn)
        self.CGTW_layout.addWidget(self.project_label)
        self.CGTW_layout.addWidget(self.project_combo_box)
        self.CGTW_layout.addLayout(self.CGTW_task_label_layout)
        self.CGTW_task_label_layout.addWidget(self.task_label)
        self.CGTW_task_label_layout.addWidget(self.task_count_label)
        self.CGTW_layout.addLayout(self.CGTW_task_section_layout)
        self.CGTW_task_section_layout.addLayout(self.CGTW_task_left_layout)
        self.CGTW_task_left_layout.addWidget(self.task_combo_box)
        self.CGTW_task_left_layout.addWidget(self.status_combo_box)
        self.CGTW_task_section_layout.addWidget(self.task_preview)
        self.CGTW_layout.addLayout(self.CGTW_tag_label_layout)
        self.CGTW_tag_label_layout.addWidget(self.tags_label)
        self.CGTW_tag_label_layout.addWidget(self.tags_help)
        self.CGTW_tag_label_layout.addStretch()
        self.CGTW_layout.addWidget(self.tag_edit)

        self.main_layout.addLayout(self.slack_layout)
        self.slack_layout.addLayout(self.slack_header_layout)
        self.slack_header_layout.addWidget(self.slack_icon)
        self.slack_header_layout.addWidget(self.slack_label)
        self.slack_header_layout.addSpacing(10)
        self.slack_header_layout.addWidget(self.slack_h_line)
        self.slack_header_layout.addWidget(self.slack_collapse_btn)
        self.slack_layout.addLayout(self.slack_options_layout)
        self.slack_options_layout.addLayout(self.slack_channel_options_layout)
        self.slack_options_layout.addSpacing(20)
        self.slack_options_layout.addLayout(self.slack_type_options_layout)
        self.slack_channel_options_layout.addWidget(self.slack_channel_label)
        self.slack_channel_options_layout.addWidget(self.slack_channel_combo_box)
        self.slack_type_options_layout.addWidget(self.asset_type_label)
        self.slack_type_options_layout.addLayout(self.slack_type_radio_layout)
        for btn in self.slack_type_radio_btn:
            self.slack_type_radio_layout.addWidget(btn)
        self.slack_layout.addWidget(self.mention_users_edit)
        self.slack_layout.addWidget(self.cc_users_edit)
        self.slack_layout.addWidget(self.description_editor)

        self.main_layout.addWidget(self.publish_btn)
        self.main_layout.addStretch()