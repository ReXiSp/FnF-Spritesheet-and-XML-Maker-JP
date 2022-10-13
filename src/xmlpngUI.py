import sys
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QAction, QActionGroup, QApplication, QGridLayout, QInputDialog, QLineEdit, QMainWindow, QMessageBox, QProgressDialog, QPushButton, QSpacerItem, QLabel, QFileDialog
from os import path
from animationwindow import AnimationView
import engine.icongridutils as icongridutils
import engine.spritesheetutils as spritesheetutils
# from frameorderscreen import FrameOrderScreen
from xmltablewindow import XMLTableView
import json

import engine.xmlpngengine as xmlpngengine
from mainUI import Ui_MainWindow
from spriteframe import SpriteFrame
from utils import SPRITEFRAME_SIZE, get_stylesheet_from_file
from settingswindow import SettingsWindow


def display_progress_bar(parent, title="Sample text", startlim=0, endlim=100):
    def update_prog_bar(progress, progresstext):
        progbar.setValue(progress)
        progbar.setLabel(QLabel(progresstext))
    progbar = QProgressDialog(title, None, startlim, endlim, parent)
    progbar.setWindowModality(Qt.WindowModal)
    progbar.show()

    return update_prog_bar, progbar

def set_preferences(prefdict):
    try:
        with open('preferences.json', 'w') as f:
            json.dump(prefdict, f)
    except Exception as e:
        with open("error.log", 'a') as errlog:
            errlog.write(str(e))

