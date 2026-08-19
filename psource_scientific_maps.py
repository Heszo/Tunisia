#!/usr/bin/env python3
"""
psource_scientific_maps.py
==========================
Publication-quality maps of CROCO point sources (rivers) for the Tunisia domain.

Figures produced
----------------
1. psource_osm_map.{svg,pdf}
   Geographic map with OpenStreetMap background, colour-coded by discharge
   direction (dsrc). Domain extent derived from croco_grd.nc.

2. psource_bathymetry.{svg,pdf}
   CROCO grid bathymetry (h, in metres) with psource overlay colour-coded
   by discharge direction. Grid lines drawn above land.

Usage
-----
    python psource_scientific_maps.py
    python psource_scientific_maps.py --grd croco_grd.nc --csv psource_diagnostico.csv
    python psource_scientific_maps.py --no-osm          # skip tile download

Dependencies
------------
    numpy, pandas, matplotlib, cartopy, cmocean, netCDF4
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patheffects as pe
import matplotlib.lines as mlines
from matplotlib.colors import BoundaryNorm
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from cartopy.mpl.gridliner import LONGITUDE_FORMATTER, LATITUDE_FORMATTER
import cmocean
import netCDF4 as nc

warnings.filterwarnings("ignore", category=UserWarning)

# ──────────────────────────────────────────────────────────────────────────────
# Style constants
# ──────────────────────────────────────────────────────────────────────────────
PROJ = ccrs.PlateCarree()

# Discharge direction (dsrc)
DSRC_COLOR = {
    0:  "#023e8a",
    1:  "#9b2226",
    -1: "#2dc653",
}
DSRC_LABEL = {
    0:  r"$\xi$ (W$\rightarrow$E)",
    1:  r"$\eta$ (S$\rightarrow$N)",
    -1: "Negative",
}
DSRC_MARKER = {
    0:  "o",
    1:  "^",
    -1: "s",
}

# Matplotlib rcParams for publication
plt.rcParams.update({
    "font.family":        "DejaVu Serif",
    "font.size":          9,
    "axes.titlesize":     10,
    "axes.labelsize":     9,
    "legend.fontsize":    8,
    "xtick.labelsize":    8,
    "ytick.labelsize":    8,
    "figure.dpi":         150,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.pad_inches": 0.05,
    "axes.linewidth":     0.8,
    "xtick.direction":    "in",
    "ytick.direction":    "in",
    "xtick.major.width":  0.6,
    "ytick.major.width":  0.6,
})

STROKE = [pe.withStroke(linewidth=2.5, foreground="white")]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _load_grid_extent(grd_path, pad=0):
    """
    Return (lon_min, lon_max, lat_min, lat_max) from croco_grd.nc with padding,
    plus rounded tick arrays for gridlines.
    """
    ds  = nc.Dataset(grd_path)
    lon = np.array(ds.variables["lon_rho"][:])
    lat = np.array(ds.variables["lat_rho"][:])
    ds.close()

    lon_min = lon.min() - pad
    lon_max = lon.max() + pad
    lat_min = lat.min() - pad
    lat_max = lat.max() + pad

    # Round to nearest 0.5° for tick placement
    def _ticks(vmin, vmax, step=1):
        start = np.ceil(vmin / step) * step
        return list(np.arange(start, vmax + step * 0.01, step))

    xlocs = _ticks(lon_min, lon_max, 1)
    ylocs = _ticks(lat_min, lat_max, 1)

    return lon_min, lon_max, lat_min, lat_max, xlocs, ylocs


def _gridlines(ax, xlocs, ylocs, line_zorder=None):
    """
    Add degree-labelled grid lines to a cartopy axes.

    If *line_zorder* is given the cartopy internal lines are hidden (lw=0)
    and equivalent lines are drawn explicitly at *line_zorder* so they render
    above rasterized land patches.
    """
    lw      = 0.001 if line_zorder is not None else 0.5
    lstyle  = "solid" if line_zorder is not None else "--"
    gl = ax.gridlines(
        draw_labels=True,
        linewidth=lw,
        color="grey",
        alpha=0.0 if line_zorder is not None else 0.6,
        linestyle=lstyle,
        crs=PROJ,
    )
    gl.xlocator   = mticker.FixedLocator(xlocs)
    gl.ylocator   = mticker.FixedLocator(ylocs)
    gl.xformatter = LONGITUDE_FORMATTER
    gl.yformatter = LATITUDE_FORMATTER
    gl.top_labels   = False
    gl.right_labels = False
    gl.xlabel_style = {"size": 8}
    gl.ylabel_style = {"size": 8}

    if line_zorder is not None:
        # NOTE: dashed linestyles (any form) fail with cartopy transforms when
        # clipping produces zero-length segments.  Solid lines at low alpha
        # give the same visual reference without the error.
        ext = ax.get_extent(PROJ)
        x0, x1, y0, y1 = ext
        for xv in xlocs:
            if x0 <= xv <= x1:
                ax.plot([xv, xv], [y0, y1],
                        color="grey", lw=0.45, alpha=0.45,
                        linestyle="solid",
                        transform=PROJ, zorder=line_zorder)
        for yv in ylocs:
            if y0 <= yv <= y1:
                ax.plot([x0, x1], [yv, yv],
                        color="grey", lw=0.45, alpha=0.45,
                        linestyle="solid",
                        transform=PROJ, zorder=line_zorder)
    return gl


def _scalebar(ax, lon0, lat0, length_deg, label, transform=PROJ):
    """Draw a simple scale bar."""
    ax.plot([lon0, lon0 + length_deg], [lat0, lat0],
            color="black", lw=2, transform=transform, zorder=10)
    ax.plot([lon0, lon0 + length_deg / 2], [lat0, lat0],
            color="white", lw=2, transform=transform, zorder=10)
    ax.text(lon0 + length_deg / 2, lat0 - 0.05, label,
            ha="center", va="top", fontsize=7, transform=transform,
            path_effects=STROKE, zorder=10)


def _legend_dsrc(ax, df, loc="lower right"):
    """Add discharge-direction legend to *ax*."""
    dsrc_counts = df["dsrc"].value_counts().to_dict()
    handles = [
        mlines.Line2D(
            [], [],
            color=DSRC_COLOR[d],
            marker=DSRC_MARKER[d], linestyle="None",
            markersize=7, markeredgecolor="white", markeredgewidth=0.7,
            label=f"{DSRC_LABEL[d]}  (n={dsrc_counts.get(d, 0)})",
        )
        for d in sorted(df["dsrc"].unique())
    ]
    ax.legend(handles=handles,
              title="Discharge direction",
              loc=loc,
              fontsize=7.5, title_fontsize=8,
              framealpha=0.92, edgecolor="#999999",
              borderpad=0.6, labelspacing=0.35)


# ──────────────────────────────────────────────────────────────────────────────
# Figure 1 — OpenStreetMap background
# ──────────────────────────────────────────────────────────────────────────────

def make_osm_figure(df, grd_path, use_osm=True):
    """
    Map of psource points over OpenStreetMap tiles.
    Colour and marker shape: discharge direction (dsrc).
    Domain extent derived from croco_grd.nc.
    """
    lon_min, lon_max, lat_min, lat_max, xlocs, ylocs = _load_grid_extent(grd_path)
    extent = [lon_min, lon_max, lat_min, lat_max]

    fig = plt.figure(figsize=(7.0, 9.0))
    ax  = fig.add_subplot(1, 1, 1, projection=ccrs.Mercator())
    ax.set_extent(extent, crs=PROJ)

    # ── Background ────────────────────────────────────────────────────────────
    if use_osm:
        try:
            from cartopy.io.img_tiles import OSM
            osm_tiles = OSM()
            ax.add_image(osm_tiles, 9)
        except Exception as exc:
            print(f"  [WARNING] OSM tile download failed: {exc}")
            print("  Falling back to Natural Earth features.")
            use_osm = False

    if not use_osm:
        ax.add_feature(cfeature.LAND.with_scale("10m"),
                       facecolor="#f0ece0", edgecolor="none", zorder=1)
        ax.add_feature(cfeature.OCEAN.with_scale("10m"),
                       facecolor="#cce5f5", zorder=1)
        ax.add_feature(cfeature.COASTLINE.with_scale("10m"),
                       linewidth=0.6, edgecolor="#555555", zorder=3)
        ax.add_feature(cfeature.BORDERS.with_scale("10m"),
                       linewidth=0.5, linestyle=":", edgecolor="#888888", zorder=3)
        ax.add_feature(cfeature.RIVERS.with_scale("10m"),
                       linewidth=0.4, edgecolor="#6baed6", zorder=3)

    # ── Grid lines ────────────────────────────────────────────────────────────
    # Cartopy draws its own degree labels; no extra ax.text for axis names needed
    _gridlines(ax, xlocs=xlocs, ylocs=ylocs)

    # ── Scatter: colour and shape by dsrc ─────────────────────────────────────
    for dsrc_val in sorted(df["dsrc"].unique()):
        sub = df[df["dsrc"] == dsrc_val]
        ax.scatter(sub["lon"], sub["lat"],
                   c=DSRC_COLOR[dsrc_val],
                   marker=DSRC_MARKER[dsrc_val],
                   s=60, zorder=7,
                   edgecolors="white", linewidths=0.7,
                   transform=PROJ)

    # ── Legend ────────────────────────────────────────────────────────────────
    _legend_dsrc(ax, df, loc="lower right")

    # ── Scale bar ─────────────────────────────────────────────────────────────
    sb_lon = lon_min + 0.15
    sb_lat = lat_min + 0.5
    _scalebar(ax, sb_lon, sb_lat, 0.45, "~50 km")

    # ── North arrow ────────────────────────────────────────────────────────────
    #ax.annotate(
    #    "N", xy=(0.97, 0.10), xytext=(0.97, 0.05),
    #    xycoords="axes fraction", textcoords="axes fraction",
    #    fontsize=9, fontweight="bold", ha="center",
    #    arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2),
    #)

    # ── Title ─────────────────────────────────────────────────────────────────
    ax.set_title(
        "CROCO River Point Sources — Tunisia Domain\n",
        fontsize=10, fontweight="bold", pad=6,
    )

    # ── Attribution ───────────────────────────────────────────────────────────
    ax.text(0.01, 0.01,
            "© OpenStreetMap contributors (openstreetmap.org/copyright)",
            transform=ax.transAxes,
            fontsize=5.5, color="#555555", va="bottom",
            path_effects=STROKE)

    # ── Statistics box ────────────────────────────────────────────────────────
    ax.text(0.5, 0.985, f"n = {len(df)} sources",
            transform=ax.transAxes,
            fontsize=7, ha="center", va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#aaaaaa", alpha=0.88))

    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Figure 2 — CROCO Bathymetry + psource overlay
# ──────────────────────────────────────────────────────────────────────────────

def make_bathymetry_figure(df, grd_path):
    """
    CROCO model bathymetry (h, metres) with psource points overlaid.
    Domain extent from grid file. Grid degree-lines drawn above land.
    """
    # ── Load grid ─────────────────────────────────────────────────────────────
    ds   = nc.Dataset(grd_path)
    lon  = np.array(ds.variables["lon_rho"][:])
    lat  = np.array(ds.variables["lat_rho"][:])
    h    = np.array(ds.variables["h"][:])
    mask = np.array(ds.variables["mask_rho"][:])
    ds.close()

    lon_min, lon_max, lat_min, lat_max, xlocs, ylocs = _load_grid_extent(grd_path)

    h_masked = np.ma.masked_where(mask == 0, h)

    # ── Figure ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(8.0, 9.0))
    ax  = fig.add_subplot(1, 1, 1, projection=PROJ)
    ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=PROJ)

    # ── Bathymetry pcolormesh (zorder 2) ──────────────────────────────────────
    depth_levels = [0, 10, 25, 50, 100, 200, 300, 500, 750, 1000]
    cmap = cmocean.cm.deep
    norm = BoundaryNorm(depth_levels, ncolors=cmap.N, clip=True)

    pcm = ax.pcolormesh(lon, lat, h_masked,
                        cmap=cmap, norm=norm,
                        transform=PROJ, rasterized=True, zorder=2)

    # ── Land patch (zorder 3) ─────────────────────────────────────────────────
    land_masked = np.ma.masked_where(mask == 1, mask)
    ax.pcolormesh(lon, lat, land_masked,
                  cmap=matplotlib.colors.ListedColormap(["#d4c5a0"]),
                  transform=PROJ, rasterized=True, zorder=3)

    # ── Isobath contours (zorder 4) ───────────────────────────────────────────
    ax.contour(lon, lat, h,
               levels=[50, 100, 200, 500],
               colors="white", linewidths=0.35, alpha=0.55,
               transform=PROJ, zorder=4)
    cs = ax.contour(lon, lat, h,
                    levels=[200],
                    colors="#b0c4de", linewidths=0.7, alpha=0.8,
                    transform=PROJ, zorder=4)
    ax.clabel(cs, fmt="%d m", fontsize=6.5, inline=True, inline_spacing=4)

    # ── Coastline and borders (zorder 5) ──────────────────────────────────────
    ax.add_feature(cfeature.COASTLINE.with_scale("10m"),
                   linewidth=0.7, edgecolor="#333333", zorder=5)
    ax.add_feature(cfeature.BORDERS.with_scale("10m"),
                   linewidth=0.5, linestyle=":", edgecolor="#666666", zorder=5)

    # ── Degree grid lines ABOVE land (zorder 6) ───────────────────────────────
    # line_zorder draws explicit lines above the land patch; labels from cartopy
    _gridlines(ax, xlocs=xlocs, ylocs=ylocs, line_zorder=6)

    # ── psource scatter (zorder 8) ────────────────────────────────────────────
    for dsrc_val in sorted(df["dsrc"].unique()):
        sub = df[df["dsrc"] == dsrc_val]
        ax.scatter(sub["lon"], sub["lat"],
                   c=DSRC_COLOR[dsrc_val],
                   marker=DSRC_MARKER[dsrc_val],
                   s=65, zorder=8,
                   edgecolors="white", linewidths=0.8,
                   transform=PROJ,
                   label=DSRC_LABEL[dsrc_val])

    # ── Colourbar ─────────────────────────────────────────────────────────────
    cbar = fig.colorbar(pcm, ax=ax,
                        orientation="vertical",
                        fraction=0.025, pad=0.02,
                        extend="max")
    cbar.set_label("Depth  (m)", fontsize=9, labelpad=6)
    cbar.set_ticks(depth_levels)
    cbar.ax.tick_params(labelsize=7.5)

    # ── Scale bar ─────────────────────────────────────────────────────────────
    sb_lon = lon_min + 0.15
    sb_lat = lat_min + 0.5
    _scalebar(ax, sb_lon, sb_lat, 0.9, "~100 km")

    # ── North arrow ────────────────────────────────────────────────────────────
    #ax.annotate(
    #    "N", xy=(0.97, 0.10), xytext=(0.97, 0.05),
    #    xycoords="axes fraction", textcoords="axes fraction",
    #    fontsize=9, fontweight="bold", ha="center",
    #    arrowprops=dict(arrowstyle="-|>", color="black", lw=1.2),
    #)

    # ── Legend ────────────────────────────────────────────────────────────────
    _legend_dsrc(ax, df, loc="upper right")

    # ── Titles / axis labels ──────────────────────────────────────────────────
    ax.set_title(
        "CROCO River Point Sources — Tunisia Domain\n"
        "Model Bathymetry",
        fontsize=10, fontweight="bold", pad=6,
    )
    ax.set_xlabel("Longitude (°E)", fontsize=9, labelpad=4)
    ax.set_ylabel("Latitude (°N)",  fontsize=9, labelpad=4)

    # ── Statistics annotation ─────────────────────────────────────────────────
    h_sea = h_masked.compressed()
    stats_txt = (
        f"Grid: {lon.shape[1]} × {lon.shape[0]}     \n"
        f"n sources = {len(df)}"
    )
    ax.text(0.01, 0.985, stats_txt,
            transform=ax.transAxes,
            fontsize=7, ha="left", va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#aaaaaa", alpha=0.88))

    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Scientific maps of CROCO psource points — Tunisia domain."
    )
    parser.add_argument("--grd",    default="croco_grd.nc",
                        help="Path to CROCO grid NetCDF file.")
    parser.add_argument("--csv",    default="psource_diagnostico.csv",
                        help="Path to psource diagnostics CSV.")
    parser.add_argument("--no-osm", action="store_true",
                        help="Skip OSM tile download; use Natural Earth instead.")
    parser.add_argument("--outdir", default=".",
                        help="Output directory for figure files.")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    use_osm = not args.no_osm

    # ── Load CSV ──────────────────────────────────────────────────────────────
    print(f"Loading '{args.csv}' …")
    df = pd.read_csv(args.csv)
    print(f"  {len(df)} sources  |  dsrc: {df['dsrc'].value_counts().to_dict()}")

    # ── Figure 1: OSM map ──────────────────────────────────────────────────────
    print("\n[1/2] Generating OSM map …")
    try:
        fig1 = make_osm_figure(df, grd_path=args.grd, use_osm=use_osm)
        for ext in ("svg", "pdf"):
            out = os.path.join(args.outdir, f"psource_osm_map.{ext}")
            fig1.savefig(out, format=ext)
            print(f"  → {out}")
        plt.close(fig1)
    except Exception as exc:
        print(f"  [ERROR] OSM figure failed: {exc}")

    # ── Figure 2: Bathymetry ───────────────────────────────────────────────────
    print("\n[2/2] Generating bathymetry figure …")
    try:
        fig2 = make_bathymetry_figure(df, grd_path=args.grd)
        for ext in ("svg", "pdf"):
            out = os.path.join(args.outdir, f"psource_bathymetry.{ext}")
            fig2.savefig(out, format=ext)
            print(f"  → {out}")
        plt.close(fig2)
    except Exception as exc:
        print(f"  [ERROR] Bathymetry figure failed: {exc}")

    print("\nDone.")


if __name__ == "__main__":
    main()
