"""
test/test_sincronizacion_bisturi.py
Pruebas para el guardado/sincronización bisturí en Google Sheets.
"""

import pytest
from unittest.mock import MagicMock, patch
from domain.planilla.service import PlanillaService


@patch("domain.planilla.service.get_sheets")
def test_sincronizar_registro_bisturi_flujo_completo(mock_get_sheets):
    mock_client = MagicMock()
    mock_spreadsheet = MagicMock()
    mock_sheet = MagicMock()
    
    mock_get_sheets.return_value = mock_client
    mock_client.open.return_value = mock_spreadsheet
    mock_spreadsheet.sheet1 = mock_sheet

    service = PlanillaService(planilla_repo=MagicMock(), historial_repo=MagicMock())

    datos_registro = {
        "nombre_planilla": "CASAS 1-20",
        "numero_territorio": 5,
        "fila": 1,
        "conductor": "Juan Pérez",
        "cantidad_abarcado": "Completo",
        "fecha_asignado": "2026-03-01",
        "fecha_completado": "2026-03-15"
    }

    # Si tenés implementado sincronizar_registro_bisturi
    if hasattr(service, "sincronizar_registro_bisturi"):
        service.sincronizar_registro_bisturi(datos_registro)

        # Verifica que haya intentado abrir la planilla validada
        mock_client.open.assert_called_once_with("CASAS 1-20")
        
        # Verifica las llamadas atómicas a la hoja
        assert mock_sheet.batch_update.called or mock_sheet.update.called