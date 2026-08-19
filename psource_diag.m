%% psource_diag.m
%  Diagnóstico de fuentes CROCO — dos paneles: scatter | pcolor+grilla
%  Ejecutar por sección (F9) o completo (F5)
% =========================================================================

%% 1. PARÁMETROS
croco_in = 'croco.in';
grd_file = 'croco_grd.nc';

%% 2. LEER GRID
lon_rho  = ncread(grd_file, 'lon_rho');
lat_rho  = ncread(grd_file, 'lat_rho');
mask_rho = double(ncread(grd_file, 'mask_rho'));
lon_u    = ncread(grd_file, 'lon_u');
lat_u    = ncread(grd_file, 'lat_u');
mask_u   = double(ncread(grd_file, 'mask_u'));
lon_v    = ncread(grd_file, 'lon_v');
lat_v    = ncread(grd_file, 'lat_v');
mask_v   = double(ncread(grd_file, 'mask_v'));

mask_rho(isnan(mask_rho)) = 0;
mask_u(isnan(mask_u))     = 0;
mask_v(isnan(mask_v))     = 0;

[nxi_rho, neta_rho] = size(mask_rho);
[nxi_u,   neta_u  ] = size(mask_u);
[nxi_v,   neta_v  ] = size(mask_v);

%% 3. LEER PSOURCE DE croco.in
fid = fopen(croco_in, 'r');
lines = {};
while ~feof(fid), lines{end+1} = fgetl(fid); end
fclose(fid);

% Bloque "psource:" (excluye psource_ncfile)
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
        nsrc = str2double(ln); data_start = i + 1; break
    end
end

ISRC = zeros(nsrc,1); JSRC = zeros(nsrc,1);
DSRC = zeros(nsrc,1); QBAR = zeros(nsrc,1);
LON  = zeros(nsrc,1); LAT  = zeros(nsrc,1);
count = 0;
for i = data_start:numel(lines)
    p = strsplit(strtrim(lines{i}));
    if numel(p) < 8 || isnan(str2double(p{1})), break; end
    count = count + 1;
    ISRC(count) = str2double(p{1});
    JSRC(count) = str2double(p{2});
    DSRC(count) = str2double(p{3});
    QBAR(count) = str2double(p{4});
    LON(count)  = str2double(p{7});
    LAT(count)  = str2double(p{8});
    if count >= nsrc, break; end
end
ISRC = ISRC(1:count); JSRC = JSRC(1:count);
DSRC = DSRC(1:count); QBAR = QBAR(1:count);
LON  = LON(1:count);  LAT  = LAT(1:count);
fprintf('Leídas %d fuentes (dsrc=0: %d | dsrc=1: %d)\n', ...
        count, sum(DSRC==0), sum(DSRC==1))

%% 4. DIAGNOSTICO: face_mask y recepción
LON_FACE  = NaN(count,1);
LAT_FACE  = NaN(count,1);
FACE_MASK = NaN(count,1);
RHO_RECV  = NaN(count,1);
STATUS    = repmat({'indefinido'}, count, 1);

for k = 1:count
    I = ISRC(k); J = JSRC(k); D = DSRC(k); Q = QBAR(k);
    if D == 0   % u-face
        if I>=1 && I<=nxi_u && J>=1 && J<=neta_u
            FACE_MASK(k) = mask_u(I,J);
            LON_FACE(k)  = lon_u(I,J);
            LAT_FACE(k)  = lat_u(I,J);
        end
        recv_i = I + (Q>=0); recv_j = J;
    else        % v-face
        if I>=1 && I<=nxi_v && J>=1 && J<=neta_v
            FACE_MASK(k) = mask_v(I,J);
            LON_FACE(k)  = lon_v(I,J);
            LAT_FACE(k)  = lat_v(I,J);
        end
        recv_i = I; recv_j = J + (Q>=0);
    end
    if recv_i>=1 && recv_i<=nxi_rho && recv_j>=1 && recv_j<=neta_rho
        RHO_RECV(k) = mask_rho(recv_i, recv_j);
    end

    fm = FACE_MASK(k); rr = RHO_RECV(k);
    if isnan(fm),            STATUS{k} = 'fuera_grilla';
    elseif rr==1 && fm==0,  STATUS{k} = 'valido';
    elseif fm==1,            STATUS{k} = 'mar_abierto';
    elseif rr==0,            STATUS{k} = 'tierra';
    end
end

% Resumen
for s = unique(STATUS)'
    fprintf('  %-16s : %d\n', s{1}, sum(strcmp(STATUS, s{1})));
end

%% 5. COLORES Y FLECHAS
C_VAL = [0.00 0.45 0.70];
C_MAR = [0.96 0.50 0.15];
C_TIE = [0.84 0.10 0.16];
C_OUT = [0.55 0.55 0.55];

idx_val = strcmp(STATUS,'valido');
idx_mar = strcmp(STATUS,'mar_abierto');
idx_tie = strcmp(STATUS,'tierra');
idx_out = strcmp(STATUS,'fuera_grilla');



