# Diagnóstico de Caída CROCO — Y2020M02 (dt=40s)

> Log analizado: `salida_Y2020M02_dt40.log`  
> Fecha de análisis: 2026-05-26

---

## 1. ¿Qué pasó?

El modelo terminó con **`MAIN: Abnormal termination: BLOWUP`** — el solver detectó `NaN` en todas las variables dinámicas (zeta, KE, PE, volumen) y abortó.

```
123124  7343.44630   NaN   NaN   NaN   NaN   tile=19
MAIN: Abnormal termination: BLOWUP
```

### Línea de tiempo del run

| Evento              | Fecha (UTC)          | Modelo day | Paso interno |
|---------------------|----------------------|------------|--------------|
| Inicio (INI)        | 2020-02-01 00:00     | 7336.0000  | —            |
| Último RST escrito  | 2020-02-07 16:00     | 7342.6667  | 121 441      |
| **BLOWUP**          | **2020-02-08 10:43** | **7343.446**| **123 124** |
| Fin previsto        | 2020-03-01 00:00     | 7365.0000  | 186 960      |

**Tiempo perdido desde el último RST:** 1 683 pasos × 40 s = **18.7 h**

---

## 2. Causa probable

### 2.1 Inestabilidad numérica (CFL barotrópica/baroclínica)

El blowup ocurrió en el **tile 19** (columna derecha del log). Las tres corridas previas muestran el mismo patrón:

| Corrida                 | dt (s) | Paso de crash | Tiempo crash |
|-------------------------|--------|---------------|--------------|
| Y2020M01 ps dt=60       | 60     | 13 583        | día 7314.43  |
| Y2020M01 ps dt=50       | 50     | 13 770        | día 7314.49  |
| **Y2020M02 dt=40**      | **40** | **123 124**   | **día 7343.45** |

Patrón claro: **reducir dt retrasa la caída pero no la evita.** Esto apunta a una zona de batimetría compleja o gradientes frontales intensos que violan CFL localmente. El tile 19 es el mismo candidato en múltiples corridas.

### 2.2 Forzamiento ONLINE_BULK (CFSR/ERA-ECMWF) estancado

En los últimos ~200 pasos antes del crash, `ONLINE_BULK` leía siempre `time = 7343.` sin avanzar. Esto puede indicar que los datos de forzamiento cubren exactamente hasta el día 7343 y el interpolador recibió valores fuera del rango válido → NaN en los flujos de superficie → inestabilidad.

```
ONLINE_BULK -- Read CFSR for time =    7343.    ← repetido >20 veces
123124  7343.44630   NaN   NaN   NaN   NaN
```

### 2.3 Forzamiento BLK es climatológico

El archivo `CROCO_FILES/croco_blk.nc` tiene `cycle_length=360` con registros en días 15, 45, 75... (climatología mensual). Si el módulo ONLINE intenta interpolar más allá del último registro disponible, la interpolación falla silenciosamente y produce NaN en los flujos.

---

## 3. Estado del archivo RST

```
croco_rst.nc
  scrum_time = 634 406 400 s   →  2020-02-07 16:00 UTC
  time_step  = [121441, 53, 1, 9]
  Dimensión time = 1 registro (modo sobrescritura NRPFRST=-1)
```

El RST está en modo **un solo registro** (`NRPFRST=-1`), por lo tanto **contiene el estado del último RST escrito** (paso 121 441). Es válido para reiniciar.

---

## 4. Sistema de detección de caída

Guardar como **`monitor_croco.sh`** y ejecutarlo en paralelo al modelo:

