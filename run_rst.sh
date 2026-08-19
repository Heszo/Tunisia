#!/bin/bash
# =============================================================
# run_rst.sh — Lanzar CROCO desde restart Y2020M02
#
# RST de entrada : CROCO_FILES/croco_rst.nc  (paso 121441)
# Período        : 2020-02-07 16:00 → 2020-03-01 00:00 UTC
# dt             : 20s  (reducido desde 40s para evitar BLOWUP)
#
# Uso:
#   chmod +x run_rst.sh
#   ./run_rst.sh
# =============================================================

set -euo pipefail

# ---------------------------------------------------------
# CONFIGURACIÓN — ajustar según el entorno
# ---------------------------------------------------------
CROCO_EXE="./croco"
INPUT="croco.in.rst"
LOGFILE="salida_Y2020M02_rst_dt20.log"
OMP_THREADS=20
RST_BACKUP="CROCO_FILES/croco_rst_Y2020M02_step121441.nc"
RST_FILE="CROCO_FILES/croco_rst.nc"

# ---------------------------------------------------------
# 1. Verificar que el ejecutable existe
# ---------------------------------------------------------
if [[ ! -x "$CROCO_EXE" ]]; then
    echo "[ERROR] No se encuentra el ejecutable: $CROCO_EXE"
    exit 1
fi

# ---------------------------------------------------------
# 2. Verificar que el RST existe y no está vacío
# ---------------------------------------------------------
if [[ ! -s "$RST_FILE" ]]; then
    echo "[ERROR] Archivo RST no encontrado o vacío: $RST_FILE"
    exit 1
fi

echo "=================================================="
echo " CROCO RESTART — Tunisia Y2020M02"
echo "=================================================="
echo " RST input   : $RST_FILE"
echo " Input file  : $INPUT"
echo " Log         : $LOGFILE"
echo " OMP threads : $OMP_THREADS"
echo " dt          : 20s  (NTIMES=96479)"
echo "=================================================="

# ---------------------------------------------------------
# 3. Backup del RST antes de sobrescribirlo
# ---------------------------------------------------------
if [[ ! -f "$RST_BACKUP" ]]; then
    echo "[INFO] Creando backup del RST..."
    cp "$RST_FILE" "$RST_BACKUP"
    echo "[OK]  Backup: $RST_BACKUP"
else
    echo "[OK]  Backup ya existe: $RST_BACKUP"
fi

# ---------------------------------------------------------
# 4. Lanzar el modelo
# ---------------------------------------------------------
echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Lanzando CROCO..."
echo ""

export OMP_NUM_THREADS=$OMP_THREADS

nohup $CROCO_EXE $INPUT > $LOGFILE 2>&1 &
PID=$!

echo "[OK]  PID = $PID"
echo "[OK]  Log en tiempo real: tail -f $LOGFILE"
echo ""

# ---------------------------------------------------------
# 5. Monitor inline — espera inicio y reporta cada 5 min
# ---------------------------------------------------------
echo "[INFO] Esperando inicio del time-stepping..."
for i in $(seq 1 30); do
    sleep 10
    if grep -q "MAIN: started time-stepping" "$LOGFILE" 2>/dev/null; then
        echo "[OK]  Modelo corriendo. Monitoreando cada 5 min (Ctrl+C para salir)"
        break
    fi
done

while kill -0 $PID 2>/dev/null; do
    sleep 300
    if grep -q "MAIN: Abnormal termination: BLOWUP" "$LOGFILE" 2>/dev/null; then
        LAST=$(grep -E "^\s+[0-9]+ +[0-9]+\." "$LOGFILE" | tail -2)
        echo ""
        echo "=========================================="
        echo "[CRASH] BLOWUP detectado — $(date '+%Y-%m-%d %H:%M:%S')"
        echo "$LAST"
        echo "=========================================="
        exit 2
    fi
    LAST_STEP=$(grep -E "^\s+[0-9]+ +[0-9]+\." "$LOGFILE" 2>/dev/null | tail -1 | awk '{print "paso="$1, "día="$2}')
    echo "[$(date '+%H:%M:%S')] $LAST_STEP"
done

# ---------------------------------------------------------
# 6. Verificar terminación normal
# ---------------------------------------------------------
echo ""
if grep -q "MAIN: DONE" "$LOGFILE" 2>/dev/null; then
    echo "[DONE] Corrida completada exitosamente."
    RST_RECS=$(grep "WRT_RST" "$LOGFILE" | wc -l)
    HIS_RECS=$(grep "WRT_HIS" "$LOGFILE" | wc -l)
    AVG_RECS=$(grep "WRT_AVG" "$LOGFILE" | wc -l)
    echo "       RST escritos : $RST_RECS"
    echo "       HIS escritos : $HIS_RECS"
    echo "       AVG escritos : $AVG_RECS"
elif grep -q "BLOWUP" "$LOGFILE" 2>/dev/null; then
    echo "[FAIL] BLOWUP — revisar log: $LOGFILE"
    exit 2
else
    echo "[WARN] Terminación sin confirmar — revisar log: $LOGFILE"
fi