class MyApp(QMainWindow):
    def __init__(self, prefs):
        super().__init__()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("XML作成支援ツール")

        self.ui.generatexml_btn.clicked.connect(self.generate_xml)
        self.ui.actionExport_as_Spritesheet_and_XML.triggered.connect(self.generate_xml)
        self.ui.actionExport_induvidual_images.triggered.connect(self.export_bunch_of_imgs)
        self.ui.frames_area.setWidgetResizable(True)
        self.frames_layout = QGridLayout(self.ui.sprite_frame_content)
        self.ui.frames_area.setWidget(self.ui.sprite_frame_content)

        self.num_labels = 0
        self.labels = []
        self.selected_labels = []
        # self.frame_dict = {} # dict< pose_name: str -> frames: list[SpriteFrame] >

        self.add_img_button = QPushButton()
        self.add_img_button.setIcon(QIcon("./assets/AddImg.png"))
        self.add_img_button.setGeometry(0, 0, SPRITEFRAME_SIZE, SPRITEFRAME_SIZE)
        self.add_img_button.setFixedSize(QSize(SPRITEFRAME_SIZE, SPRITEFRAME_SIZE))
        self.add_img_button.setIconSize(QSize(SPRITEFRAME_SIZE, SPRITEFRAME_SIZE))
        self.add_img_button.clicked.connect(self.open_frame_imgs)

        self.frames_layout.addWidget(self.add_img_button, 0, 0, Qt.AlignmentFlag(0x1|0x20))
        self.ui.myTabs.setCurrentIndex(0)

        self.setWindowIcon(QIcon("./assets/appicon.png"))
        self.icongrid_zoom = 1
        self.ui.uploadicongrid_btn.clicked.connect(self.uploadIconGrid)
        self.ui.actionImport_IconGrid.triggered.connect(self.uploadIconGrid)
        self.ui.generateicongrid_btn.clicked.connect(self.getNewIconGrid)
        self.ui.uploadicons_btn.clicked.connect(self.appendIcon)
        self.ui.actionImport_Icons.triggered.connect(self.appendIcon)
        self.ui.actionClear_IconGrid.triggered.connect(self.clearIconGrid)
        self.ui.actionClear_Icon_selection.triggered.connect(self.clearSelectedIcons)

        self.action_zoom_in = QAction(self.ui.icongrid_holder_label)
        self.ui.icongrid_holder_label.addAction(self.action_zoom_in)
        self.action_zoom_in.triggered.connect(self.zoomInPixmap)
        self.action_zoom_in.setShortcut("Ctrl+i")

        self.action_zoom_out = QAction(self.ui.icongrid_holder_label)
        self.ui.icongrid_holder_label.addAction(self.action_zoom_out)
        self.action_zoom_out.triggered.connect(self.zoomOutPixmap)
        self.action_zoom_out.setShortcut("Ctrl+o")

        self.ui.zoom_label.setText("ズーム: 100%")

        self.iconpaths = []
        self.icongrid_path = ""

        self.ui.posename_btn.clicked.connect(self.setAnimationNames)
        self.ui.posename_btn.setDisabled(True)
        self.ui.charname_textbox.textChanged.connect(self.onCharacterNameChange)

        self.num_cols = 6
        self.num_rows = 1

        self.ui.actionImport_Images.triggered.connect(self.open_frame_imgs)
        self.ui.action_import_existing.triggered.connect(self.open_existing_spsh_xml)
        self.ui.actionImport_from_GIF.triggered.connect(self.open_gif)

        self.num_rows = 1 + self.num_labels//self.num_cols
        
        for i in range(self.num_cols):
            self.frames_layout.setColumnMinimumWidth(i, 0)
            self.frames_layout.setColumnStretch(i, 0)
        for i in range(self.num_rows):
            self.frames_layout.setRowMinimumHeight(i, 0)
            self.frames_layout.setRowStretch(i, 0)
        
        vspcr = QSpacerItem(1, 1)
        self.frames_layout.addItem(vspcr, self.num_rows, 0, 1, 4)

        hspcr = QSpacerItem(1, 1)
        self.frames_layout.addItem(hspcr, 0, self.num_cols, self.num_rows, 1)

        self.ui.actionClear_Spritesheet_Grid.triggered.connect(self.clear_spriteframe_grid)
        self.ui.myTabs.currentChanged.connect(self.handle_tab_change)
        self.ui.spsh_settings_btn.clicked.connect(self.show_settings)

        self.settings_widget = SettingsWindow()

        self.anim_view_window = AnimationView()
        self.ui.actionPreview_Animation.triggered.connect(self.show_anim_preview)
        self.ui.actionPreview_Animation.setEnabled(len(self.labels) > 0)
        # adding a QActionGroup at runtime :/
        darkmode_action_group = QActionGroup(self.ui.menuDefault_Dark_mode)
        theme_opts = ["デフォルト", "ダーク"]
        checked_action = "デフォルト" if prefs.get("theme", 'default') != 'dark' else "ダーク"
        for opt in theme_opts:
            action = QAction(opt, self.ui.menuDefault_Dark_mode, checkable=True, checked=(opt == checked_action))
            self.ui.menuDefault_Dark_mode.addAction(action)
            darkmode_action_group.addAction(action)
        darkmode_action_group.setExclusive(True)
        darkmode_action_group.triggered.connect(self.set_dark_mode)
        
        self.xml_table = XMLTableView(['画像のパス', 'Name', 'Width', 'Height', 'FrameX', 'FrameY', 'FrameWidth', 'FrameHeight'])
        self.ui.actionView_XML_structure.triggered.connect(self.show_table_view)
        self.ui.actionView_XML_structure.setEnabled(len(self.labels) > 0)
        self.ui.actionFlipX.triggered.connect(lambda: self.flip_labels('X'))
        self.ui.actionFlipY.triggered.connect(lambda: self.flip_labels('Y'))

        self.ui.use_psychengine_checkbox.clicked.connect(self.handle_psychengine_checkbox)

        # self.frame_order_screen = FrameOrderScreen()
        # self.ui.actionChange_Frame_Ordering.triggered.connect(self.show_frame_order_screen)
        # self.ui.actionChange_Frame_Ordering.setEnabled(len(self.labels) > 0)
        
        # Note: Add any extra windows before this if your want the themes to apply to them
        if prefs.get("theme", 'default') == 'dark':
            self.set_theme(get_stylesheet_from_file("assets/app-styles.qss"))
        
    
    def ranged_selection_handler(self, selected_spriteframe):
        first_selected_spriteframe = None
        for sprf in self.labels:
            if sprf == selected_spriteframe:
                break

            if sprf.select_checkbox.checkState() != 0 and sprf != selected_spriteframe:
                first_selected_spriteframe = sprf
                break
        
        if first_selected_spriteframe is not None:
            start_selecting = False
            for sprf in self.labels:
                if sprf == first_selected_spriteframe:
                    start_selecting = True
                
                if start_selecting:
                    # checks the box and adds it to the selected list
                    sprf.select_checkbox.setChecked(1)
                
                if sprf == selected_spriteframe:
                    break
    
    def ranged_deletion_handler(self, selected_spriteframe):
        first_selected_spriteframe = None
        for sprf in self.labels:
            if sprf == selected_spriteframe:
                break

            if sprf.select_checkbox.checkState() != 0 and sprf != selected_spriteframe:
                first_selected_spriteframe = sprf
                break
        
        if first_selected_spriteframe is not None:
            start_selecting = False
            for sprf in self.labels:
                if sprf == first_selected_spriteframe:
                    start_selecting = True
                
                if start_selecting:
                    # unchecks the box and removes it from the selected list
                    sprf.select_checkbox.setChecked(0)
                
                if sprf == selected_spriteframe:
                    break
    

    def open_gif(self):
        gifpath = self.get_asset_path("GIFを選択...", "GIF画像 (*.gif)")
        if gifpath != '':
            update_prog_bar, progbar = display_progress_bar(self, "フレームを追加中....")
            QApplication.processEvents()
            
            sprites = spritesheetutils.get_gif_frames(gifpath, update_prog_bar)
            for i, spfr in enumerate(sprites):
                spfr.frameparent = self
                self.add_spriteframe(spfr)
                update_prog_bar(50 + ((i+1)*50//len(sprites)), f"フレームを{gifpath}から追加しました")
            progbar.close()
            
            self.ui.posename_btn.setDisabled(self.num_labels <= 0)

    def handle_psychengine_checkbox(self, checked):
        self.ui.uploadicongrid_btn.setEnabled(not checked)
    
    # def show_frame_order_screen(self):
        # self.frame_order_screen.set_frame_dict(self.frame_dict)
        # self.frame_order_screen.show()
    
    def flip_labels(self, dxn='X'):
        for lab in self.selected_labels:
            lab.flip_img(dxn)
        
        for lab in list(self.selected_labels):
            # this automatically removes it from self.selected_labels
            lab.select_checkbox.setChecked(False)

    def show_table_view(self):
        print("Showing table view...")
        self.xml_table.fill_data(self.labels)
        self.xml_table.show()

    def set_dark_mode(self, event):
        if event.text() == "ダーク":
            styles = get_stylesheet_from_file("./assets/app-styles.qss")
            self.set_theme(styles)
        else:
            self.set_theme("")
    
    def set_theme(self, stylestr):
        self.setStyleSheet(stylestr)
        self.settings_widget.setStyleSheet(stylestr)
        self.anim_view_window.setStyleSheet(stylestr)
        self.xml_table.setStyleSheet(stylestr)
        # self.frame_order_screen.setStyleSheet(stylestr)
        if stylestr == "":
            set_preferences({ "theme":"default" })
        else:
            set_preferences({ "theme":"dark" })

    def show_anim_preview(self):
        self.anim_view_window.parse_and_load_frames(self.labels)
        self.anim_view_window.show()
    
    def show_settings(self):
        self.settings_widget.show()

    def handle_tab_change(self, newtabind):
        self.ui.actionClear_Spritesheet_Grid.setDisabled(newtabind != 0)
        self.ui.action_import_existing.setDisabled(newtabind != 0)
        self.ui.actionImport_from_GIF.setDisabled(newtabind != 0)
        self.ui.actionImport_Images.setDisabled(newtabind != 0)
        self.ui.actionEdit_Frame_Properties.setDisabled(newtabind != 0 or len(self.selected_labels) <= 0)
        self.ui.menuExport.setDisabled(newtabind != 0)
        self.ui.menuEdit_Selected_Images.setDisabled(newtabind != 0)

        self.ui.actionImport_IconGrid.setDisabled(newtabind != 1)
        self.ui.actionImport_Icons.setDisabled(newtabind != 1)
        self.ui.actionClear_IconGrid.setDisabled(newtabind != 1)
        self.ui.actionClear_Icon_selection.setDisabled(newtabind != 1)
    
    def onCharacterNameChange(self):
        for label in self.labels:
            label.img_label.setToolTip(label.get_tooltip_string(self))
    
    def clear_spriteframe_grid(self):
        labs = list(self.labels)
        for lab in labs:
            lab.remove_self(self)
        self.ui.actionEdit_Frame_Properties.setDisabled(len(self.selected_labels) <= 0)
    
    def resizeEvent(self, a0):
        w = self.width()
        # print("Current width", w)
        if w < 1228:
            self.num_cols = 6
        elif 1228 <= w <= 1652:
            self.num_cols = 8
        else:
            self.num_cols = 12
        self.re_render_grid()
        return super().resizeEvent(a0)
    
    def open_existing_spsh_xml(self):
        imgpath = self.get_asset_path("スプライトシートの画像を選択...", "スプライトシート (*.png)")

        if imgpath != '':
            xmlpath = self.get_asset_path("スプライトシートのXMLを選択...", "スプライトシート (*.xml)")
            if xmlpath != '':
                trubasenamefn = lambda fpath: path.basename(fpath).split('.')[0]
                charname = trubasenamefn(xmlpath)
                if trubasenamefn(imgpath) != trubasenamefn(xmlpath):
                    self.msgbox = QMessageBox(self)
                    self.msgbox.setWindowTitle("Conflicting file names")
                    self.msgbox.setText("The Spritesheet and the XML file have different file names.\nThe character name will not be auto-filled")
                    self.msgbox.setIcon(QMessageBox.Warning)
                    self.msgbox.addButton("OK", QMessageBox.YesRole)
                    cancel_import = self.msgbox.addButton("キャンセル", QMessageBox.NoRole)
                    x = self.msgbox.exec_()
                    clickedbtn = self.msgbox.clickedButton()
                    if clickedbtn == cancel_import:
                        return
                    charname = self.ui.charname_textbox.text() # trubasenamefn(imgpath) if clickedbtn == usespsh else trubasenamefn(xmlpath)
                    print("[DEBUG] Exit status of msgbox: "+str(x))


                update_prog_bar, progbar = display_progress_bar(self, "フレームを追加中....")
                QApplication.processEvents()

                sprites = spritesheetutils.split_spsh(imgpath, xmlpath, update_prog_bar)
                for i, spfr in enumerate(sprites):
                    spfr.frameparent = self
                    self.add_spriteframe(spfr)
                    update_prog_bar(50 + ((i+1)*50//len(sprites)), f"フレームを{imgpath}から追加しました")
                progbar.close()
                
                self.ui.posename_btn.setDisabled(self.num_labels <= 0)
                
                self.ui.charname_textbox.setText(charname)

        
    
    def open_frame_imgs(self):
        imgpaths = self.get_asset_path("スプライトの画像を選択...", "スプライト (*.png)", True)

        if imgpaths:
            update_prog_bar, progbar = display_progress_bar(self, "スプライトをインポート中....", 0, len(imgpaths))
            QApplication.processEvents()

            for i, pth in enumerate(imgpaths):
                # self.add_img(pth)
                self.add_spriteframe(SpriteFrame(self, pth))
                update_prog_bar(i+1, f"フレームを{pth}から追加しました")
            progbar.close()
        
        if len(self.labels) > 0:
            self.ui.posename_btn.setDisabled(False)
    
    def add_spriteframe(self, sp):
        self.num_rows = 1 + self.num_labels//self.num_cols
        
        self.frames_layout.setRowMinimumHeight(self.num_rows - 1, 0)
        self.frames_layout.setRowStretch(self.num_rows - 1, 0)
        
        vspcr = QSpacerItem(1, 1)
        self.frames_layout.addItem(vspcr, self.num_rows, 0, 1, 4)

        hspcr = QSpacerItem(1, 1)
        self.frames_layout.addItem(hspcr, 0, self.num_cols, self.num_rows, 1)
        
        self.labels.append(sp)
        self.frames_layout.removeWidget(self.add_img_button)
        self.frames_layout.addWidget(self.labels[-1], self.num_labels // self.num_cols, self.num_labels % self.num_cols, Qt.AlignmentFlag(0x1|0x20))
        self.num_labels += 1
        self.frames_layout.addWidget(self.add_img_button, self.num_labels // self.num_cols, self.num_labels % self.num_cols, Qt.AlignmentFlag(0x1|0x20))
        self.ui.actionPreview_Animation.setEnabled(len(self.labels) > 0)
        self.ui.actionView_XML_structure.setEnabled(len(self.labels) > 0)
        # self.ui.actionChange_Frame_Ordering.setEnabled(len(self.labels) > 0)
        
        # self.update_frame_dict(sp.img_xml_data.pose_name, sp)
    
    def update_frame_dict(self, key, val, remove=False):
        # TODO
        return
    
    def re_render_grid(self):
        self.num_rows = 1 + self.num_labels//self.num_cols
        for i in range(self.num_cols):
            self.frames_layout.setColumnMinimumWidth(i, 0)
            self.frames_layout.setColumnStretch(i, 0)
        for i in range(self.num_rows):
            self.frames_layout.setRowMinimumHeight(i, 0)
            self.frames_layout.setRowStretch(i, 0)

        vspcr = QSpacerItem(1, 1)
        self.frames_layout.addItem(vspcr, self.num_rows, 0, 1, 4)

        hspcr = QSpacerItem(1, 1)
        self.frames_layout.addItem(hspcr, 0, self.num_cols, self.num_rows, 1)
        
        for i, sp in enumerate(self.labels):
            self.frames_layout.addWidget(sp, i//self.num_cols, i%self.num_cols, Qt.AlignmentFlag(0x1|0x20))
        self.frames_layout.removeWidget(self.add_img_button)
        self.frames_layout.addWidget(self.add_img_button, self.num_labels // self.num_cols, self.num_labels % self.num_cols, Qt.AlignmentFlag(0x1|0x20))
    
    def export_bunch_of_imgs(self):
        savedir = QFileDialog.getExistingDirectory(caption="Save image sequence to...")
        updatefn, progbar = display_progress_bar(self, "Exporting Image Sequence", startlim=0, endlim=len(self.labels))
        QApplication.processEvents()
        
        errmsg = xmlpngengine.save_img_sequence(self.labels, savedir, updatefn)
        progbar.close()
        if errmsg:
            self.display_msg_box("エラー", text=f"エラーが発生しました: {errmsg}", icon=QMessageBox.Critical)
        else:
            self.display_msg_box("成功！", text="画像の保存は正常に完了しました！", icon=QMessageBox.Information)
    
    def generate_xml(self):
        charname = self.ui.charname_textbox.text()
        charname = charname.strip()
        if self.num_labels > 0 and charname != '':
            savedir = QFileDialog.getExistingDirectory(caption="ファイルを保存...")
            print("Stuff saved to: ", savedir)
            if savedir != '':
                update_prog_bar, progbar = display_progress_bar(self, "生成中....", 0, len(self.labels))
                QApplication.processEvents()
                
                statuscode, errmsg = xmlpngengine.make_png_xml(
                    self.labels, 
                    savedir, 
                    charname, 
                    update_prog_bar
                )
                progbar.close()
                if errmsg is None:
                    self.display_msg_box(
                        window_title="完了！", 
                        text="ファイルは正常に生成されました！",
                        icon=QMessageBox.Information
                    )
                else:
                    self.display_msg_box(
                        window_title="エラー",
                        text=("何かのエラーが発生しました！ エラー内容: " + errmsg),
                        icon=QMessageBox.Critical
                    )
        else:
            errtxt = "フレームを追加してください。" if self.num_labels <= 0 else "キャラクター名を設定してください。"
            self.display_msg_box(
                window_title="エラー", 
                text=errtxt,
                icon=QMessageBox.Critical
            )
    
    def zoomInPixmap(self):
        if self.icongrid_path and self.icongrid_zoom <= 5:
            self.icongrid_zoom *= 1.1
            icongrid_pixmap = QPixmap(self.icongrid_path)
            w = icongrid_pixmap.width()
            h = icongrid_pixmap.height()
            icongrid_pixmap = icongrid_pixmap.scaled(int(w*self.icongrid_zoom), int(h*self.icongrid_zoom), 1)
            self.ui.icongrid_holder_label.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
            self.ui.scrollAreaWidgetContents_2.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
            self.ui.icongrid_holder_label.setPixmap(icongrid_pixmap)
            self.ui.zoom_label.setText("ズーム: %.2f %%" % (self.icongrid_zoom*100))


    def zoomOutPixmap(self):
        if self.icongrid_path and self.icongrid_zoom >= 0.125:
            self.icongrid_zoom /= 1.1
            icongrid_pixmap = QPixmap(self.icongrid_path)
            w = icongrid_pixmap.width()
            h = icongrid_pixmap.height()
            icongrid_pixmap = icongrid_pixmap.scaled(int(w*self.icongrid_zoom), int(h*self.icongrid_zoom), 1)
            self.ui.icongrid_holder_label.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
            self.ui.scrollAreaWidgetContents_2.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
            self.ui.icongrid_holder_label.setPixmap(icongrid_pixmap)
            self.ui.zoom_label.setText("ズーム: %.2f %%" % (self.icongrid_zoom*100))
    
    def uploadIconGrid(self):
        print("アイコングリッドをアップロード中...")
        self.icongrid_path = self.get_asset_path("アイコングリッドを選択...", "グリッド (*.png)")
        icongrid_pixmap = QPixmap(self.icongrid_path)
        self.ui.icongrid_holder_label.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
        self.ui.scrollAreaWidgetContents_2.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
        self.ui.icongrid_holder_label.setPixmap(icongrid_pixmap)
    
    def clearIconGrid(self):
        self.icongrid_path = ""
        self.ui.icongrid_holder_label.clear()
    
    def getNewIconGrid(self):
        if self.ui.use_psychengine_checkbox.isChecked():
            if len(self.iconpaths) > 0:
                print("Psych Engine用のアイコンを生成....")
                savepath, _ = QFileDialog.getSaveFileName(self, "名前を付けて保存", filter="画像 (*.png)")

                stat, problemimg, exception_msg = icongridutils.makePsychEngineIconGrid(self.iconpaths, savepath)

                if exception_msg is not None:
                    self.display_msg_box(
                        window_title="エラー", 
                        text=f"エラーが発生しました: {exception_msg}",
                        icon=QMessageBox.Critical
                    )
                else:
                    if stat == 0:
                        self.display_msg_box(
                            window_title="完了！", 
                            text="アイコングリッドは正常に生成されました！",
                            icon=QMessageBox.Information
                        )
                        # display final image onto the icon display area 
                        icongrid_pixmap = QPixmap(savepath)
                        self.ui.icongrid_holder_label.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
                        self.ui.scrollAreaWidgetContents_2.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
                        self.ui.icongrid_holder_label.setPixmap(icongrid_pixmap)
                    elif stat == 1:
                        self.display_msg_box(
                            window_title="アイコン画像のエラー",
                            text=f"{problemimg} 150x150より大きいので、最後のグリッドに追加することはできません。\nこのアイコンは含まれずに生成されました",
                            icon=QMessageBox.Warning
                        )
            else:
                self.display_msg_box(
                    window_title="エラー", 
                    text="アイコンを選択してください。",
                    icon=QMessageBox.Critical
                )
            
            # no need to continue past this if in psych-engine mode
            return
        
        if self.icongrid_path != '' and len(self.iconpaths) > 0:
            print("Valid!")
            # savedir = QFileDialog.getExistingDirectory(caption="Save New Icongrid to...")
            # if savedir != '':
            stat, newinds, problemimg, exception_msg = icongridutils.appendIconToGrid(self.icongrid_path, self.iconpaths) #, savedir)
            print("[DEBUG] Function finished with status: ", stat)
            errmsgs = [
                'アイコングリッドが一杯で、新しいアイコンを挿入できません。', 
                '{}のサイズは非常に大きいです。150x150が上限です。',
                'アイコンを挿入する適切な場所が見つかりません。'
            ]

            if exception_msg is not None:
                self.display_msg_box(
                    window_title="エラーが発生しました", 
                    text=("例外(エラー)が発生しました\nエラー内容:\n"+exception_msg),
                    icon=QMessageBox.Critical
                )
            else:
                if stat == 0:
                    self.display_msg_box(
                        window_title="完了！", 
                        text="アイコングリッドが正常に生成されました！\nあなたのアイコンのインデックスは{}です。".format(newinds),
                        icon=QMessageBox.Information
                    )
                elif stat == 4:
                    self.display_msg_box(
                        window_title="警告！", 
                        text="アイコンが150×150より小さいです！\nしかし、アイコングリッドは生成されました。(アイコンは微調整されました。) \nYour icon's indices: {}".format(newinds),
                        icon=QMessageBox.Warning
                    )
                else:
                    self.display_msg_box(
                        window_title="エラー", 
                        text=errmsgs[stat - 1].format(problemimg),
                        icon=QMessageBox.Critical
                )
            icongrid_pixmap = QPixmap(self.icongrid_path)
            self.ui.icongrid_holder_label.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
            self.ui.scrollAreaWidgetContents_2.setFixedSize(icongrid_pixmap.width(), icongrid_pixmap.height())
            self.ui.icongrid_holder_label.setPixmap(icongrid_pixmap)
        else:
            errtxt = "アイコングリッドの画像を追加してください" if self.icongrid_path == '' else "アイコンを追加して下さい"
            self.display_msg_box(
                window_title="エラー", 
                text=errtxt,
                icon=QMessageBox.Critical
            )
    
    def appendIcon(self):
        print("Appending icon")
        self.iconpaths = self.get_asset_path("アイコンを選択...", "アイコン (*.png)", True)
        print("Got icon: ", self.iconpaths)
        if len(self.iconpaths) > 0:
            print("Valid selected")
            self.ui.iconselected_label.setText("追加されたアイコンの数:\n{}".format(len(self.iconpaths)))
        else:
            self.ui.iconselected_label.setText("追加されたアイコンの数:\n0")
    
    def clearSelectedIcons(self):
        self.iconpaths = []
        self.ui.iconselected_label.setText("選択されたアイコンの数:\n{}".format(len(self.iconpaths)))

    def setAnimationNames(self):
        if len(self.selected_labels) == 0:
            self.display_msg_box(window_title="エラー", text="名前を変更するフレームにチェックを入れてください。", icon=QMessageBox.Critical)
        else:
            text, okPressed = QInputDialog.getText(self, "アニメーション (ポーズ) の名前を変更する", "設定するアニメーション (ポーズ) の名前:"+(" "*50), QLineEdit.Normal) # very hack-y soln but it works!
            if okPressed and text != '':
                print("new pose prefix = ", text)
                for label in self.selected_labels:
                    # self.update_frame_dict(label.img_xml_data.pose_name, label, remove=True)
                    label.data.pose_name = text
                    label.modified = True
                    # self.update_frame_dict(text, label)
                    label.img_label.setToolTip(label.get_tooltip_string(self))
                
                for label in list(self.selected_labels):
                    # this automatically removes it from self.selected_labels
                    label.select_checkbox.setChecked(False)
            else:
                print("Cancel pressed!")
    
    def display_msg_box(self, window_title="MessageBox", text="Text Here", icon=None):
        self.msgbox = QMessageBox(self)
        self.msgbox.setWindowTitle(window_title)
        self.msgbox.setText(text)
        if not icon:
            self.msgbox.setIcon(QMessageBox.Information)
        else:
            self.msgbox.setIcon(icon)
        x = self.msgbox.exec_()
        print("[DEBUG] Exit status of msgbox: "+str(x))
    
    def get_asset_path(self, wintitle="Sample", fileformat=None, multiple=False):
        if multiple:
            return QFileDialog.getOpenFileNames(
                caption=wintitle, 
                filter=fileformat,
            )[0]
        else:
            return QFileDialog.getOpenFileName(
                caption=wintitle, 
                filter=fileformat,
            )[0]




if __name__ == '__main__':
    app = QApplication(sys.argv)

    prefs = None
    try:
        with open('preferences.json') as f:
            prefs = json.load(f)
    except FileNotFoundError as fnfe:
        with open("error.log", 'a') as errlog:
            errlog.write(str(fnfe))
        
        with open('preferences.json', 'w') as f:
            prefs = { "theme":"default" }
            json.dump(prefs, f)
    
    myapp = MyApp(prefs)
    myapp.show()

    try:
        sys.exit(app.exec_())
    except SystemExit:
        print("Closing...")