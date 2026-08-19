# CROCO Ocean Model — Guía de Referencia Rápida

> **CROCO** (Coastal and Regional Ocean COmmunity model) — rama de ROMS desarrollada en IRD, INRIA, Ifremer, CNRS y Univ. Toulouse III.  
> Documentación oficial: https://croco-ocean.gitlabpages.inria.fr/croco_doc/model.html

---

## 1. Archivos principales de configuración

| Archivo | Rol |
|---|---|
| `cppdefs.h` | Activa/desactiva módulos en tiempo de compilación (`#define` / `#undef`) |
| `croco.in` | Parámetros en tiempo de ejecución (dt, archivos, salidas, etc.) |
| `cppdefs_dev.h` | Opciones avanzadas (incluido al final de `cppdefs.h`) |
| `set_global_definitions.h` | Definiciones globales derivadas (no editar directamente) |

---

## 2. `cppdefs.h` — Mapa de opciones clave

### 2.1 Selección del tipo de configuración (excluyentes)

```c
#define REGIONAL     // Configuración realista regional (ej. TUNISIA, BENGUELA)
#undef  COASTAL      // Configuración costera realista (ej. VILAINE)
// Casos académicos: UPWELLING, BASIN, SEAMOUNT, VORTEX, etc.
```

### 2.2 Paralelización

```c
#define OPENMP       // Memoria compartida
#undef  MPI          // Memoria distribuida
// OPENMP y MPI son mutuamente excluyentes en la práctica
```

### 2.3 Dinámica del modelo

```c
#define SOLVE3D      // Modo 3D (siempre para simulaciones realistas)
#define UV_COR       // Fuerza de Coriolis
#define UV_ADV       // Advección de momento
#define SALINITY     // Incluir salinidad como trazador
#define NONLIN_EOS   // Ecuación de estado no lineal (recomendado)
#define NEW_S_COORD  // Coordenadas s mejoradas (siempre recomendado)
```

### 2.4 Esquemas de advección

#### Momento horizontal (elegir uno)
```c
#define UV_HADV_UP3    // Upwind 3er orden (defecto, buen balance)
#undef  UV_HADV_UP5    // Upwind 5to orden
#undef  UV_HADV_WENO5  // WENO5 (más difusivo, robusto para zonas costeras)
```

#### Trazadores horizontal (elegir uno)
```c
#define TS_HADV_RSUP3  // RSUP3 (recomendado para regional)
#undef  TS_HADV_UP3
#undef  TS_HADV_WENO5  // WENO5 (recomendado para costero/sedimentos)
```

#### Advección vertical
```c
#define UV_VADV_SPLINES   // Splines (regional, suave)
#define TS_VADV_SPLINES
// Alternativa para costero/NBQ:
#undef  UV_VADV_WENO5
#undef  TS_VADV_WENO5
```

### 2.5 Mezcla vertical (elegir uno)

```c
#define LMD_MIXING   // KPP — recomendado para océano abierto/regional
#undef  GLS_MIXING   // GLS (k-ε, k-ω) — mejor para zonas costeras/estuarios

# ifdef LMD_MIXING
#  define LMD_SKPP    // Surface boundary layer
#  define LMD_BKPP    // Bottom boundary layer
#  define LMD_RIMIX   // Shear instability mixing
#  define LMD_CONVEC  // Convective adjustment
#  define LMD_NONLOCAL
# endif
```

### 2.6 Forzamiento superficial (Bulk Flux)

```c
#define BULK_FLUX     // Forzamiento atmosférico bulk
# ifdef BULK_FLUX
#  define BULK_GUSTINESS  // Efectos de ráfagas (COARE3p0 por defecto)
#  define BULK_LW         // Radiación de onda larga
#  define ONLINE          // Forzamiento en línea
#  ifdef ONLINE
#   define ERA_ECMWF   // Datos ERA5/ECMWF  ← regional
#   undef  AROME       // Datos AROME       ← costero
#  endif
# endif
```

