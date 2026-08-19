"""
psource_mask_check.py
=====================
Diagnóstico correcto de fuentes de ríos CROCO usando las máscaras
mask_u / mask_v del archivo croco_grd.nc.

FÍSICA DEL PSOURCE (según doc oficial CROCO):
──────────────────────────────────────────────
  dsrc=0 → flujo cruza una u-face  (entre rho(I,J) y rho(I+1,J))
            Isrc,Jsrc = índice Fortran del u-point
            Verificar: mask_u[Jsrc-1, Isrc-1]  (Python base-0)
              mask_u = 0  → borde tierra-mar  ✓ VÁLIDO
              mask_u = 1  → ambas celdas rho son agua  ✗ MAL (flujo en mar abierto)
              Además: al menos una celda rho adyacente debe ser agua

  dsrc=1 → flujo cruza una v-face  (entre rho(I,J) y rho(I,J+1))
            Isrc,Jsrc = índice Fortran del v-point
            Verificar: mask_v[Jsrc-1, Isrc-1]  (Python base-0)
              mask_v = 0  → borde tierra-mar  ✓ VÁLIDO
              mask_v = 1  → ambas celdas rho son agua  ✗ MAL

STAGGERING CROCO/ROMS (grid Tunisia: xi_rho=512, eta_rho=511):
  mask_u  (eta_u=511, xi_u=511)    → u-point(I,J) entre rho(I,J) y rho(I+1,J)
  mask_v  (eta_v=510, xi_v=512)    → v-point(I,J) entre rho(I,J) y rho(I,J+1)
  mask_rho(eta_rho=511, xi_rho=512)

Uso:
    python psource_mask_check.py --croco_in croco.in --grd croco_grd.nc
    python psource_mask_check.py --croco_in croco.in  # solo con NaturalEarth

Dependencias:
    pip install netCDF4 numpy pandas matplotlib geopandas
"""

import argparse, re, os, sys, warnings
warnings.filterwarnings('ignore')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D
import geopandas as gpd
from shapely.geometry import Point


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
                idx    = len(records)+1,
                isrc   = int(parts[0]),    # Fortran xi-index, base-1
                jsrc   = int(parts[1]),    # Fortran eta-index, base-1
                py_col = int(parts[0])-1,  # Python col (xi)
                py_row = int(parts[1])-1,  # Python row (eta)
                dsrc   = int(parts[2]),
                qbar   = float(parts[3]),
                lon    = float(parts[6]),
                lat    = float(parts[7]),
            ))
        except: break
        if len(records) >= nsrc: break
    return pd.DataFrame(records)


def parse_grid_path(croco_in_path):
    with open(croco_in_path) as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('grid:'):
            for j in range(i+1, min(i+5, len(lines))):
                c = lines[j].strip()
                if c and not c.startswith('#'):
                    return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lectura del grid NetCDF
# ─────────────────────────────────────────────────────────────────────────────

