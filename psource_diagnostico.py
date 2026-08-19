"""
psource_diagnostico.py
======================
Diagnóstico interactivo de fuentes de ríos CROCO.

Genera:
  1. psource_diagnostico.png  – figura estática con OSM + NaturalEarth coastline
  2. psource_sospechosos.csv  – tabla de puntos a revisar
  3. psource_todos.csv        – tabla completa con distancia a costa

Uso:
    python psource_diagnostico.py --croco_in croco.in

Dependencias:
    pip install geopandas shapely contextily mplcursors matplotlib pandas
"""

import argparse, re, os, sys, warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import geopandas as gpd
from shapely.geometry import Point, MultiPolygon
from shapely.ops import nearest_points, unary_union

# ─────────────────────────────────────────────────────────────────────────────
# 1. Parser croco.in
# ─────────────────────────────────────────────────────────────────────────────

def parse_psource(path):
    with open(path) as f:
        lines = f.readlines()

    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r'^psource\s*:', s) and 'ncfile' not in s:
            start = i; break
    if start is None:
        raise ValueError("No se encontró 'psource:' en el archivo.")

    nsrc = None; data_start = None
    for i in range(start+1, len(lines)):
        s = lines[i].strip()
        if s and re.match(r'^\d+$', s):
            nsrc = int(s); data_start = i+1; break

    records = []
    for i in range(data_start, len(lines)):
        parts = lines[i].strip().split()
        if len(parts) < 8: break
        try:
            records.append(dict(
                idx      = len(records)+1,
                isrc     = int(parts[0]),
                jsrc     = int(parts[1]),
                py_col   = int(parts[0])-1,
                py_row   = int(parts[1])-1,
                dsrc     = int(parts[2]),
                qbar     = float(parts[3]),
                lsrc     = parts[4].upper()=='T',
                tsrc     = parts[5].upper()=='T',
                lon      = float(parts[6]),
                lat      = float(parts[7]),
            ))
        except: break
        if len(records) >= nsrc: break

    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Geometría: tierra y distancia a costa
# ─────────────────────────────────────────────────────────────────────────────

def load_land_geometry(geojson_path='/tmp/countries.geojson'):
    """Carga el polígono de tierra y calcula la frontera costera."""
    world = gpd.read_file(geojson_path)
    land  = world.union_all()
    coast = land.boundary          # línea costera
    return land, coast


def enrich_df(df, land, coast):
    """
    Añade al DataFrame:
      on_land       : bool, el punto está dentro del polígono de tierra
      dist_coast_dd : distancia al coast en grados decimales
      status        : 'tierra', 'costera', 'oceano'
    """
    pts = [Point(r.lon, r.lat) for _, r in df.iterrows()]

    on_land = np.array([land.contains(p) for p in pts])

    # Distancia al borde costero (en grados → ~111 km/°)
    dist_coast = np.array([coast.distance(p) for p in pts])
    dist_coast_km = dist_coast * 111.0

    # Clasificación:
    # - tierra:   on_land y dist_coast_km > 1.5 km  (claramente tierra adentro)
    # - costera:  on_land y dist_coast_km <= 1.5 km (borde, puede ser OK)
    # - oceano:   ~on_land
    UMBRAL_KM = 1.5
    status = np.where(
        ~on_land, 'oceano',
        np.where(dist_coast_km <= UMBRAL_KM, 'costera', 'tierra')
    )

    df = df.copy()
    df['on_land']      = on_land
    df['dist_coast_km']= dist_coast_km.round(3)
    df['status']       = status
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. Figura de diagnóstico
# ─────────────────────────────────────────────────────────────────────────────

STATUS_COLOR = {
    'oceano'  : '#0077b6',   # azul – OK
    'costera' : '#f4a261',   # naranja – borde, revisar
    'tierra'  : '#d62828',   # rojo – problema claro
}
STATUS_MARKER = {
    'oceano'  : 'o',
    'costera' : 's',
    'tierra'  : '^',
}
DIR_LABELS = {0: 'Xi (W–E)', 1: 'Eta (S–N)', -1: 'Negativa'}

