%% psource_grids.m
%  4 paneles: mask_rho | mask_psi | mask_u (dsrc=0) | mask_v (dsrc=1)
%  Cada panel: pcolor + grilla MATLAB + puntos + flechas
% =========================================================================

%% 1. PARÁMETROS
croco_in = 'croco.in';
grd_file = 'croco_grd.nc';

%% 2. LEER GRID
lon_rho  = ncread(grd_file, 'lon_rho');
lat_rho  = ncread(grd_file, 'lat_rho');
mask_rho = double(ncread(grd_file, 'mask_rho'));

lon_psi  = ncread(grd_file, 'lon_psi');
lat_psi  = ncread(grd_file, 'lat_psi');
mask_psi = double(ncread(grd_file, 'mask_psi'));

lon_u    = ncread(grd_file, 'lon_u');
lat_u    = ncread(grd_file, 'lat_u');
mask_u   = double(ncread(grd_file, 'mask_u'));

lon_v    = ncread(grd_file, 'lon_v');
lat_v    = ncread(grd_file, 'lat_v');
mask_v   = double(ncread(grd_file, 'mask_v'));

mask_rho(isnan(mask_rho)) = 0;
mask_psi(isnan(mask_psi)) = 0;
mask_u(isnan(mask_u))     = 0;
mask_v(isnan(mask_v))     = 0;

[nxi_rho, neta_rho] = size(mask_rho);
[nxi_u,   neta_u  ] = size(mask_u);
[nxi_v,   neta_v  ] = size(mask_v);

%% 3. LEER PSOURCE
fid = fopen(croco_in, 'r');
lines = {};
while ~feof(fid), lines{end+1} = fgetl(fid); end
fclose(fid);

start_idx = 0;
for i = 1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln, '^psource\s*:', 'once')) && isempty(strfind(ln, 'ncfile'))
        start_idx = i; break
    end
end

nsrc = 0; data_start = 0;
for i = start_idx+1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln, '^\d+$', 'once'))
        nsrc = str2double(ln); data_start = i+1; break
    end
end

ISRC = zeros(nsrc,1); JSRC = zeros(nsrc,1);
DSRC = zeros(nsrc,1); QBAR = zeros(nsrc,1);
count = 0;
for i = data_start:numel(lines)
    p = strsplit(strtrim(lines{i}));
    if numel(p) < 8 || isnan(str2double(p{1})), break; end
    count = count + 1;
    ISRC(count) = str2double(p{1});
    JSRC(count) = str2double(p{2});
    DSRC(count) = str2double(p{3});
    QBAR(count) = str2double(p{4});
    if count >= nsrc, break; end
end
ISRC = ISRC(1:count); JSRC = JSRC(1:count);
DSRC = DSRC(1:count); QBAR = QBAR(1:count);
fprintf('Leídas %d fuentes  (dsrc=0: %d | dsrc=1: %d)\n', ...
        count, sum(DSRC==0), sum(DSRC==1))

%% 4. DIAGNOSTICO — face_mask y estado para cada grilla
% Posiciones en cada grilla
LON_U = NaN(count,1); LAT_U = NaN(count,1); FM_U = NaN(count,1);
LON_V = NaN(count,1); LAT_V = NaN(count,1); FM_V = NaN(count,1);

for k = 1:count
    I = ISRC(k); J = JSRC(k);
    if DSRC(k) == 0 && I>=1 && I<=nxi_u && J>=1 && J<=neta_u
        LON_U(k) = lon_u(I,J); LAT_U(k) = lat_u(I,J); FM_U(k) = mask_u(I,J);
    end
    if DSRC(k) == 1
        [nxi_v2, neta_v2] = size(mask_v);
        if I>=1 && I<=nxi_v2 && J>=1 && J<=neta_v2
            LON_V(k) = lon_v(I,J); LAT_V(k) = lat_v(I,J); FM_V(k) = mask_v(I,J);
        end
    end
end

% Para rho y psi: usar lon/lat de u o v según dsrc, igual que arriba
LON_FACE = NaN(count,1); LAT_FACE = NaN(count,1); FACE_MASK = NaN(count,1);
RHO_RECV = NaN(count,1);
STATUS   = repmat({'indefinido'}, count, 1);