### 2.7 Condiciones de contorno abiertas (OBC)

```c
#define TIDES          // Activar mareas
# ifdef TIDES
#  define SSH_TIDES    // Mareas en SSH
#  define UV_TIDES     // Mareas en velocidad
#  define POT_TIDES    // Potencial de marea
#  define TIDERAMP     // Rampa de inicio suave
# endif

#define OBC_EAST       // Abrir frontera Este
#define OBC_WEST       // Abrir frontera Oeste
#define OBC_NORTH
#define OBC_SOUTH

#define OBC_M2CHARACT  // Características para modo barotropo
#define OBC_M3ORLANSKI // Orlanski para modo barotrópico 3D
#define OBC_TORLANSKI  // Orlanski para trazadores
```

### 2.8 Forzamiento de frontera

```c
#define FRC_BRY        // Forzamiento desde archivo de frontera
# ifdef FRC_BRY
#  define Z_FRC_BRY    // SSH en frontera
#  define M2_FRC_BRY   // Velocidad barotropa
#  define M3_FRC_BRY   // Velocidad barotrópica 3D
#  define T_FRC_BRY    // Temperatura y salinidad
# endif
```

### 2.9 Aplicaciones opcionales

```c
#undef  BIOLOGY        // Modelos biogeoquímicos (PISCES, BioEBUS, etc.)
#undef  SEDIMENT       // Modelo de sedimentos USGS
#undef  MUSTANG        // Modelo de sedimentos MUSTANG
#undef  FLOATS         // Flotadores lagrangianos
#undef  STATIONS       // Estaciones de observación
#undef  PASSIVE_TRACER // Trazadores pasivos
#undef  BBL            // Bottom Boundary Layer explícita
```

### 2.10 Salidas

```c
#define AVERAGES       // Promedios temporales (recomendado)
#define AVERAGES_K     // Promedios en coordenada vertical
#undef  OUTPUTS_SURFACE
#undef  XIOS           // Servidor I/O XIOS (para MPI a gran escala)
```

---

## 3. `croco.in` — Parámetros de ejecución

### 3.1 Time stepping

```
time_stepping: NTIMES   dt[sec]  NDTFAST  NINFO
               48960     20       40       1
```

| Parámetro | Descripción |
|---|---|
| `NTIMES` | Número total de pasos de tiempo barotrópicos |
| `dt` | Paso de tiempo barotrópico [s] |
| `NDTFAST` | Subpasos del modo rápido (barotropo) por paso lento |
| `NINFO` | Frecuencia de impresión de diagnósticos en pantalla |

> **Regla práctica:** `dt` ~ 0.5–1.5 × (dx/C_max), donde C_max ≈ √(g·H_max).
> `NDTFAST` típicamente 20–60.

### 3.2 Coordenada vertical S

```
S-coord: THETA_S,   THETA_B,    Hc (m)
           7.0d0     2.0d0      200.0d0
```

| Parámetro | Rango típico | Efecto |
|---|---|---|
| `THETA_S` | 0–10 | Estiramiento hacia superficie (>0 = mayor resolución sup.) |
| `THETA_B` | 0–4  | Estiramiento hacia fondo |
| `Hc` | profundidad crítica [m] | Transición entre coordenadas σ y z |

### 3.3 Fechas

```
start_date:
2000-01-01 00:00:00

end_date:
2000-02-01 00:00:00
```

### 3.4 Archivos de entrada/salida

```
grid:        CROCO_FILES/croco_grd.nc
forcing:     CROCO_FILES/croco_frc.nc
bulk_forcing: CROCO_FILES/croco_blk.nc
climatology: CROCO_FILES/croco_clm.nc
boundary:    CROCO_FILES/croco_bry.nc
initial:     CROCO_FILES/croco_ini.nc
restart:     CROCO_FILES/croco_rst.nc
history:     CROCO_FILES/croco_his.nc
averages:    CROCO_FILES/croco_avg.nc
```

### 3.5 Frecuencias de salida

