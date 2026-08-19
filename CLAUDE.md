# CLAUDE.md — Tunisia (dominio CROCO)

## Propósito del proyecto

Visualización y control de calidad de la configuración del dominio CROCO
para Túnez. El trabajo activo es:

- Visualización de batimetría del dominio.
- Visualización y verificación de las fuentes de río (`psource`): posición
  (Isrc, Jsrc), orientación (Dsrc), caudal (Qbar), y si corresponden a un
  punto de grilla `rho` válido y no-tierra.
- Corrección puntual de la configuración cuando se detecta una fuente mal
  definida (ej. índice fuera de la costa, en tierra, o con orientación
  inconsistente con la batimetría local).

Contexto de referencia rápida sobre `psource` en CROCO: cada fuente se
define por índices de grilla `Isrc, Jsrc`, una dirección `Dsrc` (orientación
meridional/zonal), un caudal `Qbar` en m³/s, y flags de si trae temperatura
y salinidad. Estos valores viven en `croco.in` (o en `croco_runoff.nc` si se
usa `PSOURCE_NCFILE`), y deben coincidir en orden con el archivo netcdf
cuando se usa esa opción. Ver `croco_reference_guide.md` en esta carpeta
para el detalle ya recopilado localmente.

## Archivos sensibles — NUNCA editar directo

Estos archivos son entradas operativas del modelo. Claude **no debe
modificarlos directamente bajo ninguna circunstancia**, incluso si el
cambio parece trivial o se detecta un error evidente:

- `croco_grd.nc` — archivo de grilla (bathymetry, máscara tierra/mar, metrics).
- `croco.in` / `croco.in.rst` — namelist de configuración de la corrida.
- `run_rst.sh` — script de restart/ejecución.

**Protocolo cuando se detecta un problema en estos archivos:**
1. No tocar el original.
2. Generar una copia (`archivo.propuesto.ext` o similar) con el cambio sugerido.
3. Explicar en texto qué se cambiaría y por qué, con el diff si aplica.
4. Esperar confirmación explícita antes de que el cambio se aplique al
   archivo real (lo aplica el usuario, no Claude).

Esto aplica también a scripts que escriben sobre estos archivos in-place
(cuidado con cualquier `.py` o `.m` que abra `croco_grd.nc` en modo
escritura, o que sobreescriba `croco.in`).

## Relación entre scripts .m y .py

Migración en curso de Matlab (`crocotools`, herencia del ecosistema CROCO
clásico) a Python (`croco_pytools`, la vía moderna). Confirmado por el
usuario:

- **Los `.py` son la versión vigente.** Cuando exista un par con el mismo
  nombre base en `.m` y `.py` (ej. `psource_grd.m` / `psource_grd.py`,
  `psource_diagnostico.m` / `psource_diagnostico.py`), trabajar sobre el
  `.py`. Si hay una variante `_v2.py`, esa es la más reciente.
- **Los `.m` son legado.** Se conservan como referencia histórica pero no
  se editan ni se usan como base para trabajo nuevo, salvo pedido explícito.
- Scripts sin equivalente en el otro lenguaje (ej. `plot_psource.py`,
  `psource_scientific_maps.py`, `psource_mask_check.py` del lado Python;
  `draw_sources.m`, `psource_uv.m`, `sc.m`, `blues_cmap.m`, `src_color.m`
  del lado Matlab) son utilidades puntuales, no pares migrados — no asumir
  que tienen contraparte esperada en el otro lenguaje.

## Convenciones de trabajo

- Antes de proponer un cambio de configuración de una fuente, verificar
  contra `croco_grd.nc` (máscara y batimetría) que el punto de grilla sea
  válido — no asumir el índice como correcto solo porque está en `croco.in`.
- Preferir generar salidas nuevas (csv, png, html, svg de diagnóstico) en
  vez de sobreescribir las existentes, para no perder el historial de
  chequeos previos (ej. `psource_diagnostico.csv`, `psource_mask_check.csv`).
