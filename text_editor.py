from PySide6 import QtGui, QtCore, QtWidgets
import utils, widgets, SVG, models
import re

class CustomTextEdit(QtWidgets.QTextEdit):
    imageDataInserted = QtCore.Signal(QtGui.QImage)
    fileInserted = QtCore.Signal(list)
    SlackUserRole = QtCore.Qt.ItemDataRole.UserRole + 1
    USER_PROPERTY_ID = QtGui.QTextFormat.Property.UserProperty + 1  # using QTextFormat property enum to ensure ID doesn't collide with qt internal ID
    def __init__(self, default_lines=3, max_lines=20, placeholder_text=""):
        super().__init__()
        self.default_lines = default_lines
        self.max_lines = max_lines  # allowed lines count until it shows scrollbar
        self.setPlaceholderText(placeholder_text)
        self.setAcceptRichText(False)
        self.document().documentLayout().documentSizeChanged.connect(self.update_height)
        self.update_height()

        # --- completer setup ---
        self._completer = None
        self.slack_completer_model = QtGui.QStandardItemModel()  # init our custom model, instead of using internal model (clear ownership/better auto completion in IDE) (not compulsory since we can use QCompleter().model())
        self.slack_completer = QtWidgets.QCompleter()
        self.slack_completer.setModel(self.slack_completer_model)
        self.set_completer(self.slack_completer)

    def set_completer(self, completer:QtWidgets.QCompleter):
        if self._completer:
            try:
                self._completer.activated.disconnect(self._insert_user_tag)
            except Exception as e:
                print(e) 

        self._completer = completer
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        self._completer.activated[QtCore.QModelIndex].connect(self._insert_user_tag)      # choose model index as the signal overload type

    def set_completer_model(self, data:list):
        sorted_usernames = sorted(data, key=str) #sort it first to match qt default behavior on caseInsensitive model (it will assume our model is sorted, its for perfomance reason)

        self.slack_completer_model.clear()
        for user in sorted_usernames:
            item = QtGui.QStandardItem(str(user))
            item.setData(user, self.SlackUserRole)
            self.slack_completer_model.appendRow(item)

    def keyPressEvent(self, event:QtGui.QKeyEvent):
        text_cursor = self.textCursor()
        text_cursor.beginEditBlock()
        key = event.key()
        try:
            # ------- 1. block specific key actions when completer is active -------
            if self._completer and self._completer.popup().isVisible():
                # The following keys are forwarded by the completer to the widget 
                if key in (QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Return, QtCore.Qt.Key.Key_Escape, QtCore.Qt.Key.Key_Tab, QtCore.Qt.Key.Key_Backtab):
                    event.ignore()
                    return  # let the completer do default behavior

            # ------- 2. check if cursor is affecting any user tag before calling super (determine whether we need to check for modified user tag or not) -------
            has_user_tag_affected = False
            USER_ID_Property = self.currentCharFormat().property(self.USER_PROPERTY_ID)
            if USER_ID_Property:
                has_user_tag_affected = True
            elif text_cursor.hasSelection():
                temp_cursor = self.textCursor()
                for i in range(temp_cursor.selectionStart(), temp_cursor.selectionEnd()):
                    temp_cursor.setPosition(i)
                    if temp_cursor.charFormat().hasProperty(self.USER_PROPERTY_ID):
                        has_user_tag_affected = True
                        break
                            
            # ------- 3. pass the key to text edit to handle -------
            super().keyPressEvent(event)

            # ------- 4. return here if no completer found (just as safeguard, even tho completer always initialize in __init__) -------
            if not self._completer: return
            
            # ------- 5 check if current cursor editing the user tag, and listen for changes (if different from the registered text, we remove the char format)
            completion_prefix = self.text_under_cursor()
            key_sequence = QtGui.QKeySequence(event.keyCombination())
            if has_user_tag_affected and not (key_sequence in (QtGui.QKeySequence.StandardKey.Undo, QtGui.QKeySequence.StandardKey.Redo)): # return if undo or redo operation to prevent issue when check_user_tag will messed up history
                registered_text = None
                if USER_ID_Property:
                    registered_text = USER_ID_Property.get("registered_text")
                else:
                    temp_cursor = self.textCursor()
                    if not temp_cursor.atEnd():
                        temp_cursor.movePosition(QtGui.QTextCursor.MoveOperation.Right)
                        if temp_cursor.charFormat().hasProperty(self.USER_PROPERTY_ID):
                            registered_text = temp_cursor.charFormat().property(self.USER_PROPERTY_ID).get("registered_text")
                if registered_text:
                    self.check_user_tag(text_cursor, registered_text)

            # ------- 6 hide completer if @ is not present before word or in event.text(), only way to show completer is by deliberately typing @
            if self.char_before_selection() != "@" and (event.text() != "@"):
                self._completer.popup().hide()
                return

            # ------- 7  updates the completer suggestions when the word prefix/typed is changing amd show the completer
            if completion_prefix != self._completer.completionPrefix(): 
                self._completer.setCompletionPrefix(completion_prefix)  
                self._completer.popup().setCurrentIndex(self._completer.completionModel().index(0,0))

            # ------- 8 finally show the completer UI
            cursor_rect = self.cursorRect()
            cursor_rect.setWidth(self._completer.popup().sizeHintForColumn(0) +     # get the longest visible word suggestion in column 0
                                self._completer.popup().verticalScrollBar().sizeHint().width())    # add extra width for vertical scrollbar so it doesnt overlap
            self._completer.complete(cursor_rect)   # show it

        except Exception as e :
            print("Error on key press > ", e)  

        finally:
            text_cursor.endEditBlock()
            self.setTextCursor(self.textCursor())   # set text cursor to tell qt layout where the correct cursor should be, preventing scrollbar keep snap to the top

    def check_user_tag(self, cursor:QtGui.QTextCursor, registered_text):
        """ Scan through block/paragraph and find fragment of user property and replace it with default char format if registered text not matching"""
        block = cursor.block()
        iteration = block.begin()   # will give iterator to iterate over each fragments
        while not iteration.atEnd():
            fragment = iteration.fragment()
            if fragment.isValid() and fragment.charFormat().hasProperty(self.USER_PROPERTY_ID):
                frag_start = fragment.position()
                frag_end = frag_start + fragment.length()
                
                if frag_start <= cursor.position() <= frag_end:
                    temp_cursor = QtGui.QTextCursor(self.document())
                    temp_cursor.setPosition(frag_start)
                    temp_cursor.setPosition(frag_end, QtGui.QTextCursor.MoveMode.KeepAnchor)
                    if temp_cursor.selectedText() != "@" + registered_text:
                        temp_cursor.setCharFormat(QtGui.QTextCharFormat())
            iteration += 1
        return 

    def focusInEvent(self, event):
        # redirect completer instance to bound to text edit (completer can be shared between multiple input widgets, so this make sure it will always connected to text edit when its gained focus)
        if self._completer:
            self._completer.setWidget(self) 
        return super().focusInEvent(event)
    
    def _insert_user_tag(self, model_index):
        """
        convert the current word to user tag char format, slot function of completer when activated
        """
        completion = model_index.data(QtCore.Qt.ItemDataRole.DisplayRole)   # get the display text from completer
        slack_user = model_index.data(self.SlackUserRole)
        if not self._completer:
            return
        text_cursor = self.textCursor() 
        text_cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfWord, QtGui.QTextCursor.MoveMode.MoveAnchor)
        text_cursor.movePosition(QtGui.QTextCursor.MoveOperation.StartOfWord, QtGui.QTextCursor.MoveMode.KeepAnchor)
        text_cursor.movePosition(QtGui.QTextCursor.MoveOperation.PreviousWord, QtGui.QTextCursor.MoveMode.KeepAnchor)

        text_cursor.beginEditBlock()
        try:
            text_cursor.insertText("@"+completion, self.create_user_char_format(completion, slack_user, "#10000")) # from active selection replace and insert completion
            text_cursor.setCharFormat(QtGui.QTextCharFormat())
            text_cursor.insertText(" ")
            self.setTextCursor(text_cursor)
        finally:
            text_cursor.endEditBlock()

    def text_under_cursor(self):
        text_cursor = self.textCursor() # retrieve a copy of current cursor, so select doesnt modifies or highlight the text
        text_cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        return text_cursor.selectedText()
    
    def char_before_selection(self):
        text_cursor = self.textCursor() # retrieve a copy of current cursor, so select doesnt modifies or highlight the text
        text_cursor.select(QtGui.QTextCursor.SelectionType.WordUnderCursor)
        start_pos = text_cursor.selectionStart()
        return self.document().characterAt(text_cursor.selectionStart()-1) if start_pos > 0 else ""

    def create_user_char_format(self, registered_text:str, slack_user, cgtw_id:str):
        """generate new instance of user tag char format, because its lightweight we dont need to worry about it"""
        format = QtGui.QTextCharFormat()
        text_color = QtGui.QColor.fromHsvF(QtGui.QColor(f"#{slack_user.color}").hueF(), 0.7, 0.73)   # use slack color for this app
        bg_color = QtGui.QColor(text_color)
        bg_color.setAlphaF(0.15)
        format.setForeground(text_color)
        format.setBackground(bg_color)
        format.setProperty(self.USER_PROPERTY_ID, { "registered_text": registered_text, "slack_user": slack_user, "cgtw_id": cgtw_id})
        format.setFontWeight(800)

        return format

    def update_height(self):
        if self.default_lines > self.max_lines:
            self.default_lines = self.max_lines
            
        font_metrics = self.fontMetrics()
        line_height = font_metrics.lineSpacing()
        doc_height = self.document().size().height()

        min_height = line_height*self.default_lines + 2
        max_height = line_height * self.max_lines + 2

        self.setFixedHeight(int(min(max(doc_height + 2, min_height), max_height))) # clamp the doc size so its not goes above max or below min height

    def canInsertFromMimeData(self, source):
        if source.hasImage():
            return True
        else:
            return super().canInsertFromMimeData(source)
    
    def insertFromMimeData(self, source):
        "we don't add the image to document/HTML, instead we wrap it as a signal"

        # this condition below run for example when taking screenshot or saving img data in clipboard
        if source.hasImage():
            image = source.imageData()
            if image.width() * image.height() > 64_000_000:    # 8K monitor size
                reply = utils.warning(self, "Warning", "image size exceeds 64 MB, proceed?", QtWidgets.QMessageBox.StandardButton.Yes)
                if reply != QtWidgets.QMessageBox.StandardButton.Yes:
                    return False
            self.imageDataInserted.emit(image)
            return

        elif source.hasUrls():
            files = []
            for url in source.urls():
                if url.isLocalFile():
                    # check if its file to proceed
                    path = url.toLocalFile()
                    file_info = QtCore.QFileInfo(path)
                    if file_info.exists() and file_info.isFile():
                        files.append(url.toLocalFile())
                    elif not file_info.isFile():
                        print("only accept file type ")   
                    elif not file_info.exists():
                        print("file path not exists > %s"%path)  
                    else:
                        print("can't proceed filepath > %s"%path) 
                else:
                    break   # break and let qt handle it
            else:
                # if all valid images, finish here (remember this is using for else logic)
                self.fileInserted.emit(files)
                return

        super().insertFromMimeData(source)