for k = 1:count
    I = ISRC(k); J = JSRC(k); D = DSRC(k); Q = QBAR(k);
    if D == 0 && I>=1 && I<=nxi_u && J>=1 && J<=neta_u
        LON_FACE(k)  = lon_u(I,J); LAT_FACE(k)  = lat_u(I,J);
        FACE_MASK(k) = mask_u(I,J);
        ri = I + (Q>=0); rj = J;
    elseif D == 1
        [nxi_v2, neta_v2] = size(mask_v);
        if I>=1 && I<=nxi_v2 && J>=1 && J<=neta_v2
            LON_FACE(k)  = lon_v(I,J); LAT_FACE(k)  = lat_v(I,J);
            FACE_MASK(k) = mask_v(I,J);
        end
        ri = I; rj = J + (Q>=0);
    else
        continue
    end
    if D==0
        ri = I + (Q>=0); rj = J;
    else
        ri = I; rj = J + (Q>=0);
    end
    if ri>=1 && ri<=nxi_rho && rj>=1 && rj<=neta_rho
        RHO_RECV(k) = mask_rho(ri, rj);
    end
    fm = FACE_MASK(k); rr = RHO_RECV(k);
    if isnan(fm),           STATUS{k} = 'fuera_grilla';
    elseif rr==1 && fm==0, STATUS{k} = 'valido';
    elseif fm==1,           STATUS{k} = 'mar_abierto';
    elseif rr==0,           STATUS{k} = 'tierra';
    end
end

% Resumen
for s = unique(STATUS)'
    fprintf('  %-16s : %d\n', s{1}, sum(strcmp(STATUS, s{1})));
end

%% 5. COLORES Y LÍMITES
C_VAL = [0.00 0.45 0.70];
C_MAR = [0.96 0.50 0.15];
C_TIE = [0.84 0.10 0.16];
C_OUT = [0.55 0.55 0.55];
CMAP  = [0.82 0.65 0.43; 0.72 0.88 0.96];   % tierra | mar

idx_val = strcmp(STATUS,'valido');
idx_mar = strcmp(STATUS,'mar_abierto');
idx_tie = strcmp(STATUS,'tierra');
idx_out = strcmp(STATUS,'fuera_grilla');

pad = 0.30;
lon_ok  = LON_FACE(~isnan(LON_FACE));
lat_ok  = LAT_FACE(~isnan(LAT_FACE));
lon_lim = [min(lon_ok)-pad, max(lon_ok)+pad];
lat_lim = [min(lat_ok)-pad, max(lat_ok)+pad];
dl      = 0.022;   % largo flechas [grados]; ajustar según dominio

%% 6. FUNCIÓN AUXILIAR: color por estado


%% 7. FUNCIÓN AUXILIAR: dibujar puntos + flechas en un axes

%% 8. FIGURA 4 PANELES
fig = figure('Color','w','Position',[30 30 1700 800]);
tl  = tiledlayout(1,4,'TileSpacing','compact','Padding','compact');

titles  = {'mask\_\rho',  'mask\_\psi',  'mask\_u  (dsrc=0)',  'mask\_v  (dsrc=1)'};
lon_g   = {lon_rho,  lon_psi,  lon_u,   lon_v };
lat_g   = {lat_rho,  lat_psi,  lat_u,   lat_v };
mask_g  = {mask_rho, mask_psi, mask_u,  mask_v};

for p = 1:4
    ax = nexttile;

    % pcolor
    pcolor(ax, lon_g{p}', lat_g{p}', mask_g{p}')
    shading flat
    colormap(ax, CMAP)
    %clim(ax, [-0.01 1.01])
    hold on

    % Puntos + flechas — todos los paneles muestran todas las fuentes
    % (la cara u-face y v-face son posiciones de LON_FACE/LAT_FACE)
    draw_sources(ax, LON_FACE, LAT_FACE, DSRC, QBAR, STATUS, ...
                 idx_val, idx_mar, idx_tie, idx_out, ...
                 C_VAL, C_MAR, C_TIE, C_OUT, dl, count)

    xlim(lon_lim); ylim(lat_lim)
    xlabel('Lon (°E)'); ylabel('Lat (°N)')
    title(titles{p}, 'FontWeight','bold','FontSize',10)

    % Grilla MATLAB visible
    set(ax, 'XGrid','on','YGrid','on', ...
            'GridColor',[0 0 0],'GridAlpha',0.25,'GridLineStyle','-', ...
            'LineWidth',0.6,'Box','on','Layer','top')
    grid(ax,'on')
end

sgtitle('Diagnóstico psource CROCO — ○ válido  □ mar abierto  △ tierra  × fuera de grilla', ...
        'FontSize',12,'FontWeight','bold')