pad  = 0.30;
lon_lim = [min(LON_FACE(~isnan(LON_FACE)))-pad, max(LON_FACE(~isnan(LON_FACE)))+pad];
lat_lim = [min(LAT_FACE(~isnan(LAT_FACE)))-pad, max(LAT_FACE(~isnan(LAT_FACE)))+pad];
dl_arr  = 0.022;

%% 6. FIGURA — dos paneles horizontales
figure('Color','w', 'Position',[50 60 1600 720])

% -------------------------------------------------------------------------
%  PANEL A — SCATTER sobre máscara rho interpolada
% -------------------------------------------------------------------------
ax1 = subplot(1,2,1);

% Fondo: máscara rho submuestreada con scatter
step = 2;
lon_s  = lon_rho(1:step:end, 1:step:end);
lat_s  = lat_rho(1:step:end, 1:step:end);
mask_s = mask_rho(1:step:end, 1:step:end);

scatter(lon_s(:), lat_s(:), 4, mask_s(:), 's', 'filled')
colormap(ax1, [0.82 0.65 0.43; 0.72 0.88 0.96])
hold on

% Puntos por estado
if any(idx_val)
    scatter(LON_FACE(idx_val), LAT_FACE(idx_val), 55, C_VAL, 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.6)
end
if any(idx_mar)
    scatter(LON_FACE(idx_mar), LAT_FACE(idx_mar), 65, C_MAR, 's', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.6)
end
if any(idx_tie)
    scatter(LON_FACE(idx_tie), LAT_FACE(idx_tie), 70, C_TIE, '^', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.7)
end
if any(idx_out)
    scatter(LON_FACE(idx_out), LAT_FACE(idx_out), 60, C_OUT, 'x', ...
            'LineWidth',1.5)
end

% Flechas de dirección
for k = 1:count
    if isnan(LON_FACE(k)), continue; end
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    if DSRC(k)==0, du=sgn*dl_arr; dv=0;
    else,          du=0;          dv=sgn*dl_arr;
    end
    quiver(LON_FACE(k), LAT_FACE(k), du, dv, 0, ...
           'Color', src_color(STATUS{k}, C_VAL, C_MAR, C_TIE, C_OUT), ...
           'LineWidth',0.9, 'MaxHeadSize',2.5, 'HandleVisibility','off')
end

xlim(lon_lim); ylim(lat_lim)
xlabel('Longitud (°E)'); ylabel('Latitud (°N)')
title('Scatter — mask\_\rho', 'FontWeight','bold')
set(ax1, 'Box','on', 'GridAlpha',0.3)
grid on

% -------------------------------------------------------------------------
%  PANEL B — PCOLOR con grilla visible
% -------------------------------------------------------------------------
ax2 = subplot(1,2,2);

% pcolor de mask_rho completo
pcolor(ax2, lon_rho', lat_rho', mask_rho')
shading flat
colormap(ax2, [0.82 0.65 0.43; 0.72 0.88 0.96])
hold on

% Grilla de celdas visible (líneas de la grilla rho)
step_g = 4;   % mostrar una línea cada N celdas (ajustar según densidad)
for i = 1:step_g:nxi_rho
    il = lon_rho(i,:)'; jl = lat_rho(i,:)';
    plot(il, jl, '-', 'Color',[0 0 0 0.12], 'LineWidth',0.3, 'HandleVisibility','off')
end
for j = 1:step_g:neta_rho
    il = lon_rho(:,j);  jl = lat_rho(:,j);
    plot(il, jl, '-', 'Color',[0 0 0 0.12], 'LineWidth',0.3, 'HandleVisibility','off')
end

% Puntos
if any(idx_val)
    scatter(LON_FACE(idx_val), LAT_FACE(idx_val), 55, C_VAL, 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.6)
end
if any(idx_mar)
    scatter(LON_FACE(idx_mar), LAT_FACE(idx_mar), 65, C_MAR, 's', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.6)
end
if any(idx_tie)
    scatter(LON_FACE(idx_tie), LAT_FACE(idx_tie), 70, C_TIE, '^', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.7)
end
if any(idx_out)
    scatter(LON_FACE(idx_out), LAT_FACE(idx_out), 60, C_OUT, 'x', ...
            'LineWidth',1.5)
end

% Flechas
for k = 1:count
    if isnan(LON_FACE(k)), continue; end
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    if DSRC(k)==0, du=sgn*dl_arr; dv=0;
    else,          du=0;          dv=sgn*dl_arr;
    end
    quiver(LON_FACE(k), LAT_FACE(k), du, dv, 0, ...
           'Color', src_color(STATUS{k}, C_VAL, C_MAR, C_TIE, C_OUT), ...
           'LineWidth',0.9, 'MaxHeadSize',2.5, 'HandleVisibility','off')
end

xlim(lon_lim); ylim(lat_lim)
xlabel('Longitud (°E)'); ylabel('Latitud (°N)')
title('pcolor + grilla — mask\_\rho', 'FontWeight','bold')
set(ax2, 'Box','on')

sgtitle('Diagnóstico psource CROCO', 'FontSize',13, 'FontWeight','bold')