class RichTextEdit(QtWidgets.QWidget):
    IMAGE_EXTENSIONS = ['.jpg', '.png', '.bmp', '.jfif']
    MAX_ATTACHMENT = 10
    CHARACTER_LIMIT = 200 # slack API suggestion is 4000
    onAttachmentClicked = QtCore.Signal(object)
    def __init__(self, default_lines=3, max_lines=20, placeholder_text="", parent=None):
        super(RichTextEdit, self).__init__(parent)
        self._attachment_widgets = [] # contains all file and snapshot widget

        # text edit properties
        self.default_lines = default_lines
        self.max_lines = max_lines
        self.placeholder_text = placeholder_text

        self.initUI()

    @property
    def is_within_char_limit(self):
        if self.text_edit.document().characterCount() < self.CHARACTER_LIMIT:
            return True
        return False

    # slack block kit parser
    def parse_to_block_kit(self):
        """iterate through each docs block and each character, querying the text and its format"""

        line_separators = {"\u2028", "\u2029"}   # Unicode line separator / Unicode paragraph separator 
        text_elements = []
        block = self.text_edit.document().begin()    # return first text block
        while block.isValid():
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()

                if fragment.isValid():
                    text = fragment.text()
                    format = fragment.charFormat()

                    for char in line_separators:
                        text = text.replace(char, "\n")

                    # detect user tag
                    if format.hasProperty(self.text_edit.USER_PROPERTY_ID):
                        slack_user = format.property(self.text_edit.USER_PROPERTY_ID).get("slack_user")
                        if slack_user:
                            text_block = {
                                        "type" : "user",
                                        "user_id" : slack_user.id 
                                        }

                    else:
                        # assign each text format with its own parser function
                        is_bold = format.fontWeight() == QtGui.QFont.Bold
                        is_italic = format.fontItalic()
                        is_strike = format.fontStrikeOut()
                        is_underline = format.fontUnderline()
                        #is_code = format.font().family() == "Courier New"
                        
                        text_block = {
                                    "type" : "text",
                                    "text" : text,
                                    "style" : {
                                            "bold": is_bold,
                                            "italic": is_italic,
                                            "underline": is_underline,
                                            "strike": is_strike
                                        } 
                                    }
                    text_elements.append(text_block)
                iterator += 1
            
            block = block.next()
            if block.isValid():
                if text_elements:
                    existing_text = text_elements[-1]["text"]
                    existing_text += "\n"
                    text_elements[-1]["text"] = existing_text

        return {"type": "rich_text", 
                "elements": [
                        {
                            "type": "rich_text_quote",
                            "elements": text_elements
                        }
                    ]
                }

    def initUI(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(0,0,0,0)
        self.main_layout.setSpacing(0)
        self.utils_layout = QtWidgets.QHBoxLayout()

        self.init_formatting_toolbar()
        self.init_text_edit()

        # resources area (image, file, etc)
        self.resources_scroll = QtWidgets.QScrollArea()
        self.resources_scroll.hide()
        self.resources_scroll.setFixedHeight(self.resources_scroll.minimumSizeHint().height()+20+20) 
        self.resources_scroll_widget = QtWidgets.QWidget()
        self.resources_scroll.setWidget(self.resources_scroll_widget)
        self.resources_scroll.setWidgetResizable(True)
        self.resources_layout = QtWidgets.QHBoxLayout(self.resources_scroll_widget)
        self.resources_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.resources_layout.setContentsMargins(10,0,10,0)

        # utils section (e.g. custom btn/func and character limit hint)
        self.char_limit_hint = QtWidgets.QLabel("0")
        self.char_limit_hint.setProperty("font-color", "light-grey")
        self.text_edit.textChanged.connect(self._on_text_changed)
        
        # parent all widget to layout
        self.main_layout.addWidget(self.formatting_toolbar)
        self.main_layout.addWidget(self.text_edit)
        self.main_layout.addWidget(self.resources_scroll)
        self.main_layout.addLayout(self.utils_layout)

        #self.utils_layout.addWidget(self.add_attachment_btn)
        self.utils_layout.addStretch()
        self.utils_layout.addWidget(self.char_limit_hint)

        self.main_layout.addStretch()

    def init_formatting_toolbar(self):
        self.formatting_toolbar = QtWidgets.QToolBar("formatting")

        # Bold Action
        self.bold_action = QtGui.QAction("B", self)
        self.bold_action.setStatusTip("Bold")
        self.bold_action.setToolTip("Bold (Ctrl+B)")
        self.bold_action.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Weight.Bold))
        self.bold_action.setShortcut(QtGui.QKeySequence("Ctrl+B"))
        self.bold_action.setCheckable(True)
        self.bold_action.triggered.connect(self.toggle_bold)
        self.formatting_toolbar.addAction(self.bold_action)
        
        # Italic Action
        self.italic_action = QtGui.QAction("I", self)
        self.italic_action.setStatusTip("Italic")
        self.italic_action.setToolTip("Italic (Ctrl+I)")
        self.italic_action.setFont(QtGui.QFont("Arial", 10, italic=True))
        self.italic_action.setShortcut(QtGui.QKeySequence("Ctrl+I"))
        self.italic_action.setCheckable(True)
        self.italic_action.triggered.connect(self.toggle_italic)
        self.formatting_toolbar.addAction(self.italic_action)

        # Underline Action
        self.underline_action = QtGui.QAction("U", self)
        self.underline_action.setStatusTip("Underline")
        self.underline_action.setToolTip("Underline (Ctrl+U)")
        font = QtGui.QFont("Arial", 10)
        font.setUnderline(True)
        self.underline_action.setFont(font)
        self.underline_action.setShortcut(QtGui.QKeySequence("Ctrl+U"))
        self.underline_action.setCheckable(True)
        self.underline_action.triggered.connect(self.toggle_underline)
        self.formatting_toolbar.addAction(self.underline_action)

        # Strikethrough Action
        self.strike_action = QtGui.QAction("S", self)
        self.strike_action.setStatusTip("Strikethrough")
        self.strike_action.setToolTip("Strikethrough (Ctrl+Shift+X)")
        font = QtGui.QFont("Arial", 10)
        font.setStrikeOut(True)
        self.strike_action.setFont(font)
        self.strike_action.setShortcut(QtGui.QKeySequence("Ctrl+Shift+X"))
        self.strike_action.setCheckable(True)
        self.strike_action.triggered.connect(self.toggle_strike)
        self.formatting_toolbar.addAction(self.strike_action)

        # --- Separator to separate text formatting with extra action ---
        self.formatting_toolbar.addSeparator()

        # Attachment Action
        icon_img = utils.scale_image(SVG.get("attach file add"), (22, 22))
        self.attachment_action = QtGui.QAction(icon=QtGui.QPixmap.fromImage(icon_img), parent=self)
        self.attachment_action.setToolTip("Attach Files")
        self.attachment_action.triggered.connect(self.open_file_dialog)
        self.formatting_toolbar.addAction(self.attachment_action)

    def init_text_edit(self):
        self.text_edit = CustomTextEdit(self.default_lines, self.max_lines, self.placeholder_text) 
        self.text_edit.currentCharFormatChanged.connect(self.update_toolbar)
        self.text_edit.fileInserted.connect(self.attach_file)
        self.text_edit.imageDataInserted.connect(self.attach_image_data)
        #self.text_edit.setAutoFormatting(QtWidgets.QTextEdit.AutoFormattingFlag.AutoAll)   # example: when user type hyphen > it will auto convert to list

    def set_completer_model(self, data=None):
        if not data: 
            data = []
        self.text_edit.set_completer_model(data)

    def get_attachments(self):
        return [asset.attachment_obj for asset in self._attachment_widgets]

    def get_plain_text(self):
        return self.text_edit.toPlainText()

    def update_toolbar(self):
        if self.text_edit.currentCharFormat().hasProperty(self.text_edit.USER_PROPERTY_ID):
            self.formatting_toolbar.setEnabled(False)
            return
        else:
            self.formatting_toolbar.setEnabled(True)
        self.bold_action.setChecked(self.text_edit.fontWeight() == QtGui.QFont.Bold)
        self.italic_action.setChecked(self.text_edit.fontItalic())
        self.underline_action.setChecked(self.text_edit.fontUnderline())
        self.strike_action.setChecked(self.text_edit.currentCharFormat().fontStrikeOut())

    def _on_text_changed(self):
        count = self.text_edit.document().characterCount()
        
        if self.is_within_char_limit:
            self.char_limit_hint.setText(f"{count}/{self.CHARACTER_LIMIT}")
            self.char_limit_hint.setStyleSheet("")
        else:
            self.char_limit_hint.setText(f"{count}/{self.CHARACTER_LIMIT}")
            self.char_limit_hint.setStyleSheet("background-color:#e64e5b; color:#edebeb")

    def toggle_bold(self):
        format = QtGui.QTextCharFormat()
        is_bold = self.text_edit.fontWeight() >= QtGui.QFont.Weight.Bold
        weight = QtGui.QFont.Weight.Normal if is_bold else QtGui.QFont.Weight.Bold
        format.setFontWeight(weight)
        self.merge_format_to_selection(format)

    def toggle_italic(self):
        format = QtGui.QTextCharFormat()
        format.setFontItalic(not self.text_edit.fontItalic())
        self.merge_format_to_selection(format)

    def toggle_underline(self):
        format = QtGui.QTextCharFormat()
        format.setFontUnderline(not self.text_edit.fontUnderline())
        self.merge_format_to_selection(format)

    def toggle_strike(self):
        format = QtGui.QTextCharFormat()
        format.setFontStrikeOut(not self.text_edit.currentCharFormat().fontStrikeOut())
        self.merge_format_to_selection(format)

    def merge_format_to_selection(self, format):
        cursor = self.text_edit.textCursor()
        if not cursor.hasSelection():
            self.text_edit.mergeCurrentCharFormat(format) # using merge to not override any existing formatting (say we using italic and bold at same time, it wil allow both format works)
        else:
            cursor.mergeCharFormat(format)

    def add_attachment(self, attachment_class, *args):
        if len(self._attachment_widgets) == self.MAX_ATTACHMENT:
            print("max limit for attachment reached")
            return  False 
        attachment_obj = attachment_class(*args)
        if attachment_obj.size() > 10_000_000:
            print("can't upload file more than 10 MB")
            return False 
        widget = widgets.AttachmentWidget(attachment_obj)
        self.resources_layout.addWidget(widget)
        self._attachment_widgets.append(widget)
        widget.onRemove.connect(self.remove_attachment)
        widget.onAttachmentClicked.connect(self.on_attachment_clicked)
        if not self.resources_scroll.isVisible():
            self.resources_scroll.show()
        return True

    def remove_attachment(self, widget):
        if widget in self._attachment_widgets:
            self._attachment_widgets.remove(widget)
            widget.setParent(None)  # use this to remove immediately (delete Later is deferred)
            widget.deleteLater()

            if self._attachment_widgets:
                self.resources_layout.activate()    # force qt recalculate position of widget, so below can get correct and latest data 
                hovered_widget = QtWidgets.QApplication.widgetAt(QtGui.QCursor.pos())
                if hovered_widget in self._attachment_widgets:
                    try:
                        hovered_widget.enterEvent()   # not so ideal, perhaps there is better way?
                    except Exception as e:
                        print(e)
            else:
                self.resources_scroll.hide()
    
    def open_file_dialog(self):
        fnames, filter = QtWidgets.QFileDialog.getOpenFileNames(self, "Open", filter=("All Files (*)"))
        for filepath in fnames:
            if not self.add_attachment(models.FileAttachment, filepath):
                break

    def get_attachment_with_preview(self):
        return [w.attachment_obj for w in self._attachment_widgets if w.attachment_obj.preview()]

    def attach_file(self, filepaths):
        for path in filepaths:
            if not self.add_attachment(models.FileAttachment, path):
                break

    def attach_image_data(self, image):
        self.add_attachment(models.SnapshotAttachment, image, len(self.get_attachment_with_preview()))

    def on_attachment_clicked(self, preview):
        self.onAttachmentClicked.emit(preview)

    def clear(self):
        """ clear both text editor and attachments """
        for widget in self._attachment_widgets:
            self._attachment_widgets.remove(widget)
            widget.deleteLater()
            self.resources_scroll.hide()
        self.text_edit.clear()
    