```
output_time_steps: DT_HIS(H), DT_AVG(H), DT_RST(H)
                       1           6          12
```
Valores en **horas**.

### 3.6 Campos de salida — sintaxis

```
primary_history_fields: zeta UBAR VBAR  U  V   wrtT(1:NT)
                          T    T   T   T  T    50*T
```
- `T` = escribir, `F` = no escribir
- `NT` = número de trazadores
- `50*T` = los primeros 50 trazadores activos

### 3.7 Parámetros físicos clave

```
rho0:          1025.d0          ! Densidad de referencia [kg/m³]

lateral_visc:  VISC2=0.  VISC4=0.   ! Viscosidad lateral [m²/s]

bottom_drag:   RDRG=0.    RDRG2=1.e-3   Zob=1.e-2
               Cdb_min=1.e-4  Cdb_max=0.1

nudg_cof:   TauT_in=1.  TauT_out=360.  TauM_in=3.  TauM_out=360.  [days]
```

### 3.8 Fuentes puntuales (ríos)

```
psource:   Nsrc  Isrc  Jsrc  Dsrc  Qbar[m³/s]  Lsrc  Tsrc
            N
            i    j     dir   q     T  T        T_val  S_val
```
- `Dsrc`: dirección (0=Xi, 1=Eta)
- `Lsrc`: T/F para U,V
- `Tsrc`: temperatura y salinidad de la fuente

---

## 4. Configuración actual del proyecto (referencia)

### cppdefs.h — opciones activas principales

| Opción | Estado | Efecto |
|---|---|---|
| `REGIONAL` | **ON** | Modo regional realista |
| `TUNISIA` | **ON** | Nombre de la configuración |
| `OPENMP` | **ON** | Paralelización OpenMP |
| `TIDES` + `SSH/UV/POT_TIDES` | **ON** | Mareas completas |
| `OBC_*` (4 fronteras) | **ON** | Dominio abierto en todos los lados |
| `FRC_BRY` | **ON** | Forzamiento desde archivo de frontera |
| `BULK_FLUX` + `ERA_ECMWF` | **ON** | Bulk con ERA5 |
| `LMD_MIXING` completo | **ON** | KPP con SKPP, BKPP, RIMIX, CONVEC, NONLOCAL |
| `TS_HADV_RSUP3` | **ON** | Advección horizontal trazadores RSUP3 |
| `UV_HADV_UP3` | **ON** | Advección horizontal momento UP3 |
| `AVERAGES` + `AVERAGES_K` | **ON** | Salidas promediadas |
| `SPONGE` | **ON** | Capas esponja en fronteras |
| `BIOLOGY` → `BIO_BioEBUS` | **OFF** | Biología (desactivada) |

### croco.in — configuración actual

| Parámetro | Valor | Notas |
|---|---|---|
| `dt` | 20 s | Paso barotrópico |
| `NDTFAST` | 40 | Subpasos modo rápido |
| `NTIMES` | 48960 | ≈ 1 mes (2000-01-01 → 2000-02-01) |
| `THETA_S` | 7.0 | Alta resolución superficial |
| `THETA_B` | 2.0 | Moderada resolución fondo |
| `Hc` | 200 m | Profundidad crítica |
| `DT_HIS` | 1 h | Historia horaria |
| `DT_AVG` | 6 h | Promedios cada 6 h |
| `DT_RST` | 12 h | Restart cada 12 h |

---

## 5. Flujo de trabajo típico