```bash
#!/bin/bash
# monitor_croco.sh — detecta BLOWUP en log de CROCO y notifica
# Uso: ./monitor_croco.sh salida_Y2020M02_dt40.log [intervalo_seg]

LOG_FILE="${1:?Falta el archivo de log}"
INTERVAL="${2:-30}"
ALERT_FILE="CROCO_ALERT_$(basename $LOG_FILE .log).txt"

echo "[$(date)] Monitoreando: $LOG_FILE" | tee "$ALERT_FILE"

while true; do
    if [[ ! -f "$LOG_FILE" ]]; then
        echo "[$(date)] ESPERANDO archivo $LOG_FILE..."
        sleep "$INTERVAL"
        continue
    fi

    # Detectar crash
    if grep -q "MAIN: Abnormal termination: BLOWUP" "$LOG_FILE"; then
        BLOWUP_LINE=$(grep "Abnormal termination" "$LOG_FILE")
        NAN_LINE=$(grep -E "NaN.*NaN" "$LOG_FILE" | tail -1)
        STEP=$(echo "$NAN_LINE" | awk '{print $1}')
        MDAY=$(echo "$NAN_LINE" | awk '{print $2}')
        TILE=$(echo "$NAN_LINE" | awk '{print $NF}')

        echo "" | tee -a "$ALERT_FILE"
        echo "========== CROCO BLOWUP DETECTADO ==========" | tee -a "$ALERT_FILE"
        echo "  Fecha sistema : $(date)"                     | tee -a "$ALERT_FILE"
        echo "  Paso crash    : $STEP"                       | tee -a "$ALERT_FILE"
        echo "  Día modelo    : $MDAY"                       | tee -a "$ALERT_FILE"
        echo "  Tile crash    : $TILE"                       | tee -a "$ALERT_FILE"
        echo "  Log           : $LOG_FILE"                   | tee -a "$ALERT_FILE"
        echo "=============================================" | tee -a "$ALERT_FILE"

        # Registrar último RST disponible
        LAST_RST=$(grep "WRT_RST" "$LOG_FILE" | tail -1)
        echo "  Último RST    : $LAST_RST"                   | tee -a "$ALERT_FILE"

        # Notificación por email (opcional, si hay mail configurado)
        # echo "CROCO BLOWUP en $LOG_FILE paso $STEP" | mail -s "CROCO CRASH" usuario@dominio.com

        echo ""
        echo "[ALERTA] Resumen guardado en: $ALERT_FILE"
        exit 1
    fi

    # Reporte de progreso cada N intervalos
    LAST_STEP=$(grep -E "^\s+[0-9]+ +[0-9]+\." "$LOG_FILE" | tail -1 | awk '{print $1, $2}')
    if [[ -n "$LAST_STEP" ]]; then
        echo "[$(date)] Último paso: $LAST_STEP"
    fi

    sleep "$INTERVAL"
done
```

### Uso

```bash
# Terminal 1: correr el modelo
nohup ./croco croco.in > salida_Y2020M02_dt40.log 2>&1 &

# Terminal 2: monitorear (revisa cada 60 segundos)
chmod +x monitor_croco.sh
./monitor_croco.sh salida_Y2020M02_dt40.log 60
```

---

## 5. Reinicio desde el último RST

### 5.1 Backup del RST actual

```bash
# Siempre proteger el RST antes de tocar nada
cp CROCO_FILES/croco_rst.nc CROCO_FILES/croco_rst_Y2020M02_step121441.nc
```

### 5.2 Crear `croco.in` para el reinicio

Copiar `croco.in` con los siguientes cambios:

```
# --- ORIGINAL ---
time_stepping: NTIMES   dt[sec]  NDTFAST  NINFO
               63360     40      40      1
...
initial: NRREC / filename
          -1 
    CROCO_FILES/croco_ini.nc
...
history: LDEFHIS, NWRT, NRPFHIS / filename 
            T    14400     0
    CROCO_FILES/croco_his.nc

# --- CAMBIAR A ---
time_stepping: NTIMES   dt[sec]  NDTFAST  NINFO
               48240     40      40      1     ← pasos restantes hasta Mar 1
...
initial: NRREC / filename
          -1 
    CROCO_FILES/croco_rst.nc                   ← usar RST en lugar de INI
...
history: LDEFHIS, NWRT, NRPFHIS / filename 
            F    14400     0                   ← F = no crear nuevo, appended
    CROCO_FILES/croco_his.nc
```

