"""
psource_grd.py
==============
Diagnóstico de fuentes de ríos CROCO usando croco_grd.nc.

FÍSICA DEL PSOURCE (CROCO/ROMS staggered grid):
  dsrc=0  → flujo cruza u-face entre rho(I,J) y rho(I+1,J)
             Verificar: mask_u[J-1, I-1]
               = 0  borde tierra-mar  ✓ válido
               = 1  mar abierto       ✗ error

  dsrc=1  → flujo cruza v-face entre rho(I,J) y rho(I,J+1)
             Verificar: mask_v[J-1, I-1]
               = 0  borde tierra-mar  ✓ válido
               = 1  mar abierto       ✗ error

  Celda receptora según signo de Qbar:
    dsrc=0, Qbar>0 → rho(I+1, J) → mask_rho[J-1, I]     debe ser 1
    dsrc=0, Qbar<0 → rho(I,   J) → mask_rho[J-1, I-1]   debe ser 1
    dsrc=1, Qbar>0 → rho(I, J+1) → mask_rho[J,   I-1]   debe ser 1
    dsrc=1, Qbar<0 → rho(I, J  ) → mask_rho[J-1, I-1]   debe ser 1

Uso:
    python psource_grd.py --croco_in croco.in --grd CROCO_FILES/croco_grd.nc

Dependencias:
    pip install netCDF4 numpy pandas matplotlib
"""

import argparse
import re
import os
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
from matplotlib.colors import ListedColormap
from netCDF4 import Dataset


# ─────────────────────────────────────────────────────────────────────────────
# 1. Lectura croco.in
# ─────────────────────────────────────────────────────────────────────────────

def parse_psource(path):
    """Lee el bloque psource: de croco.in → DataFrame."""
    with open(path) as f:
        lines = f.readlines()

    # Encuentra "psource:" (no psource_ncfile)
    start = next(
        i for i, l in enumerate(lines)
        if re.match(r'^psource\s*:', l.strip()) and 'ncfile' not in l
    )
    # Línea con nsrc
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if re.match(r'^\d+$', s):
            nsrc, data_start = int(s), i + 1
            break

    records = []
    for line in lines[data_start:]:
        p = line.strip().split()
        if len(p) < 8:
            break
        records.append(dict(
            idx    = len(records) + 1,
            isrc   = int(p[0]),        # Fortran xi,  base-1
            jsrc   = int(p[1]),        # Fortran eta, base-1
            dsrc   = int(p[2]),        # 0=u-face / 1=v-face
            qbar   = float(p[3]),
            lon    = float(p[6]),
            lat    = float(p[7]),
        ))
        if len(records) >= nsrc:
            break

    df = pd.DataFrame(records)
    # Índices Python equivalentes
    df['py_col'] = df['isrc'] - 1
    df['py_row'] = df['jsrc'] - 1
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lectura croco_grd.nc
# ─────────────────────────────────────────────────────────────────────────────

def load_grid(grd_path):
    """Carga variables relevantes del grid NetCDF."""
    if not os.path.exists(grd_path):
        raise FileNotFoundError(f"Grid no encontrado: {grd_path}")

    ds = Dataset(grd_path)
    g = dict(
        lon_rho  = ds['lon_rho'][:],    # (eta_rho, xi_rho)
        lat_rho  = ds['lat_rho'][:],
        mask_rho = ds['mask_rho'][:],   # 0=tierra, 1=agua
        mask_u   = ds['mask_u'][:],     # (eta_u,   xi_u)
        mask_v   = ds['mask_v'][:],     # (eta_v,   xi_v)
        lon_u    = ds['lon_u'][:],      # (eta_u,   xi_u)
        lat_u    = ds['lat_u'][:],
        lon_v    = ds['lon_v'][:],      # (eta_v,   xi_v)
        lat_v    = ds['lat_v'][:],
        h        = ds['h'][:],          # batimetría
    )
    ds.close()

    neta, nxi = g['mask_rho'].shape
    print(f"  Grid: xi_rho={nxi}, eta_rho={neta}")
    print(f"  mask_u: {g['mask_u'].shape}   mask_v: {g['mask_v'].shape}")
    return g