```
1. Editar cppdefs.h
   → Seleccionar configuración (REGIONAL/COASTAL/académica)
   → Activar módulos necesarios
   → Compilar: ./jobcomp

2. Preparar archivos NetCDF de entrada
   → croco_grd.nc   (malla)
   → croco_ini.nc   (condición inicial)
   → croco_bry.nc   (condiciones de frontera, si FRC_BRY)
   → croco_blk.nc   (forzamiento atmosférico bulk)
   → croco_frc.nc   (forzamiento de marea/climatología)

3. Editar croco.in
   → Verificar fechas (start_date, end_date)
   → Ajustar dt y NDTFAST (criterio CFL)
   → Revisar rutas de archivos (CROCO_FILES/)
   → Configurar salidas (NWRT, NAVG, campos T/F)

4. Ejecutar
   → Serial:  ./croco croco.in
   → OpenMP:  OMP_NUM_THREADS=N ./croco croco.in
   → MPI:     mpirun -np N ./croco croco.in

5. Post-proceso
   → Archivos his: croco_his.nc  (snapshots)
   → Archivos avg: croco_avg.nc  (promedios)
   → Archivos rst: croco_rst.nc  (restart)
```

---

## 6. Criterio de estabilidad CFL

```
dt_barotrópico  ≤  dx / (2 × √(g × H_max))

dt_baroclínico  ≈  dt_barotrópico × NDTFAST
                 ≤  dx / (2 × C_baro_max)   [típico: 0.5–5 m/s]
```

Ejemplo (dx=5 km, H=4000 m):
- C_max = √(9.81 × 4000) ≈ 198 m/s
- dt_baro ≤ 5000 / (2×198) ≈ 12.6 s → usar `dt=10` o `dt=12`

---

## 7. Módulos de biología disponibles

| Key en cppdefs.h | Modelo |
|---|---|
| `BIO_BioEBUS` | Ecosistema de surgencia + N₂O |
| `BIO_NChlPZD` | N-Chl-P-Z-D + oxígeno |
| `BIO_N2ChlPZD2` | Extensión 2 fitoplancton |
| `PISCES` | PISCES completo (biogeoquímica compleja) |

Activar con `#define BIOLOGY` + el modelo específico.  
Requiere archivo `croco_frcbio.nc` y `#define DIAGNOSTICS_BIO`.

---

## 8. Diagnósticos disponibles

| Key | Contenido |
|---|---|
| `DIAGNOSTICS_TS` | Balance de trazadores 3D |
| `DIAGNOSTICS_UV` | Balance de momento 3D |
| `DIAGNOSTICS_VRT` | Vorticidad y energía |
| `DIAGNOSTICS_EK` | Energía cinética |
| `DIAGNOSTICS_PV` | Vorticidad potencial |
| `DIAGNOSTICS_EDDY` | Términos de eddy |
| `DIAGNOSTICS_BIO` | Términos del modelo biológico |

Cada uno genera su propio archivo NetCDF (`croco_dia*.nc`).

---

## 9. Referencia rápida de archivos NetCDF de entrada

| Archivo | Campos típicos |
|---|---|
| `croco_grd.nc` | `h`, `mask_rho`, `lon_rho`, `lat_rho`, `pm`, `pn`, `angle`, `f` |
| `croco_ini.nc` | `temp`, `salt`, `u`, `v`, `ubar`, `vbar`, `zeta`, `ocean_time` |
| `croco_bry.nc` | `temp_east/west/north/south`, `salt_*`, `u_*`, `v_*`, `zeta_*` |
| `croco_blk.nc` | `tair`, `rhum`, `prate`, `uwnd`, `vwnd`, `radlw`, `radsw` |
| `croco_frc.nc` | `tide_Eamp`, `tide_Ephase`, `tide_Cspd`, `tide_Cangle` |

---

## 10. Recursos

- **Documentación oficial:** https://croco-ocean.gitlabpages.inria.fr/croco_doc/
- **Referencia cppdefs.h:** https://croco-ocean.gitlabpages.inria.fr/croco_doc/model/model.appendices.cppdefs.h.html
- **Referencia croco.in:** https://croco-ocean.gitlabpages.inria.fr/croco_doc/model/model.appendices.croco.in.html
- **Casos de test:** https://croco-ocean.gitlabpages.inria.fr/croco_doc/model/model.test_cases.html
- **Repositorio:** https://github.com/croco-ocean/croco
- **Foro/Issues:** https://gitlab.inria.fr/croco-ocean/croco/-/issues
