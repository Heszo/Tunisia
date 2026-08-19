"""
plot_psource.py
===============
Visualización interactiva de las fuentes de ríos (psource) de CROCO.

IMPORTANTE – Convención de índices Fortran vs Python
=====================================================
En CROCO/Fortran los arrays 2D son var(xi, eta) con índices base-1:
  Isrc  → dirección xi   (columnas en Python: col = Isrc - 1)
  Jsrc  → dirección eta  (filas    en Python: row = Jsrc - 1)
En Python/NetCDF el array se almacena como var[eta, xi] = var[row, col],
por eso la conversión es:
  python_col = Isrc - 1
  python_row = Jsrc - 1
Esta distinción es crítica al indexar el grid.nc directamente.

Uso:
    python plot_psource.py --croco_in croco.in
    python plot_psource.py --croco_in croco.in --grd CROCO_FILES/croco_grd.nc --show

Dependencias:
    pip install plotly netCDF4 numpy pandas
"""

import argparse
import re
import os
import sys
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# ─────────────────────────────────────────────────────────────────────────────
# 1. Parser croco.in
# ─────────────────────────────────────────────────────────────────────────────

def parse_psource(croco_in_path):
    """
    Lee el bloque 'psource:' de croco.in.
    Columnas del croco.in: Isrc Jsrc Dsrc Qbar Lsrc Tsrc Lon Lat
    Añade columnas de índice Python: py_col = Isrc-1, py_row = Jsrc-1
    """
    with open(croco_in_path, 'r') as f:
        lines = f.readlines()

    start = None
    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r'^psource\s*:', s) and 'ncfile' not in s:
            start = i
            break
    if start is None:
        raise ValueError("No se encontró 'psource:' en el archivo.")

    nsrc = None
    data_start = None
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s and re.match(r'^\d+$', s):
            nsrc = int(s)
            data_start = i + 1
            break

    records = []
    for i in range(data_start, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 8:
            break
        try:
            isrc = int(parts[0])   # Fortran xi-index (base-1)
            jsrc = int(parts[1])   # Fortran eta-index (base-1)
            dsrc = int(parts[2])
            qbar = float(parts[3])
            lsrc = parts[4].upper() == 'T'
            tsrc = parts[5].upper() == 'T'
            lon  = float(parts[6])
            lat  = float(parts[7])
            records.append(dict(
                isrc=isrc, jsrc=jsrc, dsrc=dsrc,
                qbar=qbar, lsrc=lsrc, tsrc=tsrc,
                lon=lon, lat=lat,
                # Conversión Fortran→Python (base-1 → base-0)
                py_col=isrc - 1,   # índice de columna en numpy [eta, xi]
                py_row=jsrc - 1,   # índice de fila   en numpy [eta, xi]
            ))
        except (ValueError, IndexError):
            break
        if len(records) >= nsrc:
            break

    df = pd.DataFrame(records)
    print(f"  → {len(df)} fuentes leídas (nsrc declarado={nsrc})")
    return df


def parse_grid_path(croco_in_path):
    with open(croco_in_path, 'r') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('grid:'):
            for j in range(i + 1, min(i + 5, len(lines))):
                c = lines[j].strip()
                if c and not c.startswith('#'):
                    return c
    return None


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lectura opcional del grid NetCDF
# ─────────────────────────────────────────────────────────────────────────────

def load_grid(grd_path):
    try:
        from netCDF4 import Dataset
        if not os.path.exists(grd_path):
            print(f"  ⚠  Grilla no encontrada: '{grd_path}'")
            return None
        ds = Dataset(grd_path)
        lon  = ds.variables['lon_rho'][:]   # shape (eta, xi)
        lat  = ds.variables['lat_rho'][:]
        h    = ds.variables['h'][:]
        mask = ds.variables.get('mask_rho', None)
        mask = mask[:] if mask is not None else np.ones_like(h)
        neta, nxi = lon.shape
        ds.close()
        print(f"  → Grilla cargada: nxi={nxi}, neta={neta}  (array Python [eta,xi])")
        return dict(lon=lon, lat=lat, h=h, mask=mask, nxi=nxi, neta=neta)
    except ImportError:
        print("  ⚠  netCDF4 no instalado — sin batimetría.")
        return None
    except Exception as e:
        print(f"  ⚠  Error leyendo grilla: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Helpers de estilo
# ─────────────────────────────────────────────────────────────────────────────

DIR_LABELS = {0: 'Xi (W–E)', 1: 'Eta (S–N)', -1: 'Negativa'}
DIR_COLORS = {0: '#0077b6', 1: '#e63946', -1: '#2dc653'}
DIR_SYMBOLS = {0: 'circle', 1: 'diamond', -1: 'square'}


def hover_text(row):
    return (
        f"<b>Fuente #{int(row.name)+1}</b><br>"
        f"<b>Fortran:</b>  I={row.isrc} · J={row.jsrc}<br>"
        f"<b>Python :</b>  col={row.py_col} · row={row.py_row}<br>"
        f"Dirección: {DIR_LABELS.get(row.dsrc,'?')} (dsrc={row.dsrc})<br>"
        f"Qbar: {row.qbar:+.0f} · Lsrc={row.lsrc} · Tsrc={row.tsrc}<br>"
        f"Lon: {row.lon:.4f}°  Lat: {row.lat:.4f}°"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Figura 1 – Mapa geográfico con OpenStreetMap
# ─────────────────────────────────────────────────────────────────────────────

def make_map_figure(df):
    """Mapa interactivo con fondo OpenStreetMap y línea de costa implícita."""
    fig = go.Figure()

    for dsrc_val, group in df.groupby('dsrc'):
        texts = [hover_text(row) for _, row in group.iterrows()]
        fig.add_trace(go.Scattermap(
            lat=group['lat'],
            lon=group['lon'],
            mode='markers',
            marker=dict(
                size=10,
                color=DIR_COLORS.get(dsrc_val, '#888'),
                opacity=0.95,
            ),
            name=DIR_LABELS.get(dsrc_val, str(dsrc_val)),
            text=texts,
            hovertemplate='%{text}<extra></extra>',
        ))

    # Etiquetas I,J en Fortran (visibles como capa aparte)
    fig.add_trace(go.Scattermap(
        lat=df['lat'],
        lon=df['lon'],
        mode='text',
        text=[f"({r.isrc},{r.jsrc})" for _, r in df.iterrows()],
        textfont=dict(size=8, color='#111'),
        hoverinfo='skip',
        showlegend=True,
        visible='legendonly',
        name='Etiquetas Fortran I,J',
    ))

    center_lat = df['lat'].mean()
    center_lon = df['lon'].mean()

    fig.update_layout(
        title=dict(
            text='<b>Fuentes de Ríos CROCO — Mapa Geográfico</b><br>'
                 '<sup>Fondo: OpenStreetMap · '
                 'Hover para info · Leyenda para filtrar</sup>',
            x=0.5, xanchor='center', font=dict(size=15)
        ),
        map=dict(
            style='open-street-map',
            center=dict(lat=center_lat, lon=center_lon),
            zoom=6.5,
        ),
        legend=dict(
            title='<b>Dirección dsrc</b>',
            bgcolor='rgba(255,255,255,0.88)',
            bordercolor='#aaa', borderwidth=1,
            font=dict(size=12),
        ),
        margin=dict(l=0, r=0, t=70, b=0),
        width=950, height=680,
    )

    # Anotación resumen
    fig.add_annotation(
        xref='paper', yref='paper', x=0.01, y=0.04,
        text=(f"<b>{len(df)} fuentes</b>  |  "
              f"Xi(0): {(df.dsrc==0).sum()}  "
              f"Eta(1): {(df.dsrc==1).sum()}  "
              f"Neg(-1): {(df.dsrc==-1).sum()}<br>"
              f"<i>Índices Fortran base-1 → Python base-0: col=I-1, row=J-1</i>"),
        showarrow=False, font=dict(size=10),
        bgcolor='rgba(255,255,255,0.80)', bordercolor='#999',
        borderwidth=1, align='left'
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 5. Figura 2 – Espacio de grilla (I,J Fortran / col,row Python)
# ─────────────────────────────────────────────────────────────────────────────

def make_grid_figure(df, grid=None):
    """
    Muestra los puntos psource en el espacio de índices de la grilla.
    Eje X = I_fortran = py_col+1  (dirección xi)
    Eje Y = J_fortran = py_row+1  (dirección eta)

    Si se tiene el grid.nc, dibuja primero todos los puntos rho de la grilla.
    """
    fig = go.Figure()

    # ── Puntos de la grilla completa (si disponible) ──────────────────────
    if grid is not None:
        neta, nxi = grid['neta'], grid['nxi']
        mask = grid['mask']

        # Generar índices de todos los puntos rho
        jj, ii = np.meshgrid(np.arange(neta), np.arange(nxi), indexing='ij')
        # Aplanar
        ii_flat   = ii.ravel()
        jj_flat   = jj.ravel()
        mask_flat = mask.ravel()
        lon_flat  = grid['lon'].ravel()
        lat_flat  = grid['lat'].ravel()
        h_flat    = grid['h'].ravel()

        # Submuestreo para rendimiento
        step = max(1, nxi * neta // 8000)
        sl = slice(None, None, step)

        # Puntos de mar (mask=1)
        sea = mask_flat[sl] > 0
        fig.add_trace(go.Scattergl(
            x=(ii_flat[sl][sea] + 1),   # back to Fortran I
            y=(jj_flat[sl][sea] + 1),   # back to Fortran J
            mode='markers',
            marker=dict(size=2, color='#90e0ef', opacity=0.5),
            name='Grid rho (mar)',
            hovertemplate='I=%{x} · J=%{y}<extra>Mar</extra>',
        ))
        # Puntos de tierra (mask=0)
        land = mask_flat[sl] == 0
        if land.any():
            fig.add_trace(go.Scattergl(
                x=(ii_flat[sl][land] + 1),
                y=(jj_flat[sl][land] + 1),
                mode='markers',
                marker=dict(size=2, color='#d4a373', opacity=0.4),
                name='Grid rho (tierra)',
                hovertemplate='I=%{x} · J=%{y}<extra>Tierra</extra>',
            ))
    else:
        # Sin grilla: solo un rectángulo de referencia con el bounding box
        i_min, i_max = df['isrc'].min(), df['isrc'].max()
        j_min, j_max = df['jsrc'].min(), df['jsrc'].max()
        fig.add_shape(type='rect',
            x0=i_min-5, x1=i_max+5, y0=j_min-5, y1=j_max+5,
            line=dict(color='#ccc', width=1, dash='dot'),
            fillcolor='rgba(200,220,240,0.15)'
        )

    # ── Fuentes psource ───────────────────────────────────────────────────
    for dsrc_val, group in df.groupby('dsrc'):
        texts = [
            f"<b>#{int(r.name)+1}</b>  Fortran I={r.isrc} J={r.jsrc}<br>"
            f"Python col={r.py_col} row={r.py_row}<br>"
            f"Dir: {DIR_LABELS.get(r.dsrc,'?')}<br>"
            f"Lon={r.lon:.3f}° Lat={r.lat:.3f}°"
            for _, r in group.iterrows()
        ]
        fig.add_trace(go.Scattergl(
            x=group['isrc'],   # eje X = I Fortran
            y=group['jsrc'],   # eje Y = J Fortran
            mode='markers+text',
            marker=dict(
                size=12,
                color=DIR_COLORS.get(dsrc_val, '#888'),
                symbol=DIR_SYMBOLS.get(dsrc_val, 'circle'),
                line=dict(width=1.5, color='white'),
                opacity=0.95,
            ),
            text=[f"{r.isrc},{r.jsrc}" for _, r in group.iterrows()],
            textposition='top center',
            textfont=dict(size=7, color='#222'),
            name=DIR_LABELS.get(dsrc_val, str(dsrc_val)),
            hovertext=texts,
            hovertemplate='%{hovertext}<extra></extra>',
        ))

    # Vectores de dirección (flechas pequeñas)
    for _, row in df.iterrows():
        dx, dy = (0.8, 0) if row.dsrc == 0 else (0, 0.8) if row.dsrc == 1 else (0, 0)
        if dx or dy:
            fig.add_annotation(
                x=row.isrc + dx, y=row.jsrc + dy,
                ax=row.isrc, ay=row.jsrc,
                xref='x', yref='y', axref='x', ayref='y',
                arrowhead=2, arrowsize=1.2, arrowwidth=1.5,
                arrowcolor=DIR_COLORS.get(row.dsrc, '#888'),
                showarrow=True, text='',
            )

    fig.update_layout(
        title=dict(
            text='<b>Fuentes de Ríos — Espacio de Grilla (I, J Fortran)</b><br>'
                 '<sup>Eje X = I (dirección xi) · Eje Y = J (dirección eta) · '
                 'Índices base-1 Fortran  →  Python: col=I−1, row=J−1</sup>',
            x=0.5, xanchor='center', font=dict(size=14)
        ),
        xaxis=dict(
            title='I  (Fortran xi-index, base-1)  =  Python col + 1',
            showgrid=True, gridcolor='#e0e0e0', zeroline=False,
        ),
        yaxis=dict(
            title='J  (Fortran eta-index, base-1)  =  Python row + 1',
            showgrid=True, gridcolor='#e0e0e0', zeroline=False,
            scaleanchor='x', scaleratio=1,
        ),
        legend=dict(
            title='<b>Capa</b>',
            bgcolor='rgba(255,255,255,0.88)',
            bordercolor='#aaa', borderwidth=1,
        ),
        hovermode='closest',
        plot_bgcolor='#f8f9fa',
        paper_bgcolor='white',
        width=950, height=700,
        margin=dict(l=70, r=30, t=90, b=60),
    )

    # Anotación de conversión de índices
    fig.add_annotation(
        xref='paper', yref='paper', x=1.0, y=0.0,
        text=(
            "<b>Conversión de índices</b><br>"
            "Fortran → Python (NumPy):<br>"
            "  array[J-1, I-1]<br>"
            "  col = I - 1<br>"
            "  row = J - 1<br>"
            "<i>NetCDF almacena como [eta, xi]</i>"
        ),
        showarrow=False, font=dict(size=10),
        bgcolor='rgba(255,255,230,0.90)',
        bordercolor='#999', borderwidth=1,
        align='left', xanchor='right', yanchor='bottom'
    )

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 6. Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Plot interactivo psource CROCO.')
    parser.add_argument('--croco_in', default='croco.in')
    parser.add_argument('--grd', default=None)
    parser.add_argument('--output_map',  default='psource_map.html')
    parser.add_argument('--output_grid', default='psource_grid.html')
    parser.add_argument('--show', action='store_true')
    args = parser.parse_args()

    print(f"\n[1/3] Leyendo '{args.croco_in}' ...")
    df = parse_psource(args.croco_in)

    print("\n── Resumen (primeras 10 filas) ───────────────────────────────")
    print(df[['isrc','jsrc','py_col','py_row','dsrc','lon','lat']].head(10).to_string())
    print(f"\nTotal: {len(df)} fuentes  |  "
          f"Xi: {(df.dsrc==0).sum()}  Eta: {(df.dsrc==1).sum()}  "
          f"Neg: {(df.dsrc==-1).sum()}")

    grd_path = args.grd or parse_grid_path(args.croco_in)
    grid = load_grid(grd_path) if grd_path else None

    print(f"\n[2/3] Generando mapa geográfico (OpenStreetMap) ...")
    fig_map = make_map_figure(df)
    fig_map.write_html(args.output_map, include_plotlyjs='cdn')
    print(f"  → {args.output_map}")

    print(f"\n[3/3] Generando figura de espacio de grilla ...")
    fig_grid = make_grid_figure(df, grid)
    fig_grid.write_html(args.output_grid, include_plotlyjs='cdn')
    print(f"  → {args.output_grid}")

    if args.show:
        fig_map.show()
        fig_grid.show()

    return df, fig_map, fig_grid


if __name__ == '__main__':
    df, fig_map, fig_grid = main()
