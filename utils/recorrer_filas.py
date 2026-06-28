def localizar_celda_conductor (fila, columna) :

    celda_1 = (fila, columna + 2 or columna + 3)
    celda_2 = (fila, columna + 4 or columna + 5)
    celda_3 = (fila, columna + 6 or columna + 7)
    celda_4 = (fila, columna + 8 or columna + 9)
    celda_5 = (fila, columna + 1)

    return (celda_1, celda_2, celda_3, celda_4, celda_5)

def localizar_celda_fecha_asignado (fila, columna) :

    celda_1 = (fila + 3, columna + 2)
    celda_2 = (fila + 3, columna + 4)
    celda_3 = (fila + 3, columna + 6)
    celda_4 = (fila + 3, columna + 8)
    celda_5 = (fila + 3, columna + 1)

    return (celda_1, celda_2, celda_3, celda_4, celda_5)

def localizar_celda_fecha_completado (fila, columna) :

    celda_1 = (fila + 3, columna + 3)
    celda_2 = (fila + 3, columna + 5)
    celda_3 = (fila + 3, columna + 7)
    celda_4 = (fila + 3, columna + 9)
    celda_5 = (fila + 3, columna + 1)
    
    return (celda_1, celda_2, celda_3, celda_4, celda_5)
