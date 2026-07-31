from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from assistant.assistant_cooperative_graph import LocalAssistantGraph
from services.audio_recorder import AudioRecorder
from services.tts_service import TTSService
from workers.assistant_worker import AssistantWorker
from workers.transcription_worker import TranscriptionWorker
from tools.speech_tools import SpeechTools

class MessageInput(QTextEdit):
    send_requested = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and not event.modifiers() & Qt.ShiftModifier
        ):
            event.accept()
            self.send_requested.emit()
            return

        super().keyPressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("Local AI Assistant")
        self.resize(1050, 760)
        self.setMinimumSize(820, 620)

        self.assistant = LocalAssistantGraph(
            model="llama3.1:8b"
        )

        self.audio_recorder = AudioRecorder()

        project_root = Path(__file__).resolve().parent.parent
        piper_model = (
            project_root
            / "models"
            / "piper"
            / "ro_RO-mihai-medium.onnx"
        )

        self.tts_service = TTSService(
            model_path=piper_model
        )

        self.voice_enabled = True
        self.request_running = False
        self.request_id = 0
        self.cancelled_request_ids: set[int] = set()

        self.assistant_thread: QThread | None = None
        self.assistant_worker: AssistantWorker | None = None

        self.transcription_thread: QThread | None = None
        self.transcription_worker: TranscriptionWorker | None = None

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        main_layout = QVBoxLayout(root)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        header_layout = QHBoxLayout()

        title_container = QVBoxLayout()
        title_container.setSpacing(2)

        title = QLabel("Local AI Assistant")
        title.setObjectName("titleLabel")

        subtitle = QLabel(
            "Asistent local cu Ollama, voce și agenți specializați"
        )
        subtitle.setObjectName("subtitleLabel")

        title_container.addWidget(title)
        title_container.addWidget(subtitle)

        header_layout.addLayout(title_container)
        header_layout.addStretch()

        self.voice_button = QPushButton("🔊 Voce activă")
        self.voice_button.setObjectName("secondaryButton")
        self.voice_button.setCheckable(True)
        self.voice_button.setChecked(True)
        self.voice_button.clicked.connect(
            self._toggle_voice
        )

        self.stop_button = QPushButton("■ Oprește")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(
            self._stop_current_action
        )

        header_layout.addWidget(self.voice_button)
        header_layout.addWidget(self.stop_button)

        main_layout.addLayout(header_layout)

        # Zona principală conține:
        # - panoul cu fluxul agenților;
        # - conversația.
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)


        # -------------------------
        # Panoul agenților
        # -------------------------
        workflow_frame = QFrame()
        workflow_frame.setObjectName("workflowFrame")
        workflow_frame.setFixedWidth(210)

        workflow_layout = QVBoxLayout(workflow_frame)
        workflow_layout.setContentsMargins(16, 16, 16, 16)
        workflow_layout.setSpacing(10)

        workflow_title = QLabel("Flux activ")
        workflow_title.setObjectName("workflowTitle")

        workflow_layout.addWidget(workflow_title)

        self.workflow_router = QLabel("○ Router")
        self.workflow_conversation = QLabel("○ Conversation")
        self.workflow_calculator = QLabel("○ Calculator")
        self.workflow_search = QLabel("○ Search")
        self.workflow_weather = QLabel("○ Weather")
        self.workflow_system = QLabel("○ System")
        self.workflow_writer = QLabel("○ Email Writer")
        self.workflow_reviewer = QLabel("○ Email Reviewer")
        self.workflow_reviser = QLabel("○ Email Reviser")
        self.workflow_sender = QLabel("○ Email Sender")
        self.workflow_finish = QLabel("○ Finalizare")

        self.workflow_labels = {
            "router": self.workflow_router,
            "conversation": self.workflow_conversation,
            "calculator": self.workflow_calculator,
            "search": self.workflow_search,
            "weather": self.workflow_weather,
            "system": self.workflow_system,
            "email_writer": self.workflow_writer,
            "email_reviewer": self.workflow_reviewer,
            "email_reviser": self.workflow_reviser,
            "email_sender": self.workflow_sender,
            "email_finish": self.workflow_finish,
        }

        for label in self.workflow_labels.values():
            label.setObjectName("workflowStep")
            workflow_layout.addWidget(label)

        workflow_layout.addStretch()


        # -------------------------
        # Chatul
        # -------------------------
        self.chat = QTextBrowser()
        self.chat.setObjectName("chatView")
        self.chat.setOpenExternalLinks(False)


        content_layout.addWidget(workflow_frame)
        content_layout.addWidget(
            self.chat,
            stretch=1,
        )

        main_layout.addLayout(
            content_layout,
            stretch=1,
        )

        status_frame = QFrame()
        status_frame.setObjectName("statusFrame")

        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(14, 8, 14, 8)

        self.status_label = QLabel("Pregătit")
        self.status_label.setObjectName("statusLabel")

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(140)
        self.progress.setTextVisible(False)
        self.progress.hide()

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress)

        main_layout.addWidget(status_frame)

        input_frame = QFrame()
        input_frame.setObjectName("inputFrame")

        input_layout = QHBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 12, 12, 12)
        input_layout.setSpacing(10)

        self.message_input = MessageInput()
        self.message_input.setObjectName("messageInput")
        self.message_input.setPlaceholderText(
            "Scrie un mesaj... Enter pentru trimitere, "
            "Shift+Enter pentru rând nou"
        )
        self.message_input.setFixedHeight(82)
        self.message_input.send_requested.connect(
            self._send_message
        )

        self.microphone_button = QPushButton("🎙")
        self.microphone_button.setObjectName("microphoneButton")
        self.microphone_button.setFixedSize(54, 54)
        self.microphone_button.setToolTip(
            "Pornește înregistrarea"
        )
        self.microphone_button.clicked.connect(
            self._toggle_recording
        )

        self.send_button = QPushButton("Trimite")
        self.send_button.setObjectName("sendButton")
        self.send_button.setFixedHeight(54)
        self.send_button.clicked.connect(
            self._send_message
        )

        input_layout.addWidget(
            self.message_input,
            stretch=1,
        )
        input_layout.addWidget(self.microphone_button)
        input_layout.addWidget(self.send_button)

        main_layout.addWidget(input_frame)

        self._append_assistant_message(
            "Bună! Poți să îmi scrii sau să folosești "
            "butonul de microfon."
        )

    def _send_message(self) -> None:
        if self.request_running:
            return

        text = self.message_input.toPlainText().strip()

        if not text:
            return

        self.message_input.clear()
        self._append_user_message(text)
        self._start_assistant_request(text)

    def _start_assistant_request(self, text: str) -> None:
        
        self._reset_workflow()
        
        self.request_id += 1
        current_request_id = self.request_id

        self.request_running = True
        self._set_busy(
            True,
            "Asistentul procesează cererea...",
        )

        thread = QThread(self)
        worker = AssistantWorker(
            assistant=self.assistant,
            message=text,
            request_id=current_request_id,
        )

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.finished.connect(
            self._assistant_finished
        )
        worker.failed.connect(
            self._assistant_failed
        )
        worker.progress.connect(
            self._workflow_progress
        )

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(
            self._clear_assistant_thread
        )

        self.assistant_thread = thread
        self.assistant_worker = worker

        thread.start()

    def _workflow_progress(
        self,
        node_name: str,
        state: str,
    ) -> None:
        """
        Primește de la AssistantWorker numele nodului executat
        și starea lui, apoi actualizează interfața.
        """

        self._set_workflow_step(
            node_name,
            state,
        )

        status_messages = {
            "router": "Routerul analizează cererea...",
            "conversation": (
                "ConversationAgent generează răspunsul..."
            ),
            "calculator": (
                "CalculatorAgent efectuează calculul..."
            ),
            "search": (
                "SearchAgent caută informațiile..."
            ),
            "weather": (
                "WeatherAgent obține datele meteo..."
            ),
            "system": (
                "SystemAgent verifică sistemul..."
            ),
            "email_writer": (
                "Email Writer redactează emailul..."
            ),
            "email_reviewer": (
                "Email Reviewer verifică emailul..."
            ),
            "email_reviser": (
                "Email Reviser corectează emailul..."
            ),
            "email_finish": (
                "Finalizez emailul..."
            ),
            "email_sender": (
                "Email Sender trimite emailul..."
            ),
        }

        if state == "active":
            self.status_label.setText(
                status_messages.get(
                    node_name,
                    f"Rulează {node_name}...",
                )
            )

        elif state == "completed":
            self.status_label.setText(
                f"{node_name} finalizat."
            )   
        
    def _assistant_finished(
        self,
        response: str,
        request_id: int,
    ) -> None:
        if request_id in self.cancelled_request_ids:
            self.cancelled_request_ids.discard(request_id)
            return

        self.request_running = False
        self._set_busy(False, "Pregătit")
        display_text = response
        speech_text = SpeechTools.prepare_for_tts(response)

        self._append_assistant_message(display_text)

        if self.voice_enabled:
            self.tts_service.speak(speech_text)
            self.stop_button.setEnabled(True)
            self.status_label.setText(
                "Redau răspunsul vocal..."
            )

    def _assistant_failed(
        self,
        error: str,
        request_id: int,
    ) -> None:
        if request_id in self.cancelled_request_ids:
            self.cancelled_request_ids.discard(request_id)
            return

        self.request_running = False
        self._set_busy(False, "Eroare")

        self._append_error_message(error)

    def _clear_assistant_thread(self) -> None:
        self.assistant_thread = None
        self.assistant_worker = None

    def _toggle_recording(self) -> None:
        if self.audio_recorder.is_recording:
            self._stop_recording_and_transcribe()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        if self.request_running:
            return

        try:
            self.tts_service.stop()
            self.audio_recorder.start()

            self.microphone_button.setText("■")
            self.microphone_button.setProperty(
                "recording",
                True,
            )
            self.microphone_button.style().unpolish(
                self.microphone_button
            )
            self.microphone_button.style().polish(
                self.microphone_button
            )

            self.microphone_button.setToolTip(
                "Oprește înregistrarea"
            )

            self.status_label.setText(
                "Ascult... apasă din nou pentru oprire."
            )
            self.stop_button.setEnabled(True)

        except Exception as exc:
            self._show_error(
                f"Microfonul nu a putut fi pornit:\n{exc}"
            )

    def _stop_recording_and_transcribe(self) -> None:
        try:
            audio_path = self.audio_recorder.stop()

            self._reset_microphone_button()
            self._set_busy(
                True,
                "Transcriu înregistrarea...",
            )

            thread = QThread(self)
            worker = TranscriptionWorker(
                audio_path=audio_path,
                model_name="small",
            )

            worker.moveToThread(thread)

            thread.started.connect(worker.run)

            worker.finished.connect(
                self._transcription_finished
            )
            worker.failed.connect(
                self._transcription_failed
            )

            worker.finished.connect(thread.quit)
            worker.failed.connect(thread.quit)

            thread.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            thread.finished.connect(
                self._clear_transcription_thread
            )

            self.transcription_thread = thread
            self.transcription_worker = worker

            thread.start()

        except Exception as exc:
            self._reset_microphone_button()
            self._set_busy(False, "Pregătit")
            self._show_error(
                f"Înregistrarea nu a putut fi procesată:\n{exc}"
            )

    def _transcription_finished(self, text: str) -> None:
        self._set_busy(False, "Pregătit")

        self.message_input.setPlainText(text)
        self.message_input.setFocus()

        self._send_message()

    def _transcription_failed(self, error: str) -> None:
        self._set_busy(False, "Eroare")
        self._append_error_message(
            f"Transcrierea a eșuat: {error}"
        )

    def _clear_transcription_thread(self) -> None:
        self.transcription_thread = None
        self.transcription_worker = None

    def _toggle_voice(self, checked: bool) -> None:
        self.voice_enabled = checked

        if checked:
            self.voice_button.setText("🔊 Voce activă")
        else:
            self.voice_button.setText("🔇 Voce oprită")
            self.tts_service.stop()
            self.status_label.setText("Pregătit")

    def _stop_current_action(self) -> None:
        self.tts_service.stop()

        if self.audio_recorder.is_recording:
            self.audio_recorder.cancel()
            self._reset_microphone_button()

        if self.request_running:
            self.cancelled_request_ids.add(
                self.request_id
            )

            self.request_running = False
            self._append_system_message(
                "Procesarea a fost oprită."
            )

        self._set_busy(False, "Oprit")
        self.message_input.setEnabled(True)
        self.send_button.setEnabled(True)
        self.microphone_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _set_busy(
        self,
        busy: bool,
        status: str,
    ) -> None:
        self.status_label.setText(status)
        self.progress.setVisible(busy)

        self.message_input.setEnabled(not busy)
        self.send_button.setEnabled(not busy)
        self.microphone_button.setEnabled(not busy)

        self.stop_button.setEnabled(busy)

    def _reset_microphone_button(self) -> None:
        self.microphone_button.setText("🎙")
        self.microphone_button.setProperty(
            "recording",
            False,
        )
        self.microphone_button.style().unpolish(
            self.microphone_button
        )
        self.microphone_button.style().polish(
            self.microphone_button
        )
        self.microphone_button.setToolTip(
            "Pornește înregistrarea"
        )

    def _append_user_message(self, text: str) -> None:
        self.chat.append(
            f"""
            <div style="margin: 12px 0; text-align: right;">
                <span style="
                    display: inline-block;
                    background: #2563eb;
                    color: white;
                    padding: 10px 14px;
                    border-radius: 16px;
                    max-width: 72%;
                ">
                    {escape(text)}
                </span>
            </div>
            """
        )

        self._scroll_to_bottom()

    def _append_assistant_message(self, text: str) -> None:
        safe_text = escape(text).replace("\n", "<br>")

        self.chat.append(
            f"""
            <div style="margin: 12px 0; text-align: left;">
                <span style="
                    display: inline-block;
                    background: #1e293b;
                    color: #e2e8f0;
                    padding: 10px 14px;
                    border-radius: 16px;
                    max-width: 78%;
                ">
                    <b>AI</b><br>
                    {safe_text}
                </span>
            </div>
            """
        )

        self._scroll_to_bottom()

    def _append_error_message(self, text: str) -> None:
        self.chat.append(
            f"""
            <div style="
                margin: 12px 0;
                color: #fca5a5;
            ">
                <b>Eroare:</b> {escape(text)}
            </div>
            """
        )

        self._scroll_to_bottom()
    
    def _reset_workflow(self) -> None:
        """
        Resetează toate etapele fluxului.
        """

        for label in self.workflow_labels.values():
            original_text = label.text()

            original_text = original_text.replace("●", "○")
            original_text = original_text.replace("✓", "○")

            label.setText(original_text)
            label.setProperty("state", "inactive")

            label.style().unpolish(label)
            label.style().polish(label)


    def _set_workflow_step(
        self,
        step_name: str,
        state: str = "active",
    ) -> None:
        """
        Actualizează vizual o etapă din flux.

        state poate fi:
        - active
        - completed
        - inactive
        """

        label = self.workflow_labels.get(step_name)

        if label is None:
            return

        text = label.text()

        text = text.replace("○", "")
        text = text.replace("●", "")
        text = text.replace("✓", "")
        text = text.strip()

        if state == "active":
            prefix = "●"
        elif state == "completed":
            prefix = "✓"
        else:
            prefix = "○"

        label.setText(f"{prefix} {text}")
        label.setProperty("state", state)

        label.style().unpolish(label)
        label.style().polish(label)

    def _append_system_message(self, text: str) -> None:
        self.chat.append(
            f"""
            <div style="
                margin: 10px 0;
                text-align: center;
                color: #94a3b8;
            ">
                {escape(text)}
            </div>
            """
        )

        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        scrollbar = self.chat.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(
            self,
            "Eroare",
            message,
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        self.tts_service.stop()
        self.audio_recorder.cancel()

        event.accept()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow {
                background: #07111f;
            }

            QWidget {
                color: #e5e7eb;
                font-family: "Segoe UI";
                font-size: 14px;
            }

            QLabel#titleLabel {
                font-size: 25px;
                font-weight: 700;
                color: #f8fafc;
            }

            QLabel#subtitleLabel {
                color: #94a3b8;
                font-size: 13px;
            }

            QTextBrowser#chatView {
                background: #0b1728;
                border: 1px solid #1e293b;
                border-radius: 18px;
                padding: 14px;
                selection-background-color: #2563eb;
            }

            QFrame#statusFrame {
                background: #0b1728;
                border: 1px solid #1e293b;
                border-radius: 11px;
            }

            QLabel#statusLabel {
                color: #94a3b8;
            }

            QProgressBar {
                background: #111827;
                border: none;
                border-radius: 3px;
                height: 5px;
            }

            QProgressBar::chunk {
                background: #38bdf8;
                border-radius: 3px;
            }

            QFrame#inputFrame {
                background: #0b1728;
                border: 1px solid #1e293b;
                border-radius: 16px;
            }

            QTextEdit#messageInput {
                background: #111d30;
                border: 1px solid #26364d;
                border-radius: 12px;
                padding: 10px;
                color: #f8fafc;
            }

            QTextEdit#messageInput:focus {
                border: 1px solid #38bdf8;
            }

            QPushButton {
                border: none;
                border-radius: 10px;
                padding: 9px 15px;
                font-weight: 600;
            }

            QPushButton#sendButton {
                background: #2563eb;
                color: white;
                min-width: 92px;
            }

            QPushButton#sendButton:hover {
                background: #3b82f6;
            }

            QPushButton#microphoneButton {
                background: #172338;
                color: #e2e8f0;
                font-size: 21px;
                border-radius: 27px;
            }

            QPushButton#microphoneButton:hover {
                background: #24334d;
            }

            QPushButton#microphoneButton[recording="true"] {
                background: #dc2626;
                color: white;
            }

            QPushButton#secondaryButton {
                background: #172338;
                color: #dbeafe;
            }

            QPushButton#secondaryButton:hover {
                background: #24334d;
            }

            QPushButton#stopButton {
                background: #7f1d1d;
                color: #fee2e2;
            }

            QPushButton#stopButton:hover {
                background: #991b1b;
            }

            QPushButton:disabled {
                background: #182234;
                color: #64748b;
            }
            QFrame#workflowFrame {
                background: #0b1728;
                border: 1px solid #1e293b;
                border-radius: 16px;
            }

            QLabel#workflowTitle {
                color: #f8fafc;
                font-size: 16px;
                font-weight: 700;
                padding-bottom: 8px;
            }

            QLabel#workflowStep {
                background: transparent;
                color: #64748b;
                padding: 9px 10px;
                border-radius: 8px;
                font-size: 13px;
            }

            QLabel#workflowStep[state="active"] {
                background: #172554;
                color: #93c5fd;
                font-weight: 600;
            }

            QLabel#workflowStep[state="completed"] {
                background: #052e2b;
                color: #5eead4;
            }

            QLabel#workflowStep[state="inactive"] {
                color: #64748b;
            }


            """
        )