def make_diagnostics_figure(df, land, coast, world_gdf, output_png):
    """
    Dos paneles:
      Izquierda  – mapa geográfico de toda la región
      Derecha    – zoom en los puntos sospechosos
    """
    sosp = df[df['status'] != 'oceano']

    # Recorte geográfico
    pad = 0.4
    lon_min, lon_max = df.lon.min()-pad, df.lon.max()+pad
    lat_min, lat_max = df.lat.min()-pad, df.lat.max()+pad

    fig, axes = plt.subplots(1, 2, figsize=(18, 10),
                             gridspec_kw={'width_ratios': [1.4, 1]})
    fig.patch.set_facecolor('#f0f4f8')

    for ax in axes:
        ax.set_facecolor('#caf0f8')

    # ── Panel izquierdo: región completa ──────────────────────────────────
    ax = axes[0]

    # Tierra (NaturalEarth)
    land_gdf = world_gdf.cx[lon_min:lon_max, lat_min:lat_max]
    land_gdf.plot(ax=ax, color='#e9c46a', edgecolor='#264653',
                  linewidth=0.6, zorder=2)

    # Todos los puntos
    for status, grp in df.groupby('status'):
        ax.scatter(grp.lon, grp.lat,
                   c=STATUS_COLOR[status],
                   marker=STATUS_MARKER[status],
                   s=70, zorder=5, linewidths=0.8,
                   edgecolors='white',
                   label=f"{status.capitalize()} ({len(grp)})")

    # Etiquetas de puntos problemáticos
    for _, row in df[df['status']=='tierra'].iterrows():
        ax.annotate(f"#{row.idx}\n({row.isrc},{row.jsrc})",
                    xy=(row.lon, row.lat),
                    xytext=(6, 6), textcoords='offset points',
                    fontsize=6.5, color='#d62828',
                    bbox=dict(boxstyle='round,pad=0.2',
                              fc='white', ec='#d62828', alpha=0.7),
                    zorder=8)

    ax.set_xlim(lon_min, lon_max)
    ax.set_ylim(lat_min, lat_max)
    ax.set_xlabel('Longitud (°E)', fontsize=10)
    ax.set_ylabel('Latitud (°N)', fontsize=10)
    ax.set_title('Diagnóstico psource — Región completa\n'
                 '(NaturalEarth + umbral 1.5 km desde costa)',
                 fontsize=11, fontweight='bold')
    ax.grid(True, linestyle='--', linewidth=0.4, color='#aaa', zorder=1)
    ax.set_aspect('equal')

    # Leyenda de estado
    handles_status = [
        mpatches.Patch(color=c, label=f'{s.capitalize()}')
        for s, c in STATUS_COLOR.items()
    ]
    handles_dir = [
        Line2D([0],[0], marker='o', color='w',
               markerfacecolor='gray', markersize=7,
               label=f'Dir {v}')
        for k, v in DIR_LABELS.items()
    ]
    leg1 = ax.legend(handles=handles_status,
                     title='Estado', loc='lower left',
                     fontsize=8, title_fontsize=9,
                     framealpha=0.88)
    ax.add_artist(leg1)

    # ── Panel derecho: scatter I vs J en espacio de grilla ───────────────
    ax2 = axes[1]
    ax2.set_facecolor('#ffffff')

    for status, grp in df.groupby('status'):
        ax2.scatter(grp.isrc, grp.jsrc,
                    c=STATUS_COLOR[status],
                    marker=STATUS_MARKER[status],
                    s=80, zorder=4,
                    linewidths=0.8, edgecolors='#444',
                    label=f"{status.capitalize()} ({len(grp)})")

    # Etiquetas en el espacio de grilla
    for _, row in df.iterrows():
        color = STATUS_COLOR[row.status]
        ax2.annotate(f"#{int(row.idx)}",
                     xy=(row.isrc, row.jsrc),
                     xytext=(3, 3), textcoords='offset points',
                     fontsize=5.5, color=color, zorder=6)

    # Recuadro de sospechosos
    if len(sosp):
        pad2 = 3
        rect = mpatches.FancyBboxPatch(
            (sosp.isrc.min()-pad2, sosp.jsrc.min()-pad2),
            sosp.isrc.max()-sosp.isrc.min()+2*pad2,
            sosp.jsrc.max()-sosp.jsrc.min()+2*pad2,
            boxstyle='round,pad=1',
            linewidth=1.2, linestyle='--',
            edgecolor='#d62828', facecolor='none', zorder=3)
        ax2.add_patch(rect)

    ax2.set_xlabel('I  (Fortran xi, base-1)   →   Python col = I−1',
                   fontsize=9)
    ax2.set_ylabel('J  (Fortran eta, base-1)  →   Python row = J−1',
                   fontsize=9)
    ax2.set_title('Espacio de grilla (I, J Fortran)\n'
                  'Marcador ▲ = claramente en tierra · ■ = borde costero',
                  fontsize=11, fontweight='bold')
    ax2.grid(True, linestyle='--', linewidth=0.35, color='#ccc', zorder=1)
    ax2.legend(title='Estado', fontsize=8, title_fontsize=9,
               loc='best', framealpha=0.9)

    # Caja de conversión de índices
    ax2.text(0.98, 0.02,
             "Fortran → NumPy\narray[J−1, I−1]\ncol = I−1 · row = J−1",
             transform=ax2.transAxes,
             fontsize=7.5, va='bottom', ha='right',
             bbox=dict(boxstyle='round', fc='#fffde7',
                       ec='#bbb', alpha=0.9))

    # Tabla resumen dentro de la figura
    n_ok    = (df.status=='oceano').sum()
    n_borde = (df.status=='costera').sum()
    n_tierra= (df.status=='tierra').sum()
    fig.text(0.5, 0.01,
             f"Total: {len(df)} fuentes  |  "
             f"✓ Océano: {n_ok}  |  "
             f"⚠ Borde (<1.5 km): {n_borde}  |  "
             f"✗ Tierra: {n_tierra}",
             ha='center', fontsize=11,
             color='#264653', fontweight='bold')

    plt.tight_layout(rect=[0, 0.04, 1, 1])
    plt.savefig(output_png, dpi=160, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  → {output_png}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Figura detallada de sospechosos
# ─────────────────────────────────────────────────────────────────────────────

def make_suspects_figure(df, land_gdf, output_png):
    """Mini-mapas individuales para cada punto sospechoso."""
    sosp = df[df['status'] != 'oceano'].reset_index(drop=True)
    if len(sosp) == 0:
        print("  ✓ No hay puntos sospechosos.")
        return

    n = len(sosp)
    ncols = min(5, n)
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(ncols*3.2, nrows*3.0),
                             squeeze=False)
    fig.patch.set_facecolor('#f0f4f8')

    for idx, (_, row) in enumerate(sosp.iterrows()):
        ax = axes[idx // ncols][idx % ncols]
        delta = 0.15

        # Recorte local
        local = land_gdf.cx[row.lon-delta:row.lon+delta,
                             row.lat-delta:row.lat+delta]
        ax.set_facecolor('#caf0f8')
        if len(local):
            local.plot(ax=ax, color='#e9c46a',
                       edgecolor='#264653', linewidth=0.7, zorder=2)

        # Punto
        color = STATUS_COLOR[row.status]
        ax.scatter([row.lon], [row.lat],
                   c=color, s=120, zorder=5,
                   edgecolors='white', linewidths=1.2,
                   marker=STATUS_MARKER[row.status])

        ax.set_xlim(row.lon-delta, row.lon+delta)
        ax.set_ylim(row.lat-delta, row.lat+delta)
        ax.set_aspect('equal')
        ax.grid(True, linestyle='--', linewidth=0.3, color='#aaa', zorder=1)
        ax.tick_params(labelsize=5)

        estado_emoji = '✗' if row.status=='tierra' else '⚠'
        ax.set_title(
            f"{estado_emoji} Fuente #{int(row.idx)}\n"
            f"I={row.isrc} J={row.jsrc}\n"
            f"({row.lon:.3f}°, {row.lat:.3f}°)\n"
            f"d_costa={row.dist_coast_km:.2f} km",
            fontsize=6.5, color=color, fontweight='bold', pad=3
        )

    # Apaga ejes sobrantes
    for extra in range(n, nrows*ncols):
        axes[extra // ncols][extra % ncols].axis('off')

    plt.suptitle('Fuentes psource sospechosas — Vista detallada\n'
                 '(▲ tierra · ■ borde costero)',
                 fontsize=12, fontweight='bold', y=1.01)
    plt.tight_layout()
    plt.savefig(output_png, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  → {output_png}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--croco_in',    default='croco.in')
    parser.add_argument('--geojson',     default='/tmp/countries.geojson')
    parser.add_argument('--out_diag',    default='psource_diagnostico.png')
    parser.add_argument('--out_detail',  default='psource_sospechosos.png')
    parser.add_argument('--out_csv',     default='psource_diagnostico.csv')
    args = parser.parse_args()

    print(f"\n[1/4] Leyendo '{args.croco_in}' ...")
    df = parse_psource(args.croco_in)
    print(f"  → {len(df)} fuentes")

    print(f"\n[2/4] Cargando geometría de tierra ...")
    world_gdf = gpd.read_file(args.geojson)
    land, coast = load_land_geometry(args.geojson)

    print(f"\n[3/4] Clasificando puntos ...")
    df = enrich_df(df, land, coast)

    print(f"\n  Estado de las {len(df)} fuentes:")
    for s, g in df.groupby('status'):
        print(f"    {s:10s}: {len(g):3d} puntos")

    # Guardar CSV
    df.to_csv(args.out_csv, index=False, float_format='%.4f')
    print(f"\n  → CSV: {args.out_csv}")

    sosp = df[df['status'] != 'oceano']
    if len(sosp):
        print(f"\n  ⚠  Puntos a revisar (dist_costa < 1.5 km o en tierra):")
        print(sosp[['idx','isrc','jsrc','dsrc','lon','lat',
                     'dist_coast_km','status']].to_string(index=False))

    print(f"\n[4/4] Generando figuras ...")
    make_diagnostics_figure(df, land, coast, world_gdf, args.out_diag)
    make_suspects_figure(df, world_gdf, args.out_detail)

    print("\n¡Listo! Archivos generados:")
    for f in [args.out_diag, args.out_detail, args.out_csv]:
        size = os.path.getsize(f)/1024 if os.path.exists(f) else 0
        print(f"  {f}  ({size:.0f} KB)")

if __name__ == '__main__':
    main()