def load_grid(grd_path):
    try:
        from netCDF4 import Dataset
        if not os.path.exists(grd_path):
            print(f"  ⚠  Grid no encontrado: '{grd_path}'")
            return None
        ds = Dataset(grd_path)
        grid = dict(
            lon_rho  = ds.variables['lon_rho'][:],
            lat_rho  = ds.variables['lat_rho'][:],
            mask_rho = ds.variables['mask_rho'][:],   # (eta_rho, xi_rho)
            mask_u   = ds.variables['mask_u'][:],     # (eta_u, xi_u)
            mask_v   = ds.variables['mask_v'][:],     # (eta_v, xi_v)
            lon_u    = ds.variables.get('lon_u', None),
            lat_u    = ds.variables.get('lat_u', None),
            lon_v    = ds.variables.get('lon_v', None),
            lat_v    = ds.variables.get('lat_v', None),
        )
        if grid['lon_u'] is not None:
            grid['lon_u'] = grid['lon_u'][:]
            grid['lat_u'] = grid['lat_u'][:]
        if grid['lon_v'] is not None:
            grid['lon_v'] = grid['lon_v'][:]
            grid['lat_v'] = grid['lat_v'][:]
        neta, nxi = grid['lon_rho'].shape
        print(f"  → Grid cargado: xi_rho={nxi}, eta_rho={neta}")
        print(f"    mask_u: {grid['mask_u'].shape}  mask_v: {grid['mask_v'].shape}")
        ds.close()
        return grid
    except ImportError:
        print("  ⚠  netCDF4 no instalado")
        return None
    except Exception as e:
        print(f"  ⚠  Error: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Diagnóstico con máscaras
# ─────────────────────────────────────────────────────────────────────────────

def diagnose_with_masks(df, grid):
    """
    Verifica cada fuente contra mask_u o mask_v según dsrc.

    Regla (ver doc oficial CROCO):
      mask_u / mask_v = product of adjacent rho masks
        = 1  → ambas celdas rho vecinas son agua  → flujo en mar abierto ✗
        = 0  → al menos una celda rho es tierra   → puede ser borde ✓

    Para que sea un borde VÁLIDO tierra→mar:
      Exactamente UNA celda rho adyacente debe ser tierra (mask_rho=0)
      y la otra debe ser agua (mask_rho=1).
    """
    mask_u   = grid['mask_u']    # (eta_u, xi_u)
    mask_v   = grid['mask_v']    # (eta_v, xi_v)
    mask_rho = grid['mask_rho']  # (eta_rho, xi_rho)
    neta_rho, nxi_rho = mask_rho.shape

    results = []
    for _, row in df.iterrows():
        I = row.isrc      # Fortran 1-based xi
        J = row.jsrc      # Fortran 1-based eta
        pi = row.py_col   # Python col = I-1
        pj = row.py_row   # Python row = J-1

        if row.dsrc == 0:
            # u-face: entre rho(I, J) y rho(I+1, J)
            # Python: mask_u[pj, pi]
            face_label = 'u-face'
            try:
                face_mask = float(mask_u[pj, pi])
            except IndexError:
                face_mask = np.nan

            # Celdas rho adyacentes: (J, I) y (J, I+1) en Fortran
            #   Python: [pj, pi] y [pj, pi+1]
            try:
                rho_a = float(mask_rho[pj, pi])      # rho(I, J)
            except: rho_a = np.nan
            try:
                rho_b = float(mask_rho[pj, pi+1])    # rho(I+1, J)
            except: rho_b = np.nan

            # Celda receptora según signo de qbar
            # Qbar>0: flujo en +xi → entra a rho(I+1,J) → rho_b
            # Qbar<0: flujo en -xi → entra a rho(I,J)   → rho_a
            recv = rho_b if row.qbar >= 0 else rho_a
            send = rho_a if row.qbar >= 0 else rho_b

        elif row.dsrc == 1:
            # v-face: entre rho(I, J) y rho(I, J+1)
            # Python: mask_v[pj, pi]
            face_label = 'v-face'
            try:
                face_mask = float(mask_v[pj, pi])
            except IndexError:
                face_mask = np.nan

            # Celdas rho adyacentes: (J, I) y (J+1, I) en Fortran
            try:
                rho_a = float(mask_rho[pj,   pi])   # rho(I, J)
            except: rho_a = np.nan
            try:
                rho_b = float(mask_rho[pj+1, pi])   # rho(I, J+1)
            except: rho_b = np.nan

            # Qbar>0: flujo en +eta → entra a rho(I,J+1) → rho_b
            recv = rho_b if row.qbar >= 0 else rho_a
            send = rho_a if row.qbar >= 0 else rho_b
        else:
            face_label = '?-face'
            face_mask = np.nan
            rho_a = rho_b = recv = send = np.nan

        # ── Clasificación ────────────────────────────────────────────────
        # VÁLIDO: recv=1 (agua) y send=0 (tierra) → borde correcto
        # ADVERTENCIA: recv=1 pero send=1 → fuente en mar abierto
        # ERROR: recv=0 → celda receptora es tierra
        if np.isnan(face_mask):
            status = 'fuera_de_grilla'
        elif recv == 1.0 and send == 0.0:
            status = 'valido'          # borde tierra→mar correcto
        elif recv == 1.0 and send == 1.0:
            status = 'mar_abierto'     # ambas celdas son agua
        elif recv == 0.0:
            status = 'tierra'          # celda receptora es tierra ✗ ERROR
        else:
            status = 'indefinido'

        results.append(dict(
            face_label=face_label,
            face_mask=face_mask,
            rho_receptor=recv,
            rho_emisor=send,
            status=status,
        ))

    result_df = pd.DataFrame(results)
    return pd.concat([df.reset_index(drop=True), result_df], axis=1)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Figuras
# ─────────────────────────────────────────────────────────────────────────────

STATUS_COLOR = {
    'valido'          : '#0077b6',
    'mar_abierto'     : '#f4a261',
    'tierra'          : '#d62828',
    'fuera_de_grilla' : '#adb5bd',
    'indefinido'      : '#6c757d',
    # fallback (sin grid)
    'oceano'          : '#0077b6',
    'costera'         : '#f4a261',
}
STATUS_MARKER = {
    'valido'      : 'o', 'mar_abierto': 's',
    'tierra'      : '^', 'fuera_de_grilla': 'x',
    'indefinido'  : 'D',
    'oceano'      : 'o', 'costera'    : 's',
}
STATUS_LABEL = {
    'valido'         : '✓ Válido (borde tierra→mar)',
    'mar_abierto'    : '⚠ Mar abierto (ambas celdas=agua)',
    'tierra'         : '✗ En tierra (celda receptora=tierra)',
    'fuera_de_grilla': '? Fuera de grilla',
    'indefinido'     : '? Indefinido',
    'oceano'         : '✓ Océano (NE)',
    'costera'        : '⚠ Costera (NE)',
}

def make_full_figure(df, world_gdf, grid, output_png):
    fig = plt.figure(figsize=(20, 11), facecolor='#f0f4f8')
    gs  = gridspec.GridSpec(1, 3, figure=fig, wspace=0.35,
                            left=0.04, right=0.97, top=0.92, bottom=0.08)

    ax_map  = fig.add_subplot(gs[0])    # Mapa geográfico
    ax_grid = fig.add_subplot(gs[1])    # Espacio I-J
    ax_tab  = fig.add_subplot(gs[2])    # Tabla sospechosos
    ax_tab.axis('off')

    pad = 0.4
    lon_min = df.lon.min()-pad; lon_max = df.lon.max()+pad
    lat_min = df.lat.min()-pad; lat_max = df.lat.max()+pad

    # ── Panel 1: Mapa geográfico ──────────────────────────────────────────
    ax_map.set_facecolor('#caf0f8')
    land_clip = world_gdf.cx[lon_min:lon_max, lat_min:lat_max]
    if len(land_clip):
        land_clip.plot(ax=ax_map, color='#e9c46a',
                       edgecolor='#264653', linewidth=0.5, zorder=2)

    for status, grp in df.groupby('status'):
        ax_map.scatter(grp.lon, grp.lat,
                       c=STATUS_COLOR.get(status, '#999'),
                       marker=STATUS_MARKER.get(status, 'o'),
                       s=75, zorder=5, linewidths=0.7, edgecolors='white',
                       label=STATUS_LABEL.get(status, status))

    # Etiquetas de problemáticos
    for _, r in df[df['status'].isin(['tierra','mar_abierto'])].iterrows():
        ax_map.annotate(f"#{int(r.idx)}",
                        xy=(r.lon, r.lat), xytext=(5, 4),
                        textcoords='offset points', fontsize=6.5,
                        color=STATUS_COLOR.get(r.status,'#999'),
                        bbox=dict(boxstyle='round,pad=0.2',
                                  fc='white', ec=STATUS_COLOR.get(r.status,'#999'),
                                  alpha=0.75),
                        zorder=8)

    ax_map.set_xlim(lon_min, lon_max); ax_map.set_ylim(lat_min, lat_max)
    ax_map.set_aspect('equal')
    ax_map.set_xlabel('Longitud (°E)', fontsize=9)
    ax_map.set_ylabel('Latitud (°N)', fontsize=9)
    title_src = 'mask_u / mask_v (grd)' if grid else 'NaturalEarth (proxy)'
    ax_map.set_title(f'Mapa geográfico\n({title_src})',
                     fontsize=10, fontweight='bold')
    ax_map.grid(True, ls='--', lw=0.4, color='#aaa', zorder=1)
    ax_map.legend(fontsize=7, title='Estado', title_fontsize=8,
                  loc='lower left', framealpha=0.88)

    # ── Panel 2: Espacio I-J ──────────────────────────────────────────────
    ax_grid.set_facecolor('#ffffff')

    # Fondo: máscara del grid si disponible
    if grid is not None:
        mask_rho = grid['mask_rho']
        neta, nxi = mask_rho.shape
        step = max(1, nxi*neta // 15000)
        jj, ii = np.meshgrid(np.arange(neta), np.arange(nxi), indexing='ij')
        m_flat  = mask_rho.ravel()[::step]
        ii_flat = ii.ravel()[::step] + 1   # back to Fortran I
        jj_flat = jj.ravel()[::step] + 1
        # Ocean
        sea = m_flat == 1
        ax_grid.scatter(ii_flat[sea], jj_flat[sea],
                        c='#caf0f8', s=1.5, zorder=1, linewidths=0)
        # Land
        lnd = m_flat == 0
        ax_grid.scatter(ii_flat[lnd], jj_flat[lnd],
                        c='#e9c46a', s=1.5, zorder=1, linewidths=0)

    for status, grp in df.groupby('status'):
        ax_grid.scatter(grp.isrc, grp.jsrc,
                        c=STATUS_COLOR.get(status, '#999'),
                        marker=STATUS_MARKER.get(status, 'o'),
                        s=80, zorder=6, linewidths=0.8, edgecolors='#333',
                        label=STATUS_LABEL.get(status, status))

    # Etiquetas
    for _, r in df.iterrows():
        ax_grid.annotate(f"#{int(r.idx)}",
                         xy=(r.isrc, r.jsrc), xytext=(2, 2),
                         textcoords='offset points', fontsize=5,
                         color=STATUS_COLOR.get(r.status, '#555'), zorder=7)

    # Flechas de dirección
    for _, r in df.iterrows():
        dx = 1.5 if r.dsrc == 0 else 0
        dy = 1.5 if r.dsrc == 1 else 0
        if r.qbar < 0:
            dx, dy = -dx, -dy
        if dx or dy:
            ax_grid.annotate('',
                xy=(r.isrc+dx, r.jsrc+dy),
                xytext=(r.isrc, r.jsrc),
                arrowprops=dict(
                    arrowstyle='->', color=STATUS_COLOR.get(r.status,'#888'),
                    lw=0.9))

    ax_grid.set_xlabel('I  (Fortran xi, base-1)  /  Python col = I−1', fontsize=8)
    ax_grid.set_ylabel('J  (Fortran eta, base-1)  /  Python row = J−1', fontsize=8)
    ax_grid.set_title('Espacio de grilla (I, J)\nAzul=mar · Ocre=tierra',
                      fontsize=10, fontweight='bold')
    ax_grid.grid(True, ls='--', lw=0.3, color='#ccc', zorder=0)
    if grid is not None:
        ax_grid.set_xlim(df.isrc.min()-10, df.isrc.max()+10)
        ax_grid.set_ylim(df.jsrc.min()-10, df.jsrc.max()+10)
    ax_grid.legend(fontsize=6.5, title='Estado', title_fontsize=7.5,
                   loc='best', framealpha=0.9)

    # Caja de conversión
    ax_grid.text(0.99, 0.01,
                 "dsrc=0 → u-face: mask_u[J−1, I−1]\n"
                 "dsrc=1 → v-face: mask_v[J−1, I−1]\n"
                 "mask=0: borde ✓  mask=1: mar abierto ✗\n"
                 "Python: array[J−1, I−1]",
                 transform=ax_grid.transAxes, fontsize=7,
                 va='bottom', ha='right',
                 bbox=dict(boxstyle='round', fc='#fffde7', ec='#bbb', alpha=0.92))

    # ── Panel 3: Tabla de sospechosos ─────────────────────────────────────
    bad = df[df['status'].isin(['tierra','mar_abierto','fuera_de_grilla'])].copy()
    ax_tab.set_title(f'Fuentes a revisar ({len(bad)} / {len(df)})',
                     fontsize=10, fontweight='bold', pad=10)

    if len(bad) == 0:
        ax_tab.text(0.5, 0.5, '✓ Todas las fuentes son válidas',
                    ha='center', va='center', fontsize=12, color='#0077b6',
                    transform=ax_tab.transAxes)
    else:
        cols = ['idx','isrc','jsrc','dsrc','qbar','lon','lat','status']
        if 'face_mask' in bad.columns:
            cols += ['face_mask','rho_receptor']
        tab_data = bad[cols].values.tolist()
        col_labels = [c.replace('_','\n') for c in cols]

        tbl = ax_tab.table(
            cellText=[[str(v) if not isinstance(v, float) 
                        else f'{v:.3f}' for v in row] for row in tab_data],
            colLabels=col_labels,
            cellLoc='center', loc='upper center',
            bbox=[0, 0.02, 1, 0.95]
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(7.5)

        # Colorear filas según estado
        for (r_idx, c_idx), cell in tbl.get_celld().items():
            if r_idx == 0:
                cell.set_facecolor('#264653')
                cell.set_text_props(color='white', fontweight='bold')
            else:
                row_status = bad.iloc[r_idx-1]['status']
                cell.set_facecolor(STATUS_COLOR.get(row_status, '#fff') + '33')
                cell.set_edgecolor('#ccc')

    # ── Título general ────────────────────────────────────────────────────
    n_ok  = (df.status=='valido').sum() if 'valido' in df.status.values else (df.status=='oceano').sum()
    n_bad = len(df) - n_ok
    fig.suptitle(
        f'Diagnóstico psource CROCO  —  {len(df)} fuentes  |  '
        f'✓ OK: {n_ok}  |  ⚠/✗ Revisar: {n_bad}\n'
        f'Fuentes cruzan u-face (dsrc=0) o v-face (dsrc=1) en el límite tierra-mar',
        fontsize=11, fontweight='bold', y=0.98
    )

    plt.savefig(output_png, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  → {output_png}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--croco_in',  default='croco.in')
    parser.add_argument('--grd',       default=None)
    parser.add_argument('--geojson',   default='/tmp/countries.geojson')
    parser.add_argument('--output',    default='psource_mask_check.png')
    parser.add_argument('--csv',       default='psource_mask_check.csv')
    args = parser.parse_args()

    print(f"\n[1/4] Leyendo '{args.croco_in}' ...")
    df = parse_psource(args.croco_in)
    print(f"  → {len(df)} fuentes  (Xi/dsrc=0: {(df.dsrc==0).sum()}, "
          f"Eta/dsrc=1: {(df.dsrc==1).sum()})")

    grd_path = args.grd or parse_grid_path(args.croco_in)
    grid = load_grid(grd_path) if grd_path else None

    print(f"\n[2/4] Clasificando puntos ...")
    if grid is not None:
        df = diagnose_with_masks(df, grid)
        print("  Usando mask_u / mask_v del grid NetCDF")
    else:
        # Fallback: NaturalEarth
        print("  Sin grid → usando NaturalEarth como proxy")
        world = gpd.read_file(args.geojson)
        land  = world.union_all()
        coast = land.boundary
        df['on_land'] = df.apply(
            lambda r: land.contains(Point(r.lon, r.lat)), axis=1)
        df['dist_coast_km'] = df.apply(
            lambda r: coast.distance(Point(r.lon, r.lat))*111.0, axis=1)
        df['status'] = np.where(
            ~df['on_land'], 'oceano',
            np.where(df['dist_coast_km'] <= 1.5, 'costera', 'tierra'))
        df['face_mask']     = np.nan
        df['rho_receptor']  = np.nan

    print(f"\n  Resumen por estado:")
    for s, g in df.groupby('status'):
        print(f"    {s:20s}: {len(g):3d}")

    # Mostrar problemáticos
    bad = df[df['status'].isin(['tierra','mar_abierto','fuera_de_grilla'])]
    if len(bad):
        print(f"\n  ⚠  {len(bad)} fuentes problemáticas:")
        cols = ['idx','isrc','jsrc','dsrc','qbar','lon','lat','status']
        if 'face_mask' in df.columns:
            cols += ['face_mask','rho_receptor']
        print(bad[cols].to_string(index=False))

    df.to_csv(args.csv, index=False, float_format='%.4f')
    print(f"\n  → CSV: {args.csv}")

    print(f"\n[3/4] Cargando coastline NaturalEarth ...")
    world_gdf = gpd.read_file(args.geojson)

    print(f"\n[4/4] Generando figura ...")
    make_full_figure(df, world_gdf, grid, args.output)

    print("\n¡Listo!")

if __name__ == '__main__':
    main()