**Cálculo de NTIMES para el reinicio:**

```
scrum_time RST = 634 406 400 s  →  2020-02-07 16:00 UTC
scrum_time FIN = 636 336 000 s  →  2020-03-01 00:00 UTC
Δt = 1 929 600 s / 40 s/paso = 48 240 pasos
```

### 5.3 Opción: reducir dt para evitar nuevo BLOWUP

Si el crash se repite, reducir dt y ajustar ndtfast para mantener el CFL barotropico:

| dt (s) | ndtfast | dt_baro (s) | NTIMES   |
|--------|---------|-------------|----------|
| 40     | 40      | 1.00        | 48 240   |
| 30     | 30      | 1.00        | 64 320   |
| 20     | 20      | 1.00        | 96 480   |

```
# Para dt=30s:
time_stepping: NTIMES   dt[sec]  NDTFAST  NINFO
               64320     30      30      1
```

### 5.4 Investigar tile 19 (crash recurrente)

El tile 19 aparece en el BLOWUP de múltiples corridas. Localizar la zona geográfica correspondiente para revisar la batimetría o la configuración de la esponja:

```bash
# En Octave/MATLAB — con MPI_Setup se puede mapear tile -> subdomain
# O ejecutar el modelo con 1 proceso para aislar la ubicación exacta:
./croco croco.in_restart_dt30 > salida_restart_debug.log 2>&1
grep -E "NaN|WARNING|BLOWUP" salida_restart_debug.log | head -30
```

### 5.5 Verificar cobertura del forzamiento ONLINE

Confirmar que los datos de ERA/CFSR cubren el período completo hasta Mar 1 2020:

```bash
ls -la CROCO_FILES/blk/
# Debe existir croco_blk_Y2020M02.nc (o equivalente real-time)
# Si solo hay climatología (cycle_length=360), considerar generar forzamiento
# real-time para febrero-marzo 2020
```

---

## 6. Flujo organizado de trabajo post-crash

```
CRASH detectado (monitor_croco.sh)
    │
    ▼
1. Backup RST
   cp croco_rst.nc croco_rst_Y2020M02_step121441.nc

    │
    ▼
2. Diagnóstico rápido del log
   grep -E "NaN|BLOWUP|ONLINE_BULK|WRT_RST" salida_*.log | tail -30

    │
    ▼
3. Decidir acción
   ├── dt OK, causa forcing → revisar cobertura datos ERA/CFSR
   │       → regenerar croco_blk.nc si es necesario
   │
   └── dt insuficiente (CFL) → reducir dt en croco.in_restart
           → recalcular NTIMES = Δt_segundos / nuevo_dt

    │
    ▼
4. Preparar croco.in_restart
   - initial: -1 / CROCO_FILES/croco_rst.nc
   - NTIMES = 48240  (o reajustado con nuevo dt)
   - LDEFHIS = F     (continuar archivos existentes)

    │
    ▼
5. Lanzar reinicio + monitor
   nohup ./croco croco.in_restart > salida_Y2020M02_restart.log 2>&1 &
   ./monitor_croco.sh salida_Y2020M02_restart.log 60
```

---

## 7. Checklist antes de relanzar

- [ ] RST backup creado (`croco_rst_Y2020M02_step121441.nc`)
- [ ] `croco.in_restart` tiene `initial = croco_rst.nc`, `NRREC = -1`
- [ ] `NTIMES = 48240` (o ajustado al nuevo dt)
- [ ] `LDEFHIS = F` para no borrar el HIS ya escrito
- [ ] Verificar que `croco_bry.nc` y `croco_clm.nc` cubren hasta Mar 1 2020
- [ ] Verificar que `croco_blk.nc` (o forzamiento ONLINE) cubre hasta Mar 1 2020
- [ ] `monitor_croco.sh` lanzado en paralelo
- [ ] Nuevo log con nombre descriptivo (`salida_Y2020M02_restart_dt40.log`)
