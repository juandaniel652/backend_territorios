from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException
from core.google_sheets import get_sheets

# ✅ Importamos la clase correcta desde su dominio
from domain.agenda.service import AgendaQuincenalService

DEFAULT_SPREADSHEET_NAME = "salida_modelo" 

def _obtener_dia_semana(fecha_str: str) -> int:
    """Convierte fecha 'YYYY-MM-DD' a 0=Lunes ... 6=Domingo"""
    return datetime.strptime(fecha_str, "%Y-%m-%d").weekday()

def sincronizar_automatico_sin_params(db: Session) -> dict:
    """
    Botón de un solo clic: Genera la agenda actual y sube únicamente la Semana 1 
    a Google Sheets (Columna A: Horario, Columna C: Territorio, Columna D: Conductor).
    """
    # 1. Instanciamos el servicio de agenda
    try:
        agenda_service = AgendaQuincenalService(db)
        resultado_agenda = agenda_service.generar_propuesta_quincenal_combinada()
        
        propuesta = resultado_agenda.get("propuesta") if isinstance(resultado_agenda, dict) else resultado_agenda
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al generar la agenda combinada: {str(e)}"
        )

    if not propuesta:
        raise HTTPException(status_code=404, detail="No se generó ninguna propuesta para sincronizar.")

    # 2. Conectarse a Google Sheets
    try:
        client = get_sheets()
        sheet = client.open(DEFAULT_SPREADSHEET_NAME).sheet1
    except Exception as e:
        raise HTTPException(
            status_code=400, 
            detail=f"No se pudo conectar a Google Sheets '{DEFAULT_SPREADSHEET_NAME}': {str(e)}"
        )

    fila_actual = 3
    ultimo_dia = None
    total_actualizadas = 0

    try:
        # 3. Tomamos ÚNICAMENTE la Semana 1
        semana_1 = propuesta[0]
        salidas = semana_1.get("salidas") if isinstance(semana_1, dict) else semana_1.salidas

        # 4. Recorrer y escribir en las columnas A, C y D arrancando desde la fila 3
        for salida in salidas:
            fecha = salida.get("fecha") if isinstance(salida, dict) else salida.fecha
            horario = salida.get("horario") if isinstance(salida, dict) else salida.horario
            territorio = salida.get("territorio_numero") if isinstance(salida, dict) else salida.territorio_numero
            conductor = salida.get("conductor_nombre") if isinstance(salida, dict) else salida.conductor_nombre

            dia_actual = _obtener_dia_semana(fecha)

            if ultimo_dia is None:
                fila_actual = 3
            elif dia_actual == ultimo_dia:
                fila_actual += 1  # Mismo día -> Fila inmediatamente siguiente
            else:
                fila_actual += 2  # Día distinto -> Salta 2 filas

            ultimo_dia = dia_actual

            # Columna A (1) -> Horario, Columna C (3) -> Territorio, Columna D (4) -> Conductor
            sheet.update_cell(fila_actual, 1, horario)
            sheet.update_cell(fila_actual, 3, territorio)
            sheet.update_cell(fila_actual, 4, conductor)
            total_actualizadas += 1

        return {
            "status": "success",
            "message": f"Sincronización automática de la Semana 1 completada en '{DEFAULT_SPREADSHEET_NAME}'.",
            "filas_actualizadas": total_actualizadas
        }

    except Exception as e:
        print(f"--- ERROR ESCRIBIENDO EN SHEETS ---: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al escribir en Google Sheets: {str(e)}")