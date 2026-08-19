"""
psource_grd.py  (v2 – corregido)
=================================
Diagnóstico de fuentes de ríos CROCO usando croco_grd.nc.

CORRECCIÓN PRINCIPAL:
  netCDF4 puede almacenar mask_u/mask_v con fill_value donde mask=0 (tierra).
  Al leer el array como MaskedArray, esas celdas aparecen como 'masked' en
  lugar de literalmente 0. Usamos np.ma.filled(arr, 0) para que la tierra
  quede como 0 y no como NaN.

FÍSICA DEL PSOURCE (staggered grid CROCO/ROMS):
  dsrc=0 → u-face entre rho(I,J) y rho(I+1,J)   [Python: mask_u[J-1, I-1]]
  dsrc=1 → v-face entre rho(I,J) y rho(I,J+1)   [Python: mask_v[J-1, I-1]]

  face_mask = 0 → borde tierra-mar          ✓ posición válida
  face_mask = 1 → ambas celdas son océano   ✗ fuente en mar abierto
  rho_recv  = 0 → celda receptora es tierra ✗ error de índice

Uso:
    python psource_grd.py --croco_in croco.in --grd CROCO_FILES/croco_grd.nc

Dependencias:
    pip install netCDF4 numpy pandas matplotlib plotly
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
from matplotlib.colors import ListedColormap
import plotly.graph_objects as go
from netCDF4 import Dataset


# ─────────────────────────────────────────────────────────────────────────────
# 1. Lectura croco.in
# ─────────────────────────────────────────────────────────────────────────────

def parse_psource(path):
    with open(path) as f:
        lines = f.readlines()
    start = next(
        i for i, l in enumerate(lines)
        if re.match(r'^psource\s*:', l.strip()) and 'ncfile' not in l
    )
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
            isrc   = int(p[0]),
            jsrc   = int(p[1]),
            dsrc   = int(p[2]),
            qbar   = float(p[3]),
            lon    = float(p[6]),   # T_src / lon de referencia
            lat    = float(p[7]),   # S_src / lat de referencia
            py_col = int(p[0]) - 1,
            py_row = int(p[1]) - 1,
        ))
        if len(records) >= nsrc:
            break
    return pd.DataFrame(records)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lectura croco_grd.nc  (con corrección de fill_value)
# ─────────────────────────────────────────────────────────────────────────────

def _read_filled(ds, varname, fill=0):
    """
    Lee una variable NetCDF y reemplaza valores masked con `fill`.
    CRÍTICO: mask_u/mask_v usan fill_value en celdas de tierra (mask=0),
    por eso hay que llenar con 0 y NO con NaN.
    """
    v = ds[varname][:]
    return np.ma.filled(v, fill).astype(float)


def load_grid(grd_path):
    if not os.path.exists(grd_path):
        raise FileNotFoundError(f"Grid no encontrado: {grd_path}")
    ds = Dataset(grd_path)

    g = dict(
        lon_rho  = _read_filled(ds, 'lon_rho',  fill=np.nan),
        lat_rho  = _read_filled(ds, 'lat_rho',  fill=np.nan),
        mask_rho = _read_filled(ds, 'mask_rho', fill=0),   # 0=tierra, 1=agua
        mask_u   = _read_filled(ds, 'mask_u',   fill=0),   # 0=tierra/borde, 1=agua
        mask_v   = _read_filled(ds, 'mask_v',   fill=0),
        lon_u    = _read_filled(ds, 'lon_u',    fill=np.nan),
        lat_u    = _read_filled(ds, 'lat_u',    fill=np.nan),
        lon_v    = _read_filled(ds, 'lon_v',    fill=np.nan),
        lat_v    = _read_filled(ds, 'lat_v',    fill=np.nan),
        h        = _read_filled(ds, 'h',        fill=np.nan),
    )
    ds.close()

    neta, nxi = g['mask_rho'].shape
    print(f"  mask_rho : {g['mask_rho'].shape}  "
          f"(tierra: {int((g['mask_rho']==0).sum())}, "
          f"agua: {int((g['mask_rho']==1).sum())})")
    print(f"  mask_u   : {g['mask_u'].shape}   "
          f"mask_v: {g['mask_v'].shape}")
    return g


# ─────────────────────────────────────────────────────────────────────────────
# 3. Diagnóstico con mask_u / mask_v
# ─────────────────────────────────────────────────────────────────────────────

def _get(arr, r, c):
    """Acceso seguro con chequeo de bounds.
    Cast explícito a int: iterrows() puede devolver numpy.float64
    cuando el DataFrame mezcla tipos; NumPy rechaza floats como índices.
    """
    r, c = int(r), int(c)
    if r < 0 or c < 0 or r >= arr.shape[0] or c >= arr.shape[1]:
        return np.nan
    return float(arr[r, c])


def diagnose(df, g):
    """
    Para cada fuente evalúa la máscara de la cara y la celda receptora.

    CROCO staggered grid (Fortran base-1):
      dsrc=0: u-face(I,J) entre rho(I,J) y rho(I+1,J)
        → mask_u [J-1, I-1]   = producto de mask_rho adyacentes
        → recv (Qbar>0): mask_rho[J-1, I]     (rho I+1, J)
        → recv (Qbar<0): mask_rho[J-1, I-1]   (rho I,   J)
        → lon/lat de la cara: lon_u[J-1, I-1]

      dsrc=1: v-face(I,J) entre rho(I,J) y rho(I,J+1)
        → mask_v [J-1, I-1]
        → recv (Qbar>0): mask_rho[J,   I-1]   (rho I, J+1)
        → recv (Qbar<0): mask_rho[J-1, I-1]   (rho I, J  )
        → lon/lat de la cara: lon_v[J-1, I-1]
    """
    mask_rho = g['mask_rho']
    mask_u   = g['mask_u']
    mask_v   = g['mask_v']

    rows = []
    for _, r in df.iterrows():
        pi, pj = r.py_col, r.py_row   # Python indices (base-0)

        if r.dsrc == 0:
            face = _get(mask_u, pj, pi)
            recv = _get(mask_rho, pj, pi + 1) if r.qbar >= 0 \
                   else _get(mask_rho, pj, pi)
            send = _get(mask_rho, pj, pi)     if r.qbar >= 0 \
                   else _get(mask_rho, pj, pi + 1)
            lon_f = _get(g['lon_u'], pj, pi)
            lat_f = _get(g['lat_u'], pj, pi)

        elif r.dsrc == 1:
            face = _get(mask_v, pj, pi)
            recv = _get(mask_rho, pj + 1, pi) if r.qbar >= 0 \
                   else _get(mask_rho, pj, pi)
            send = _get(mask_rho, pj, pi)     if r.qbar >= 0 \
                   else _get(mask_rho, pj + 1, pi)
            lon_f = _get(g['lon_v'], pj, pi)
            lat_f = _get(g['lat_v'], pj, pi)
        else:
            face = recv = send = lon_f = lat_f = np.nan

        # Clasificación
        if np.isnan(face):
            status = 'fuera_de_grilla'
        elif recv == 1 and face == 0:
            status = 'valido'       # ✓ borde tierra→mar correcto
        elif face == 1:
            status = 'mar_abierto'  # ✗ ambas celdas son agua
        elif recv == 0:
            status = 'tierra'       # ✗ celda receptora es tierra
        else:
            status = 'indefinido'

        rows.append(dict(
            face_mask = face,
            rho_recv  = recv,
            rho_send  = send,
            lon_face  = lon_f,
            lat_face  = lat_f,
            status    = status,
        ))

    return pd.concat([df.reset_index(drop=True), pd.DataFrame(rows)], axis=1)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Figura estática (PNG)
# ─────────────────────────────────────────────────────────────────────────────

STATUS_COLOR  = {
    'valido'         : '#0077b6',
    'mar_abierto'    : '#f4a261',
    'tierra'         : '#d62828',
    'fuera_de_grilla': '#adb5bd',
    'indefinido'     : '#6c757d',
}
STATUS_MARKER = {
    'valido': 'o', 'mar_abierto': 's',
    'tierra': '^', 'fuera_de_grilla': 'x', 'indefinido': 'D',
}
STATUS_LABEL = {
    'valido'         : '✓ Válido (borde tierra→mar)',
    'mar_abierto'    : '⚠ Mar abierto (face_mask=1)',
    'tierra'         : '✗ Tierra (recv=0)',
    'fuera_de_grilla': '? Fuera de grilla',
    'indefinido'     : '? Indefinido',
}
DIR_LABEL = {0: 'Xi (dsrc=0)', 1: 'Eta (dsrc=1)', -1: 'Neg'}


def make_png(df, g, output_png):
    mask_rho = g['mask_rho']
    lon_rho  = g['lon_rho']
    lat_rho  = g['lat_rho']
    neta, nxi = mask_rho.shape

    fig = plt.figure(figsize=(22, 10), facecolor='#f0f4f8')
    gs  = gridspec.GridSpec(1, 3, figure=fig, wspace=0.28,
                            left=0.03, right=0.97, top=0.91, bottom=0.07)

    ax_geo = fig.add_subplot(gs[0])
    ax_ij  = fig.add_subplot(gs[1])
    ax_tab = fig.add_subplot(gs[2])
    ax_tab.axis('off')

    bad_s = ['tierra', 'mar_abierto', 'fuera_de_grilla']

    # ── Panel 1: Mapa geográfico ──────────────────────────────────────────
    step = max(1, min(nxi, neta) // 250)
    lon_s = lon_rho[::step, ::step]
    lat_s = lat_rho[::step, ::step]
    h_s   = np.where(mask_rho[::step, ::step] == 1,
                     g['h'][::step, ::step], np.nan)
    land_s = np.where(mask_rho[::step, ::step] == 0, 1.0, np.nan)

    ax_geo.set_facecolor('#caf0f8')
    pc = ax_geo.pcolormesh(lon_s, lat_s, h_s, cmap='Blues_r',
                           shading='auto',
                           vmin=0, vmax=np.nanpercentile(h_s, 98), zorder=1)
    plt.colorbar(pc, ax=ax_geo, label='Profundidad h (m)',
                 fraction=0.03, pad=0.02)
    ax_geo.pcolormesh(lon_s, lat_s, land_s,
                      cmap=ListedColormap(['#d4a373']),
                      shading='auto', zorder=1, alpha=0.8)
    # Línea de costa fina
    ax_geo.contour(lon_rho[::max(1,step//2), ::max(1,step//2)],
                   lat_rho[::max(1,step//2), ::max(1,step//2)],
                   mask_rho[::max(1,step//2), ::max(1,step//2)],
                   levels=[0.5], colors=['#264653'],
                   linewidths=0.7, zorder=3)

    for status, grp in df.groupby('status'):
        ax_geo.scatter(
            grp['lon_face'], grp['lat_face'],
            c=STATUS_COLOR.get(status, '#999'),
            marker=STATUS_MARKER.get(status, 'o'),
            s=90, zorder=6, edgecolors='white', linewidths=0.9,
            label=STATUS_LABEL.get(status, status))

    for _, r in df[df['status'].isin(bad_s)].iterrows():
        ax_geo.annotate(
            f"#{int(r.idx)} ({r.isrc},{r.jsrc})",
            xy=(r.lon_face, r.lat_face), xytext=(6, 4),
            textcoords='offset points', fontsize=6.5,
            color=STATUS_COLOR.get(r.status, '#d62828'),
            bbox=dict(boxstyle='round,pad=0.2', fc='white',
                      ec=STATUS_COLOR.get(r.status,'#d62828'), alpha=0.8),
            zorder=9)

    pad = 0.4
    ax_geo.set_xlim(df.lon.min()-pad, df.lon.max()+pad)
    ax_geo.set_ylim(df.lat.min()-pad, df.lat.max()+pad)
    ax_geo.set_aspect('equal')
    ax_geo.set_xlabel('Longitud (°E)', fontsize=9)
    ax_geo.set_ylabel('Latitud (°N)', fontsize=9)
    ax_geo.set_title('Mapa geográfico\n'
                     '(posición real de u/v-face en el grid)',
                     fontsize=10, fontweight='bold')
    ax_geo.grid(True, ls='--', lw=0.35, color='#aaa', zorder=0, alpha=0.6)
    ax_geo.legend(fontsize=7.5, title='Estado', title_fontsize=8.5,
                  loc='lower left', framealpha=0.9)

    # ── Panel 2: Espacio I-J ──────────────────────────────────────────────
    step2 = max(1, min(nxi, neta) // 350)
    jj2, ii2 = np.meshgrid(np.arange(0, neta, step2),
                            np.arange(0, nxi,  step2), indexing='ij')
    m2 = mask_rho[::step2, ::step2]

    ax_ij.scatter((ii2+1)[m2==1], (jj2+1)[m2==1],
                  c='#caf0f8', s=0.8, zorder=1, linewidths=0)
    ax_ij.scatter((ii2+1)[m2==0], (jj2+1)[m2==0],
                  c='#d4a373', s=0.8, zorder=1, linewidths=0)

    for status, grp in df.groupby('status'):
        ax_ij.scatter(grp['isrc'], grp['jsrc'],
                      c=STATUS_COLOR.get(status, '#999'),
                      marker=STATUS_MARKER.get(status, 'o'),
                      s=95, zorder=6, edgecolors='#222', linewidths=0.8,
                      label=STATUS_LABEL.get(status, status))

    for _, r in df.iterrows():
        ax_ij.annotate(f"#{int(r.idx)}",
                       xy=(r.isrc, r.jsrc), xytext=(2, 2),
                       textcoords='offset points', fontsize=5,
                       color=STATUS_COLOR.get(r.status, '#444'), zorder=7)
        sign = 1 if r.qbar >= 0 else -1
        dx = sign * 3.0 if r.dsrc == 0 else 0
        dy = sign * 3.0 if r.dsrc == 1 else 0
        if dx or dy:
            ax_ij.annotate('',
                xy=(r.isrc+dx, r.jsrc+dy), xytext=(r.isrc, r.jsrc),
                arrowprops=dict(arrowstyle='->', lw=0.9,
                                color=STATUS_COLOR.get(r.status,'#888')),
                zorder=5)

    ax_ij.set_xlim(df.isrc.min()-15, df.isrc.max()+15)
    ax_ij.set_ylim(df.jsrc.min()-15, df.jsrc.max()+15)
    ax_ij.set_xlabel('I (xi, Fortran base-1) → Python col = I−1', fontsize=8.5)
    ax_ij.set_ylabel('J (eta, Fortran base-1) → Python row = J−1', fontsize=8.5)
    ax_ij.set_title('Espacio de grilla (I, J Fortran)\nAzul=océano · Ocre=tierra',
                    fontsize=10, fontweight='bold')
    ax_ij.grid(True, ls='--', lw=0.3, color='#ccc', zorder=0)
    ax_ij.legend(fontsize=7.5, loc='best', title='Estado',
                 title_fontsize=8.5, framealpha=0.9)
    ax_ij.text(0.99, 0.01,
               "dsrc=0 → mask_u[J−1, I−1]\n"
               "dsrc=1 → mask_v[J−1, I−1]\n"
               "face=0 ✓  face=1 ✗ mar abierto\n"
               "rho_recv=1 ✓  rho_recv=0 ✗ tierra",
               transform=ax_ij.transAxes, fontsize=7.5,
               va='bottom', ha='right',
               bbox=dict(boxstyle='round', fc='#fffde7', ec='#bbb', alpha=0.92))

    # ── Panel 3: Tabla ────────────────────────────────────────────────────
    bad = df[df['status'].isin(bad_s)].copy()
    ax_tab.set_title(f'Fuentes a revisar: {len(bad)} / {len(df)}',
                     fontsize=10, fontweight='bold', pad=12)

    if len(bad) == 0:
        ax_tab.text(0.5, 0.55, '✓ Todas las fuentes\nson válidas',
                    ha='center', va='center', fontsize=14,
                    color='#0077b6', transform=ax_tab.transAxes)
    else:
        cols = ['idx','isrc','jsrc','dsrc','qbar','lon','lat',
                'face_mask','rho_recv','status']
        heads = ['#','I','J','dsrc','Qbar','Lon','Lat',
                 'face\nmask','rho\nrecv','Estado']
        cell_data = []
        for _, r in bad[cols].iterrows():
            cell_data.append([
                str(int(r.idx)), str(r.isrc), str(r.jsrc), str(r.dsrc),
                f"{r.qbar:+.0f}", f"{r.lon:.3f}", f"{r.lat:.3f}",
                f"{r.face_mask:.0f}" if not np.isnan(r.face_mask) else '?',
                f"{r.rho_recv:.0f}"  if not np.isnan(r.rho_recv)  else '?',
                r.status,
            ])
        tbl = ax_tab.table(cellText=cell_data, colLabels=heads,
                           cellLoc='center', loc='upper center',
                           bbox=[0, 0.08, 1, 0.88])
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        for (ri, ci), cell in tbl.get_celld().items():
            if ri == 0:
                cell.set_facecolor('#264653')
                cell.set_text_props(color='white', fontweight='bold')
            else:
                st = bad.iloc[ri-1]['status']
                cell.set_facecolor(STATUS_COLOR.get(st,'#fff') + '28')
                cell.set_edgecolor('#ddd')

    summary = []
    for st, grp in df.groupby('status'):
        summary.append(f"{STATUS_LABEL.get(st,st)}: {len(grp)}")
    ax_tab.text(0.5, 0.04, '\n'.join(summary), ha='center', va='bottom',
                fontsize=8, transform=ax_tab.transAxes,
                bbox=dict(boxstyle='round', fc='white', ec='#ccc', alpha=0.8))

    n_ok = (df.status == 'valido').sum()
    fig.suptitle(
        f'Diagnóstico psource CROCO  ·  {len(df)} fuentes  ·  '
        f'✓ Válidas: {n_ok}   ⚠/✗ Revisar: {len(df)-n_ok}',
        fontsize=12, fontweight='bold', y=0.98)

    plt.savefig(output_png, dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  PNG → {output_png}")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Figura HTML interactiva (Plotly + OSM)
# ─────────────────────────────────────────────────────────────────────────────

DIR_COLOR  = {0: '#00b4d8', 1: '#e63946', -1: '#06d6a0'}


def make_html(df, g, output_html):
    """
    Mapa interactivo Plotly con:
      · Fondo OpenStreetMap
      · Puntos en la posición real de la u/v-face (lon_face, lat_face)
      · Color por estado diagnóstico
      · Forma del marcador por dsrc (círculo=xi, diamante=eta)
      · Hover completo: índices Fortran/Python, mask values, dirección
      · Capa de etiquetas I,J activable desde la leyenda
    """
    fig = go.Figure()

    symbol_map = {0: 'circle', 1: 'diamond', -1: 'square'}

    for status, grp in df.groupby('status'):
        for dsrc_val, sub in grp.groupby('dsrc'):
            hover = []
            for _, r in sub.iterrows():
                recv_str = f"{r.rho_recv:.0f}" if not np.isnan(r.rho_recv) else '?'
                face_str = f"{r.face_mask:.0f}" if not np.isnan(r.face_mask) else '?'
                hover.append(
                    f"<b>Fuente #{int(r.idx)}</b><br>"
                    f"<b>Fortran:</b>  I={r.isrc} · J={r.jsrc}<br>"
                    f"<b>Python  :</b>  col={r.py_col} · row={r.py_row}<br>"
                    f"Dirección: {DIR_LABEL.get(r.dsrc,'?')}  (dsrc={r.dsrc})<br>"
                    f"Qbar: {r.qbar:+.0f} m³/s<br>"
                    f"face_mask={face_str}  rho_recv={recv_str}<br>"
                    f"<b>Estado: {STATUS_LABEL.get(status, status)}</b><br>"
                    f"lon_face={r.lon_face:.4f}°  lat_face={r.lat_face:.4f}°"
                )
            fig.add_trace(go.Scattermap(
                lat=sub['lat_face'],
                lon=sub['lon_face'],
                mode='markers',
                marker=dict(
                    size=12,
                    color=STATUS_COLOR.get(status, '#888'),
                    symbol=symbol_map.get(dsrc_val, 'circle'),
                    opacity=0.92,
                ),
                name=f"{STATUS_LABEL.get(status,status)} · {DIR_LABEL.get(dsrc_val,'')}",
                text=hover,
                hovertemplate='%{text}<extra></extra>',
            ))

    # Capa de etiquetas I,J (activable)
    fig.add_trace(go.Scattermap(
        lat=df['lat_face'],
        lon=df['lon_face'],
        mode='text',
        text=[f"({r.isrc},{r.jsrc})" for _, r in df.iterrows()],
        textfont=dict(size=8, color='black'),
        hoverinfo='skip',
        showlegend=True,
        visible='legendonly',
        name='Etiquetas I,J (Fortran)',
    ))

    # Vectores de dirección: líneas cortas desde la cara
    lon_lines, lat_lines = [], []
    delta = 0.015
    for _, r in df.iterrows():
        sign = 1 if r.qbar >= 0 else -1
        if r.dsrc == 0:
            dlon, dlat = sign * delta * 3, 0
        elif r.dsrc == 1:
            dlon, dlat = 0, sign * delta * 3
        else:
            continue
        if np.isnan(r.lon_face) or np.isnan(r.lat_face):
            continue
        lon_lines += [r.lon_face, r.lon_face + dlon, None]
        lat_lines += [r.lat_face, r.lat_face + dlat, None]

    fig.add_trace(go.Scattermap(
        lat=lat_lines, lon=lon_lines,
        mode='lines',
        line=dict(width=2, color='rgba(50,50,50,0.5)'),
        hoverinfo='skip',
        name='Dirección flujo',
        showlegend=True,
    ))

    center_lat = df['lat_face'].dropna().mean()
    center_lon = df['lon_face'].dropna().mean()

    fig.update_layout(
        title=dict(
            text=(f'<b>Salidas de Ríos CROCO — {len(df)} fuentes</b><br>'
                  '<sup>Posición real de u/v-face del grid  ·  '
                  'Fondo: OpenStreetMap  ·  '
                  'Hover para info completa  ·  '
                  'Leyenda para filtrar  ·  '
                  'Círculo=dsrc0(Xi)  Diamante=dsrc1(Eta)</sup>'),
            x=0.5, xanchor='center', font=dict(size=14)
        ),
        map=dict(
            style='open-street-map',
            center=dict(lat=center_lat, lon=center_lon),
            zoom=7.0,
        ),
        legend=dict(
            title='<b>Estado · Dirección</b>',
            bgcolor='rgba(255,255,255,0.88)',
            bordercolor='#aaa', borderwidth=1,
            font=dict(size=10),
        ),
        margin=dict(l=0, r=0, t=80, b=0),
        width=1100, height=750,
    )

    # Anotación resumen
    n_ok  = (df.status == 'valido').sum()
    n_bad = len(df) - n_ok
    fig.add_annotation(
        xref='paper', yref='paper', x=0.01, y=0.04,
        text=(f"<b>{len(df)} fuentes</b>  |  "
              f"✓ {n_ok} válidas  |  ⚠/✗ {n_bad} revisar<br>"
              f"Xi(dsrc=0): {(df.dsrc==0).sum()}  "
              f"Eta(dsrc=1): {(df.dsrc==1).sum()}<br>"
              f"<i>I,J Fortran base-1  →  Python: col=I−1, row=J−1</i>"),
        showarrow=False, font=dict(size=10),
        bgcolor='rgba(255,255,255,0.82)',
        bordercolor='#aaa', borderwidth=1, align='left'
    )

    fig.write_html(output_html, include_plotlyjs='cdn')
    print(f"  HTML → {output_html}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--croco_in', default='croco.in')
    parser.add_argument('--grd',      required=True)
    parser.add_argument('--png',      default='psource_grd.png')
    parser.add_argument('--html',     default='psource_grd.html')
    parser.add_argument('--csv',      default='psource_grd.csv')
    args = parser.parse_args()

    print(f"\n[1/4] Leyendo '{args.croco_in}' ...")
    df = parse_psource(args.croco_in)
    print(f"  {len(df)} fuentes  "
          f"(dsrc=0: {(df.dsrc==0).sum()}, dsrc=1: {(df.dsrc==1).sum()})")

    print(f"\n[2/4] Cargando '{args.grd}' ...")
    g = load_grid(args.grd)

    print(f"\n[3/4] Diagnóstico con mask_u / mask_v ...")
    df = diagnose(df, g)

    print("\n  Resumen:")
    for st, grp in df.groupby('status'):
        print(f"    {STATUS_LABEL.get(st, st):42s}: {len(grp)}")

    bad = df[df['status'].isin(['tierra','mar_abierto','fuera_de_grilla'])]
    if len(bad):
        print(f"\n  ⚠  {len(bad)} fuentes a corregir:")
        print(bad[['idx','isrc','jsrc','dsrc','qbar',
                    'face_mask','rho_recv','status']].to_string(index=False))

    df.to_csv(args.csv, index=False, float_format='%.5f')
    print(f"\n  CSV → {args.csv}")

    print(f"\n[4/4] Generando figuras ...")
    make_png(df,  g, args.png)
    make_html(df, g, args.html)

    print("\n¡Listo!")
    return df


if __name__ == '__main__':
    df = main()
