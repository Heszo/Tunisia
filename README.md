# Tunisia — dominio CROCO

Visualización y control de calidad de la configuración del dominio [CROCO](https://www.croco-ocean.org/) para Túnez.

## Objetivo

El trabajo activo en este repositorio es:

- Visualización de la batimetría del dominio.
- Visualización y verificación de las fuentes de río (`psource`): posición
  (`Isrc`, `Jsrc`), orientación (`Dsrc`), caudal (`Qbar`), y si corresponden
  a un punto de grilla `rho` válido y no-tierra.
- Corrección puntual de la configuración cuando se detecta una fuente mal
  definida (ej. índice fuera de la costa, en tierra, o con orientación
  inconsistente con la batimetría local).

### `psource` en CROCO

Cada fuente de río se define por índices de grilla `Isrc, Jsrc`, una
dirección `Dsrc` (orientación meridional/zonal, u-face o v-face), un caudal
`Qbar` en m³/s, y flags de si trae temperatura y salinidad. Estos valores
viven en `croco.in` (o en `croco_runoff.nc` si se usa `PSOURCE_NCFILE`), y
deben coincidir en orden con el archivo NetCDF cuando se usa esa opción.
Ver [`croco_reference_guide.md`](croco_reference_guide.md) para el detalle
recopilado sobre la física del staggered grid CROCO/ROMS.

## Estructura del repositorio

### Scripts vigentes (Python — `croco_pytools`)

| Script | Descripción |
|---|---|
| `psource_grd.py` | Diagnóstico de fuentes usando `mask_u`/`mask_v`/`mask_rho` de `croco_grd.nc`. Clasifica cada fuente como válida, mar abierto, tierra o fuera de grilla, y genera figura (mapa geográfico + espacio I-J + tabla) y CSV. |
| `psource_grd_v2.py` | Versión corregida de `psource_grd.py`: soluciona el manejo de `MaskedArray` de netCDF4 en las celdas de tierra (fill_value vs. 0 literal). Es la variante más reciente para este chequeo. |
| `psource_mask_check.py` | Diagnóstico de fuentes contra `mask_u`/`mask_v`, con salida `psource_mask_check.csv`. |
| `psource_diagnostico.py` | Diagnóstico interactivo con fondo OSM/NaturalEarth y distancia a costa. |
| `plot_psource.py` | Visualización interactiva de las fuentes (HTML). |
| `psource_scientific_maps.py` | Mapas científicos de calidad de publicación (SVG/PDF): mapa OSM y batimetría con overlay de `psource` coloreado por dirección de descarga. |

Todos operan sobre `croco.in` y `croco_grd.nc` en modo **solo lectura**.

> **Convención de índices:** en CROCO/Fortran los arrays 2D son `var(xi, eta)`
> con índices base-1 (`Isrc`, `Jsrc`). En Python/NetCDF el array se almacena
> como `var[eta, xi]`, por lo que `python_col = Isrc - 1` y
> `python_row = Jsrc - 1`. Esta distinción es crítica al indexar el grid
> directamente.

### Scripts legacy (Matlab — `crocotools`)

`blues_cmap.m`, `draw_sources.m`, `psource_diag.m`, `psource_grd.m`,
`psource_grids.m`, `psource_plot.m`, `psource_psi.m`, `psource_uv.m`,
`sc.m`, `src_color.m` — se conservan como referencia histórica de la
migración a Python, pero no se editan ni se usan como base para trabajo
nuevo.

### Configuración y documentación

- `croco.in` / `croco.in.rst` — namelist de configuración de la corrida.
- `run_rst.sh` — script de restart/ejecución.
- `croco_reference_guide.md` — guía de referencia sobre `psource` y la
  física del grid CROCO/ROMS.
- `CROCO_BLOWUP_Y2020M02.md` — notas sobre un incidente de blow-up del
  modelo.

### Salidas de diagnóstico versionadas

Los `.csv` (`psource_diagnostico.csv`, `psource_grd.csv`,
`psource_mask_check.csv`) se versionan como referencia de resultados
previos. Las figuras (`.png`, `.pdf`, `.svg`, `.html`) y el archivo de
grilla `croco_grd.nc` (56 MB) no se versionan — son regenerables desde los
scripts o son datos de entrada del modelo (ver `.gitignore`).

## Uso

```bash
pip install netCDF4 numpy pandas matplotlib

python psource_grd_v2.py --croco_in croco.in --grd croco_grd.nc
```

Genera `psource_grd.png` y `psource_grd.csv` con el diagnóstico de todas
las fuentes.

## Archivos sensibles — no editar directamente

`croco_grd.nc`, `croco.in` / `croco.in.rst` y `run_rst.sh` son entradas
operativas del modelo. Ante un error detectado en estos archivos, el
protocolo es generar una copia propuesta (`archivo.propuesto.ext`) con el
cambio sugerido y explicar el diff — nunca modificarlos in-place sin
confirmación explícita. Ver [`CLAUDE.md`](CLAUDE.md) para el detalle
completo de estas convenciones de trabajo.

## Licencia

Este proyecto está bajo licencia MIT — ver [`LICENSE`](LICENSE).