# ─────────────────────────────────────────────────────────────────────────────
# 3. Diagnóstico con mask_u / mask_v
# ─────────────────────────────────────────────────────────────────────────────

def diagnose(df, g):
    """
    Para cada fuente determina:
      face_mask    : valor de mask_u o mask_v en la cara
      rho_recv     : mask_rho de la celda receptora
      rho_send     : mask_rho de la celda emisora
      status       : 'valido' | 'mar_abierto' | 'tierra' | 'limite'
      lon_face     : longitud de la cara (u o v point)
      lat_face     : latitud  de la cara
    """
    mask_rho = g['mask_rho']
    mask_u   = g['mask_u']
    mask_v   = g['mask_v']
    lon_u, lat_u = g['lon_u'], g['lat_u']
    lon_v, lat_v = g['lon_v'], g['lat_v']

    rows = []
    for _, r in df.iterrows():
        I  = r.isrc          # Fortran, base-1
        J  = r.jsrc
        pi = r.py_col        # = I-1
        pj = r.py_row        # = J-1

        if r.dsrc == 0:
            # ── u-face entre rho(I,J) y rho(I+1,J) ──────────────────────
            # Python: mask_u[pj, pi]
            face = _safe(mask_u, pj, pi)
            # Celda receptora y emisora
            if r.qbar >= 0:
                recv = _safe(mask_rho, pj, pi + 1)   # rho(I+1, J)
                send = _safe(mask_rho, pj, pi)        # rho(I,   J)
            else:
                recv = _safe(mask_rho, pj, pi)
                send = _safe(mask_rho, pj, pi + 1)
            lon_f = _safe(lon_u, pj, pi)
            lat_f = _safe(lat_u, pj, pi)

        elif r.dsrc == 1:
            # ── v-face entre rho(I,J) y rho(I,J+1) ──────────────────────
            # Python: mask_v[pj, pi]
            face = _safe(mask_v, pj, pi)
            if r.qbar >= 0:
                recv = _safe(mask_rho, pj + 1, pi)   # rho(I, J+1)
                send = _safe(mask_rho, pj,     pi)   # rho(I, J  )
            else:
                recv = _safe(mask_rho, pj,     pi)
                send = _safe(mask_rho, pj + 1, pi)
            lon_f = _safe(lon_v, pj, pi)
            lat_f = _safe(lat_v, pj, pi)

        else:
            face = recv = send = lon_f = lat_f = np.nan

        # Clasificación
        if np.isnan(face):
            status = 'fuera_de_grilla'
        elif recv == 1 and face == 0:
            status = 'valido'        # ✓ borde tierra→mar
        elif face == 1:
            status = 'mar_abierto'   # ✗ ambas celdas son agua
        elif recv == 0:
            status = 'tierra'        # ✗ celda receptora es tierra
        else:
            status = 'indefinido'

        rows.append(dict(face_mask=face, rho_recv=recv, rho_send=send,
                         lon_face=lon_f, lat_face=lat_f, status=status))

    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


def _safe(arr, r, c):
    """Indexa un array con chequeo de bounds."""
    try:
        if r < 0 or c < 0 or r >= arr.shape[0] or c >= arr.shape[1]:
            return np.nan
        v = arr[r, c]
        return float(np.ma.filled(v, np.nan))
    except Exception:
        return np.nan


# ─────────────────────────────────────────────────────────────────────────────
# 4. Figura
# ─────────────────────────────────────────────────────────────────────────────

STATUS_COLOR  = {'valido': '#0077b6', 'mar_abierto': '#f4a261',
                 'tierra': '#d62828', 'fuera_de_grilla': '#adb5bd',
                 'indefinido': '#6c757d'}
STATUS_MARKER = {'valido': 'o', 'mar_abierto': 's',
                 'tierra': '^', 'fuera_de_grilla': 'x', 'indefinido': 'D'}
STATUS_LABEL  = {
    'valido'         : '✓ Válido (borde tierra→mar)',
    'mar_abierto'    : '⚠ Mar abierto (face_mask=1)',
    'tierra'         : '✗ Tierra (celda recv=0)',
    'fuera_de_grilla': '? Fuera de grilla',
    'indefinido'     : '? Indefinido',
}


