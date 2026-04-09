from __future__ import annotations

from typing import Any

from PySide6.QtGui import QDoubleValidator, QValidator, QWheelEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QWidget,
    QSpinBox,
)

from genesis.core.instrument.config_field import ConfigFieldDefinition


class _NoWheelSpinBox(QSpinBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        edit = self.lineEdit()
        if edit is not None:
            edit.setMaxLength(32)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class _NoWheelDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._validator = QDoubleValidator(self)
        self._validator.setNotation(QDoubleValidator.Notation.ScientificNotation)
        edit = self.lineEdit()
        if edit is not None:
            edit.setMaxLength(64)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()

    def validate(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        stripped = text.strip()
        if stripped in {"", "-", "+", ".", "-.", "+."}:
            return (QValidator.State.Intermediate, text, pos)
        self._validator.setRange(
            float(self.minimum()), float(self.maximum()), max(16, int(self.decimals()))
        )
        state, _, _ = self._validator.validate(text, pos)
        return (state, text, pos)

    def valueFromText(self, text: str) -> float:
        try:
            value = float(text.strip())
        except Exception:
            return float(self.value())
        return max(float(self.minimum()), min(float(self.maximum()), value))


class InstrumentConfigForm(QWidget):
    """
    Auto-generated form for instrument configuration fields.

    This UI does not encode instrument behavior; it only collects values that
    are later persisted into the job JSON.
    """

    def __init__(
        self,
        fields: list[ConfigFieldDefinition],
        initialValues: dict[str, Any] | None = None,
        initialSweepKeys: list[str] | None = None,
        showSweepCheckboxes: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.fields = fields
        self.initialValues = initialValues or {}
        self.initialSweepKeys = set(initialSweepKeys or [])
        self.showSweepCheckboxes = showSweepCheckboxes

        self._widgetByKey: dict[str, QWidget] = {}
        self._sweepCheckByKey: dict[str, QCheckBox] = {}
        self._baseFieldEnabledByKey: dict[str, bool] = {}

        self._layout = QFormLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet(
            """
            QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled,
            QLineEdit:disabled, QCheckBox:disabled {
                background-color: #2a2a2a;
                color: #8f8f8f;
                border: 1px solid #555555;
            }
            """
        )

        for field in self.fields:
            self._addField(field)

    def _addField(self, field: ConfigFieldDefinition) -> None:
        value = self.initialValues.get(field.key, field.default)
        fieldType = field.fieldType

        if fieldType == "int":
            widget = _NoWheelSpinBox(self)
            widget.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            widget.setValue(int(value))
            if field.minValue is not None or field.maxValue is not None:
                minValue = (
                    int(field.minValue) if field.minValue is not None else -2147483648
                )
                maxValue = (
                    int(field.maxValue) if field.maxValue is not None else 2147483647
                )
                widget.setRange(minValue, maxValue)
            if field.stepValue is not None:
                widget.setSingleStep(int(field.stepValue))

        elif fieldType == "float":
            widget = _NoWheelDoubleSpinBox(self)
            widget.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            widget.setValue(float(value))
            widget.setDecimals(6)
            if field.minValue is not None or field.maxValue is not None:
                minValue = (
                    float(field.minValue) if field.minValue is not None else -1e12
                )
                maxValue = float(field.maxValue) if field.maxValue is not None else 1e12
                widget.setRange(minValue, maxValue)
            if field.stepValue is not None:
                widget.setSingleStep(float(field.stepValue))

        elif fieldType == "bool":
            widget = QCheckBox(self)
            widget.setChecked(bool(value))

        elif fieldType == "enum":
            widget = QComboBox(self)
            for choice in field.choices or []:
                widget.addItem(choice.label, userData=choice.value)
            index = widget.findData(value)
            widget.setCurrentIndex(index if index >= 0 else 0)

        else:
            # Default: treat as string
            widget = QLineEdit(self)
            widget.setText(str(value))

        if self.showSweepCheckboxes and field.sweepable:
            rowWidget = QWidget(self)
            rowLayout = QHBoxLayout(rowWidget)
            rowLayout.setContentsMargins(0, 0, 0, 0)
            rowLayout.addWidget(widget, 1)
            sweepCheck = QCheckBox("Sweep", rowWidget)
            sweepCheck.setChecked(field.key in self.initialSweepKeys)
            self._sweepCheckByKey[field.key] = sweepCheck
            sweepCheck.toggled.connect(
                lambda _checked, key=field.key: self._applyFieldEnabled(key)
            )
            rowLayout.addWidget(sweepCheck)
            self._layout.addRow(field.label, rowWidget)
        else:
            self._layout.addRow(field.label, widget)

        self._widgetByKey[field.key] = widget
        self._baseFieldEnabledByKey[field.key] = True
        self._applyFieldEnabled(field.key)

    def getValues(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for field in self.fields:
            widget = self._widgetByKey[field.key]
            fieldType = field.fieldType

            if fieldType == "int":
                values[field.key] = int(widget.value())  # type: ignore[attr-defined]
            elif fieldType == "float":
                values[field.key] = float(widget.value())  # type: ignore[attr-defined]
            elif fieldType == "bool":
                values[field.key] = bool(widget.isChecked())  # type: ignore[attr-defined]
            elif fieldType == "enum":
                values[field.key] = widget.currentData()  # type: ignore[attr-defined]
            else:
                values[field.key] = widget.text()  # type: ignore[attr-defined]

        return values

    def getSweepSelections(self) -> list[str]:
        selected: list[str] = []
        for key, cb in self._sweepCheckByKey.items():
            if cb.isChecked():
                selected.append(key)
        return selected

    def getWidget(self, key: str) -> QWidget | None:
        return self._widgetByKey.get(key)

    def setSweepOptionEnabled(self, key: str, enabled: bool) -> None:
        cb = self._sweepCheckByKey.get(key)
        if cb is None:
            return
        cb.setEnabled(enabled)
        if not enabled:
            cb.setChecked(False)

    def setFieldEnabled(self, key: str, enabled: bool) -> None:
        if key not in self._widgetByKey:
            return
        self._baseFieldEnabledByKey[key] = enabled
        self._applyFieldEnabled(key)

    def _applyFieldEnabled(self, key: str) -> None:
        widget = self._widgetByKey.get(key)
        if widget is None:
            return
        baseEnabled = self._baseFieldEnabledByKey.get(key, True)
        sweepCheck = self._sweepCheckByKey.get(key)
        sweepSelected = bool(sweepCheck and sweepCheck.isChecked())
        widget.setEnabled(baseEnabled and not sweepSelected)
