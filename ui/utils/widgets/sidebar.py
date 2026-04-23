from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame

class Sidebar(QWidget):
    def __init__(self, title: str, subtitle: str, menu_items: list[tuple[str, callable]], logout_callback):
        super().__init__()
        self.setObjectName("sidebar")
        root = QVBoxLayout(self)

        brand = QFrame()
        brand_layout = QVBoxLayout(brand)
        title_label = QLabel(title)
        title_label.setObjectName("sidebarTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("pageSubtitle")
        brand_layout.addWidget(title_label)
        brand_layout.addWidget(subtitle_label)

        root.addWidget(brand)

        for text, callback in menu_items:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            root.addWidget(btn)

        root.addStretch()

        logout_btn = QPushButton("로그아웃")
        logout_btn.setObjectName("dangerButton")
        logout_btn.clicked.connect(logout_callback)
        root.addWidget(logout_btn)