def make_figure(df, g, output_png):
    mask_rho = g['mask_rho']
    lon_rho  = g['lon_rho']
    lat_rho  = g['lat_rho']
    neta, nxi = mask_rho.shape

    fig = plt.figure(figsize=(22, 10), facecolor='#f0f4f8')
    gs  = gridspec.GridSpec(1, 3, figure=fig, wspace=0.30,
                            left=0.04, right=0.97, top=0.91, bottom=0.07)

    ax_geo  = fig.add_subplot(gs[0])   # Mapa geográfico
    ax_ij   = fig.add_subplot(gs[1])   # Espacio I-J
    ax_tab  = fig.add_subplot(gs[2])   # Tabla
    ax_tab.axis('off')

    bad_statuses = ['tierra', 'mar_abierto', 'fuera_de_grilla']

    # ─── Panel 1: Mapa geográfico ─────────────────────────────────────────
    # Fondo: pcolormesh con mask_rho (tierra / océano)
    step = max(1, min(nxi, neta) // 200)
    lon_s = lon_rho[::step, ::step]
    lat_s = lat_rho[::step, ::step]
    h_s   = np.where(mask_rho[::step, ::step] == 1,
                     g['h'][::step, ::step], np.nan)

    # Batimetría en el mar
    pc = ax_geo.pcolormesh(lon_s, lat_s, h_s,
                           cmap='Blues_r', shading='auto',
                           vmin=0, vmax=np.nanpercentile(h_s, 98),
                           zorder=1)
    plt.colorbar(pc, ax=ax_geo, label='h (m)', fraction=0.03, pad=0.02)

    # Contorno de costa (mask_rho=0)
    ax_geo.contour(lon_rho, lat_rho, mask_rho,
                   levels=[0.5], colors=['#264653'],
                   linewidths=0.6, zorder=2)

    # Tierra
    land_color = np.where(mask_rho[::step, ::step] == 0, 1.0, np.nan)
    ax_geo.pcolormesh(lon_s, lat_s, land_color,
                      cmap=ListedColormap(['#d4a373']),
                      shading='auto', zorder=1, alpha=0.7)

    # Puntos psource en su posición geográfica de la cara (u/v point)
    for status, grp in df.groupby('status'):
        ax_geo.scatter(grp['lon_face'], grp['lat_face'],
                       c=STATUS_COLOR.get(status, '#999'),
                       marker=STATUS_MARKER.get(status, 'o'),
                       s=80, zorder=6, edgecolors='white', linewidths=0.8,
                       label=STATUS_LABEL.get(status, status))

    # Etiquetas de problemáticos
    for _, r in df[df['status'].isin(bad_statuses)].iterrows():
        ax_geo.annotate(
            f"#{int(r.idx)}\nI={r.isrc},J={r.jsrc}",
            xy=(r.lon_face, r.lat_face), xytext=(6, 4),
            textcoords='offset points', fontsize=6,
            color=STATUS_COLOR.get(r.status, '#d62828'),
            bbox=dict(boxstyle='round,pad=0.2', fc='white',
                      ec=STATUS_COLOR.get(r.status, '#d62828'), alpha=0.8),
            zorder=9)

    # Zoom a la región de fuentes
    pad = 0.5
    ax_geo.set_xlim(df.lon.min()-pad, df.lon.max()+pad)
    ax_geo.set_ylim(df.lat.min()-pad, df.lat.max()+pad)
    ax_geo.set_xlabel('Longitud (°E)', fontsize=9)
    ax_geo.set_ylabel('Latitud (°N)', fontsize=9)
    ax_geo.set_title('Posición geográfica de las caras\n'
                     '(lon/lat de u-point o v-point)',
                     fontsize=10, fontweight='bold')
    ax_geo.grid(True, ls='--', lw=0.35, color='#aaa', zorder=0, alpha=0.6)
    ax_geo.legend(fontsize=7.5, title='Estado', title_fontsize=8.5,
                  loc='lower left', framealpha=0.9)

    # ─── Panel 2: Espacio I-J ─────────────────────────────────────────────
    # Fondo: mask_rho en espacio de índices
    step2 = max(1, min(nxi, neta) // 300)
    jj, ii = np.meshgrid(np.arange(0, neta, step2),
                         np.arange(0, nxi,  step2), indexing='ij')
    m_s = mask_rho[::step2, ::step2]

    sea  = m_s == 1
    land = m_s == 0
    ax_ij.scatter((ii+1)[sea],  (jj+1)[sea],
                  c='#caf0f8', s=0.5, zorder=1, linewidths=0)
    ax_ij.scatter((ii+1)[land], (jj+1)[land],
                  c='#d4a373', s=0.5, zorder=1, linewidths=0)

    # Fuentes
    for status, grp in df.groupby('status'):
        ax_ij.scatter(grp['isrc'], grp['jsrc'],
                      c=STATUS_COLOR.get(status, '#999'),
                      marker=STATUS_MARKER.get(status, 'o'),
                      s=90, zorder=6, edgecolors='#222', linewidths=0.8,
                      label=STATUS_LABEL.get(status, status))

    # Etiquetas e índices
    for _, r in df.iterrows():
        ax_ij.annotate(f"#{int(r.idx)}",
                       xy=(r.isrc, r.jsrc), xytext=(2, 2),
                       textcoords='offset points', fontsize=5,
                       color=STATUS_COLOR.get(r.status, '#444'), zorder=7)

    # Flechas de dirección del flujo
    for _, r in df.iterrows():
        sign = 1 if r.qbar >= 0 else -1
        dx = sign * 2.5 if r.dsrc == 0 else 0
        dy = sign * 2.5 if r.dsrc == 1 else 0
        if dx or dy:
            ax_ij.annotate('',
                xy=(r.isrc + dx, r.jsrc + dy),
                xytext=(r.isrc, r.jsrc),
                arrowprops=dict(
                    arrowstyle='->', lw=0.9,
                    color=STATUS_COLOR.get(r.status, '#888')),
                zorder=5)

    ax_ij.set_xlim(df.isrc.min()-15, df.isrc.max()+15)
    ax_ij.set_ylim(df.jsrc.min()-15, df.jsrc.max()+15)
    ax_ij.set_xlabel('I  (Fortran xi, base-1)  —  Python col = I−1', fontsize=8.5)
    ax_ij.set_ylabel('J  (Fortran eta, base-1)  —  Python row = J−1', fontsize=8.5)
    ax_ij.set_title('Espacio de grilla (I, J Fortran)\n'
                    'Azul=océano · Ocre=tierra · Flecha=dirección flujo',
                    fontsize=10, fontweight='bold')
    ax_ij.grid(True, ls='--', lw=0.3, color='#ccc', zorder=0)
    ax_ij.legend(fontsize=7.5, title='Estado', title_fontsize=8.5,
                 loc='best', framealpha=0.9)

    # Caja de referencia
    ax_ij.text(0.99, 0.01,
               "dsrc=0 → mask_u[J−1, I−1]\n"
               "dsrc=1 → mask_v[J−1, I−1]\n"
               "face=0 ✓  face=1=mar abierto ✗\n"
               "recv=mask_rho celda receptora",
               transform=ax_ij.transAxes, fontsize=7.5,
               va='bottom', ha='right',
               bbox=dict(boxstyle='round', fc='#fffde7', ec='#bbb', alpha=0.92))

    # ─── Panel 3: Tabla ───────────────────────────────────────────────────
    bad = df[df['status'].isin(bad_statuses)].copy()
    ok  = df[~df['status'].isin(bad_statuses)]

    ax_tab.set_title(f'Fuentes a revisar: {len(bad)} / {len(df)}',
                     fontsize=10, fontweight='bold', pad=12)

    if len(bad) == 0:
        ax_tab.text(0.5, 0.55, '✓ Todas las fuentes\nson válidas',
                    ha='center', va='center', fontsize=14,
                    color='#0077b6', transform=ax_tab.transAxes)
    else:
        cols      = ['idx', 'isrc', 'jsrc', 'dsrc', 'qbar',
                     'lon', 'lat', 'face_mask', 'rho_recv', 'status']
        col_heads = ['#', 'I', 'J', 'dsrc', 'Qbar',
                     'Lon', 'Lat', 'face\nmask', 'rho\nrecv', 'Estado']

        cell_data = []
        for _, r in bad[cols].iterrows():
            cell_data.append([
                str(int(r['idx'])), str(r['isrc']), str(r['jsrc']),
                str(r['dsrc']),
                f"{r['qbar']:+.0f}",
                f"{r['lon']:.3f}", f"{r['lat']:.3f}",
                f"{r['face_mask']:.0f}" if not np.isnan(r['face_mask']) else '?',
                f"{r['rho_recv']:.0f}" if not np.isnan(r['rho_recv']) else '?',
                r['status'],
            ])

        tbl = ax_tab.table(
            cellText=cell_data, colLabels=col_heads,
            cellLoc='center', loc='upper center',
            bbox=[0.0, 0.08, 1.0, 0.88]
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)

        for (ri, ci), cell in tbl.get_celld().items():
            if ri == 0:
                cell.set_facecolor('#264653')
                cell.set_text_props(color='white', fontweight='bold')
            else:
                st = bad.iloc[ri-1]['status']
                cell.set_facecolor(STATUS_COLOR.get(st, '#fff') + '28')
                cell.set_edgecolor('#ddd')

    # Resumen numérico debajo de la tabla
    summary_lines = []
    for st, grp in df.groupby('status'):
        summary_lines.append(f"{STATUS_LABEL.get(st, st)}: {len(grp)}")
    ax_tab.text(0.5, 0.04, '\n'.join(summary_lines),
                ha='center', va='bottom', fontsize=8,
                transform=ax_tab.transAxes,
                bbox=dict(boxstyle='round', fc='white', ec='#ccc', alpha=0.8))

    # ─── Título global ────────────────────────────────────────────────────
    n_ok  = (df.status == 'valido').sum()
    n_bad = len(df) - n_ok
    fig.suptitle(
        f'Diagnóstico psource CROCO  ·  {len(df)} fuentes  ·  '
        f'✓ Válidas: {n_ok}   ⚠/✗ Revisar: {n_bad}\n'
        f'mask_u (dsrc=0) / mask_v (dsrc=1) desde {os.path.basename(grd_path)}',
        fontsize=12, fontweight='bold', y=0.98
    )

    plt.savefig(output_png, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  → {output_png}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Diagnóstico psource CROCO con croco_grd.nc')
    parser.add_argument('--croco_in', default='croco.in',
                        help='Archivo croco.in')
    parser.add_argument('--grd', required=True,
                        help='Archivo croco_grd.nc')
    parser.add_argument('--output', default='psource_grd.png',
                        help='Figura de salida (PNG)')
    parser.add_argument('--csv', default='psource_grd.csv',
                        help='CSV de salida')
    args = parser.parse_args()

    global grd_path
    grd_path = args.grd

    print(f"\n[1/3] Leyendo '{args.croco_in}' ...")
    df = parse_psource(args.croco_in)
    print(f"  {len(df)} fuentes  (dsrc=0: {(df.dsrc==0).sum()}, "
          f"dsrc=1: {(df.dsrc==1).sum()})")

    print(f"\n[2/3] Cargando grid '{args.grd}' ...")
    g = load_grid(args.grd)

    print(f"\n[3/3] Diagnóstico con mask_u / mask_v ...")
    df = diagnose(df, g)

    print(f"\n  Resumen:")
    for st, grp in df.groupby('status'):
        print(f"    {STATUS_LABEL.get(st, st):42s}: {len(grp)}")

    bad = df[df['status'].isin(['tierra', 'mar_abierto', 'fuera_de_grilla'])]
    if len(bad):
        print(f"\n  Fuentes a corregir:")
        print(bad[['idx','isrc','jsrc','dsrc','qbar','lon','lat',
                    'face_mask','rho_recv','status']].to_string(index=False))

    df.to_csv(args.csv, index=False, float_format='%.5f')
    print(f"\n  CSV: {args.csv}")

    make_figure(df, g, args.output)
    print("\n¡Listo!")


if __name__ == '__main__':
    main()
