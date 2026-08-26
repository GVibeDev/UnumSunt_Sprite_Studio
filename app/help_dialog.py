from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


_HELP_SECTIONS: tuple[tuple[str, str], ...] = (
    (
        "Quick Start",
        """
        <h2>Unum Sunt Sprite Studio — Quick Start</h2>
        <p><b>Sprite Studio is a production pipeline, not a one-click sprite generator.</b>
        You can enter the workflow from a generated image, an existing image, a video,
        a frame sequence, or a spritesheet.</p>

        <h3>Choose your starting point</h3>
        <ul>
          <li><b>Text concept:</b> Prompt Builder → Image Gen → Generate → Extraction → Clean-up → Alignment → Export.</li>
          <li><b>Existing image:</b> Image Gen/Generate reference → Generate → Extraction → Clean-up → Alignment → Export.</li>
          <li><b>Existing video:</b> Open Video → Extraction → Selection → Clean-up → Alignment → Export.</li>
          <li><b>Existing spritesheet:</b> Sprite Sheet → Decompose/Normalize → Clean-up/Alignment → Character Set → Export.</li>
          <li><b>Frame sequence:</b> Import sequence → Clean-up → Alignment → Character Set → Export.</li>
        </ul>

        <h3>Core-first workflow</h3>
        <p>The Core works without the local AI runtime. Generation is optional; all inspection,
        selection, clean-up, alignment, organization, and export tools remain available for
        existing media.</p>

        <h3>Where to begin</h3>
        <p>Create or open a project in <b>Project</b>, select a Project Group, then use either
        <b>Workflow</b> for a guided route or open the required workspace directly.</p>
        """,
    ),
    (
        "Production Workflow",
        """
        <h2>Production Workflow</h2>
        <p>A reliable production run is usually iterative:</p>
        <p><b>test → compare → preserve → refine</b></p>

        <ol>
          <li><b>Prompt Builder:</b> keep prompts modular and avoid contradictory instructions.</li>
          <li><b>Image Gen:</b> create or refine a clean master/reference image.</li>
          <li><b>Generate:</b> create motion with WanGP/Wan Animate when required.</li>
          <li><b>Extraction:</b> inspect frames and establish the alpha/background result.</li>
          <li><b>Selection:</b> remove duplicates, anomalies, and unusable frames.</li>
          <li><b>Clean-up:</b> repair masks/alpha and propagate repeatable corrections.</li>
          <li><b>Alignment:</b> normalize scale, pivot, anchors, mirroring, and output geometry.</li>
          <li><b>Character Set:</b> organize subject → animation → direction assets and layers.</li>
          <li><b>Export:</b> produce frame sequences and/or spritesheets.</li>
        </ol>

        <h3>Useful rule</h3>
        <p>A generation does not have to be perfect to be useful. If several frames are good,
        keep them and continue through the production tools instead of discarding the whole run.</p>

        <h3>Calibration</h3>
        <p>Use <b>Calibration Lab</b> and <b>Production Presets</b> to preserve configurations
        that actually worked. Higher resolution, more steps, and more frames do not automatically
        produce better results.</p>
        """,
    ),
    (
        "Local AI",
        """
        <h2>Local AI Setup</h2>
        <p>Local AI is optional and remains separate from the Sprite Studio Core.</p>

        <h3>Runtime Manager</h3>
        <p>Open <b>File → AI Runtime Manager</b> to:</p>
        <ul>
          <li>run preflight and health checks;</li>
          <li>install a managed WanGP runtime;</li>
          <li>detect/adopt an existing compatible WanGP installation;</li>
          <li>install or maintain Wan Animate and Krea 2 components;</li>
          <li>repair/update managed runtime components.</li>
        </ul>

        <h3>Hardware and storage</h3>
        <p>A complete managed AI setup should be planned around <b>about 100 GB of free disk space</b>,
        with additional room for projects, generated media, and cache. Local generation is
        GPU-intensive. There is no single universal VRAM/RAM minimum because requirements depend
        on model, resolution, frame count, precision, and memory/offload profile.</p>

        <h3>Existing WanGP</h3>
        <p>An adopted external runtime is treated as read-only by maintenance: Sprite Studio does
        not move, rename, repair, or delete it automatically.</p>

        <h3>Krea 2</h3>
        <p>Krea 2 remains separately licensed. Managed use requires explicit license/AUP
        acknowledgement. Generated Krea output must be reviewed before it is promoted directly
        into the WAN reference workflow.</p>
        """,
    ),
    (
        "Controls & Tips",
        """
        <h2>Controls & Practical Tips</h2>

        <h3>Common shortcuts</h3>
        <ul>
          <li><b>Ctrl+N</b> — New Project</li>
          <li><b>Ctrl+O</b> — Open Project</li>
          <li><b>Ctrl+S</b> — Save Project</li>
          <li><b>Ctrl+Shift+O</b> — Open Video</li>
          <li><b>Ctrl+Alt+O</b> — Open Spritesheet</li>
          <li><b>Space</b> — Play/Pause in Extraction</li>
          <li><b>Left / Right</b> — Previous/Next frame in Extraction</li>
          <li><b>A</b> — Add current frame to the R1 selection</li>
          <li><b>Delete</b> — Remove selected frame / clear the active clean-up selection where applicable</li>
        </ul>

        <h3>Generation tips</h3>
        <ul>
          <li>Start with a clean, readable reference and a simple background.</li>
          <li>Avoid conflicting prompt instructions.</li>
          <li>Keep identity anchors visible and consistent across references.</li>
          <li>Change one important variable at a time when calibrating.</li>
          <li>Preserve good runs as profiles/presets instead of relying on memory.</li>
        </ul>

        <h3>Clean-up and alignment</h3>
        <p>Keep edits non-destructive where possible. Use propagation only when the same correction
        is valid for all selected frames, then inspect the result before export.</p>
        """,
    ),
    (
        "About & Licensing",
        """
        <h2>About & Licensing</h2>
        <p><b>Unum Sunt Sprite Studio Core</b> is free and open-source software distributed under
        the <b>GNU General Public License v3.0 or later (GPL-3.0-or-later)</b>.</p>

        <p>A paid packaged distribution does not make the Core proprietary and does not remove
        GPL rights. The Corresponding Source for the distributed version must be provided or made
        available alongside the binaries at no additional charge.</p>

        <p>WanGP, Krea 2, Wan Animate, model checkpoints, and other third-party components remain
        subject to their own licenses and terms. See <b>LICENSE</b>,
        <b>THIRD_PARTY_NOTICES.txt</b>, <b>KREA_SAFETY_AND_USE.txt</b>, and
        <b>OPEN_SOURCE_LICENSE_NOTICE.txt</b> in the distributed package.</p>

        <p><b>More control, not more promises.</b></p>
        """,
    ),
)


class HelpDialog(QDialog):
    """Built-in, offline guidance for the public Windows release."""

    def __init__(self, parent=None, *, section: str = "Quick Start") -> None:
        super().__init__(parent)
        self.setWindowTitle("Sprite Studio Help")
        self.setModal(False)
        self.resize(820, 640)

        root = QVBoxLayout(self)

        intro = QLabel(
            "Offline help for the production pipeline. These pages describe the Core and the "
            "optional local-AI workflow without requiring an internet connection."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        section_index = 0
        for index, (title, html) in enumerate(_HELP_SECTIONS):
            page = QWidget()
            layout = QVBoxLayout(page)
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setHtml(html)
            layout.addWidget(browser)
            self.tabs.addTab(page, title)
            if title.casefold() == section.casefold():
                section_index = index

        self.tabs.setCurrentIndex(section_index)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.close)
        root.addWidget(buttons)

        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
