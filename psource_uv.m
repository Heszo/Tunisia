%% ============================================================
%  psource_uv.m
%  Dos pcolor: mask_u (dsrc=0) y mask_v (dsrc=1)
%  Ejecutar sección por sección con F9
% =============================================================

%% 1. PARAMETROS
croco_in = 'croco.in';
grd_file = 'croco_grd.nc';

%% 2. LEER GRID
mask_u  = double(ncread(grd_file, 'mask_u'));    % (xi_u,  eta_u)
mask_v  = double(ncread(grd_file, 'mask_v'));    % (xi_v,  eta_v)
lon_u   = ncread(grd_file, 'lon_u');
lat_u   = ncread(grd_file, 'lat_u');
lon_v   = ncread(grd_file, 'lon_v');
lat_v   = ncread(grd_file, 'lat_v');

% fill_value → tierra=0
mask_u(isnan(mask_u)) = 0;
mask_v(isnan(mask_v)) = 0;

fprintf('mask_u: %d x %d\n', size(mask_u,1), size(mask_u,2))
fprintf('mask_v: %d x %d\n', size(mask_v,1), size(mask_v,2))

%% 3. LEER PSOURCE
fid   = fopen(croco_in,'r');
lines = {};
while ~feof(fid), lines{end+1} = fgetl(fid); end
fclose(fid);
%% ============================================================
%  psource_uv.m
%  Dos pcolor: mask_u (dsrc=0) y mask_v (dsrc=1)
%  Ejecutar sección por sección con F9
% =============================================================

%% 1. PARAMETROS
croco_in = 'croco.in';
grd_file = 'croco_grd.nc';

%% 2. LEER GRID
mask_u  = double(ncread(grd_file, 'mask_u'));    % (xi_u,  eta_u)
mask_v  = double(ncread(grd_file, 'mask_v'));    % (xi_v,  eta_v)
lon_u   = ncread(grd_file, 'lon_u');
lat_u   = ncread(grd_file, 'lat_u');
lon_v   = ncread(grd_file, 'lon_v');
lat_v   = ncread(grd_file, 'lat_v');

% fill_value → tierra=0
mask_u(isnan(mask_u)) = 0;
mask_v(isnan(mask_v)) = 0;

fprintf('mask_u: %d x %d\n', size(mask_u,1), size(mask_u,2))
fprintf('mask_v: %d x %d\n', size(mask_v,1), size(mask_v,2))

%% 3. LEER PSOURCE
fid   = fopen(croco_in,'r');
lines = {};
while ~feof(fid), lines{end+1} = fgetl(fid); end
fclose(fid);

% Encontrar bloque psource: (no ncfile)
start_idx = 0;
for i = 1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^psource\s*:','once')) && isempty(strfind(ln,'ncfile'))
        start_idx = i; break
    end
end

% Leer nsrc
nsrc = 0; data_start = 0;
for i = start_idx+1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^\d+$','once'))
        nsrc = str2double(ln); data_start = i+1; break
    end
end

% Leer datos
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
ISRC=ISRC(1:count); JSRC=JSRC(1:count);
DSRC=DSRC(1:count); QBAR=QBAR(1:count);
LON=LON(1:count);   LAT=LAT(1:count);
fprintf('%d fuentes  (dsrc=0: %d  dsrc=1: %d)\n', ...
        count, sum(DSRC==0), sum(DSRC==1))

%% 4. GRAFICO mask_u  — fuentes dsrc=0

idx0 = find(DSRC == 0);    % fuentes en u-face

figure('Color','w','Position',[50 100 800 680])

% pcolor: 0=tierra(ocre)  1=mar(azul)
pcolor(lon_u', lat_u', mask_u')
shading flat
colormap([0.82 0.65 0.43   % tierra
          0.65 0.85 0.94]) % mar
hold on

% Fuentes dsrc=0 en su posición geográfica (lon_u, lat_u del punto I,J)
[nxi_u, neta_u] = size(mask_u);
lon_src0 = NaN(numel(idx0),1);
lat_src0 = NaN(numel(idx0),1);
fm_src0  = NaN(numel(idx0),1);

for ki = 1:numel(idx0)
    k = idx0(ki);
    I = ISRC(k); J = JSRC(k);
    if I>=1 && I<=nxi_u && J>=1 && J<=neta_u
        lon_src0(ki) = lon_u(I,J);
        lat_src0(ki) = lat_u(I,J);
        fm_src0(ki)  = mask_u(I,J);
    end
end

% Separar válidos (face=0) y problemáticos (face=1 o NaN)
ok0  = fm_src0 == 0;
bad0 = fm_src0 == 1;
nan0 = isnan(fm_src0);

if any(ok0)
    scatter(lon_src0(ok0), lat_src0(ok0), 70, ...
            [0.00 0.45 0.70], 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Valido face=0 (%d)', sum(ok0)))
end
if any(bad0)
    scatter(lon_src0(bad0), lat_src0(bad0), 90, ...
            [0.85 0.10 0.15], '^', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Mar abierto face=1 (%d)', sum(bad0)))
end
if any(nan0)
    scatter(lon_src0(nan0), lat_src0(nan0), 90, ...
            [0.5 0.5 0.5], 'x', 'LineWidth', 1.5, ...
            'DisplayName', sprintf('Fuera de grilla (%d)', sum(nan0)))
end

% Flechas de dirección
for ki = 1:numel(idx0)
    if isnan(lon_src0(ki)), continue; end
    k   = idx0(ki);
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    dl  = 0.02;
    quiver(lon_src0(ki), lat_src0(ki), sgn*dl, 0, 0, ...
           'Color',[0.1 0.1 0.1], 'LineWidth',0.9, ...
           'MaxHeadSize',2, 'HandleVisibility','off')
end

% Etiquetas de índice
for ki = 1:numel(idx0)
    if isnan(lon_src0(ki)), continue; end
    k = idx0(ki);
    text(lon_src0(ki)+0.015, lat_src0(ki)+0.015, ...
         sprintf('(%d,%d)', ISRC(k), JSRC(k)), ...
         'FontSize', 6.5, 'Color', [0.1 0.1 0.1])
end

pad = 0.3;
xlim([min(lon_src0(~isnan(lon_src0)))-pad, max(lon_src0(~isnan(lon_src0)))+pad])
ylim([min(lat_src0(~isnan(lat_src0)))-pad, max(lat_src0(~isnan(lat_src0)))+pad])
xlabel('Longitud (°E)', 'FontSize', 11)
ylabel('Latitud (°N)',  'FontSize', 11)
title({'mask\_u  —  fuentes dsrc=0  (u-face, flujo en xi)', ...
       'Ocre=tierra  Azul=mar  Flecha=dirección flujo'}, ...
      'FontSize', 11, 'FontWeight', 'bold')
% legend('Location','SouthWest','FontSize',9)
colorbar('off')
grid on; box on

%% 5. GRAFICO mask_v  — fuentes dsrc=1

idx1 = find(DSRC == 1);    % fuentes en v-face

figure('Color','w','Position',[900 100 800 680])

pcolor(lon_v', lat_v', mask_v')
shading flat
colormap([0.82 0.65 0.43
          0.65 0.85 0.94])
hold on

[nxi_v, neta_v] = size(mask_v);
lon_src1 = NaN(numel(idx1),1);
lat_src1 = NaN(numel(idx1),1);
fm_src1  = NaN(numel(idx1),1);

for ki = 1:numel(idx1)
    k = idx1(ki);
    I = ISRC(k); J = JSRC(k);
    if I>=1 && I<=nxi_v && J>=1 && J<=neta_v
        lon_src1(ki) = lon_v(I,J);
        lat_src1(ki) = lat_v(I,J);
        fm_src1(ki)  = mask_v(I,J);
    end
end

ok1  = fm_src1 == 0;
bad1 = fm_src1 == 1;
nan1 = isnan(fm_src1);

if any(ok1)
    scatter(lon_src1(ok1), lat_src1(ok1), 70, ...
            [0.00 0.45 0.70], 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Valido face=0 (%d)', sum(ok1)))
end
if any(bad1)
    scatter(lon_src1(bad1), lat_src1(bad1), 90, ...
            [0.85 0.10 0.15], '^', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Mar abierto face=1 (%d)', sum(bad1)))
end
if any(nan1)
    scatter(lon_src1(nan1), lat_src1(nan1), 90, ...
            [0.5 0.5 0.5], 'x', 'LineWidth', 1.5, ...
            'DisplayName', sprintf('Fuera de grilla (%d)', sum(nan1)))
end

% Flechas verticales (flujo en eta)
for ki = 1:numel(idx1)
    if isnan(lon_src1(ki)), continue; end
    k   = idx1(ki);
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    dl  = 0.02;
    quiver(lon_src1(ki), lat_src1(ki), 0, sgn*dl, 0, ...
           'Color',[0.1 0.1 0.1], 'LineWidth',0.9, ...
           'MaxHeadSize',2, 'HandleVisibility','off')
end

for ki = 1:numel(idx1)
    if isnan(lon_src1(ki)), continue; end
    k = idx1(ki);
    text(lon_src1(ki)+0.015, lat_src1(ki)+0.015, ...
         sprintf('(%d,%d)', ISRC(k), JSRC(k)), ...
         'FontSize', 6.5, 'Color', [0.1 0.1 0.1])
end

pad = 0.3;
xlim([min(lon_src1(~isnan(lon_src1)))-pad, max(lon_src1(~isnan(lon_src1)))+pad])
ylim([min(lat_src1(~isnan(lat_src1)))-pad, max(lat_src1(~isnan(lat_src1)))+pad])
xlabel('Longitud (°E)', 'FontSize', 11)
ylabel('Latitud (°N)',  'FontSize', 11)
title({'mask\_v  —  fuentes dsrc=1  (v-face, flujo en eta)', ...
       'Ocre=tierra  Azul=mar  Flecha=dirección flujo'}, ...
      'FontSize', 11, 'FontWeight', 'bold')
% legend('Location','SouthWest','FontSize',9)
colorbar('off')
grid on; box on
% Encontrar bloque psource: (no ncfile)
start_idx = 0;
for i = 1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^psource\s*:','once')) && isempty(strfind(ln,'ncfile'))
        start_idx = i; break
    end
end

% Leer nsrc
nsrc = 0; data_start = 0;
for i = start_idx+1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^\d+$','once'))
        nsrc = str2double(ln); data_start = i+1; break
    end
end

% Leer datos
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
ISRC=ISRC(1:count); JSRC=JSRC(1:count);
DSRC=DSRC(1:count); QBAR=QBAR(1:count);
LON=LON(1:count);   LAT=LAT(1:count);
fprintf('%d fuentes  (dsrc=0: %d  dsrc=1: %d)\n', ...
        count, sum(DSRC==0), sum(DSRC==1))

%% 4. GRAFICO mask_u  — fuentes dsrc=0

idx0 = find(DSRC == 0);    % fuentes en u-face

figure('Color','w','Position',[50 100 800 680])

% pcolor: 0=tierra(ocre)  1=mar(azul)
pcolor(lon_u', lat_u', mask_u')
shading flat
colormap([0.82 0.65 0.43   % tierra
          0.65 0.85 0.94]) % mar
hold on

% Fuentes dsrc=0 en su posición geográfica (lon_u, lat_u del punto I,J)
[nxi_u, neta_u] = size(mask_u);
lon_src0 = NaN(numel(idx0),1);
lat_src0 = NaN(numel(idx0),1);
fm_src0  = NaN(numel(idx0),1);

for ki = 1:numel(idx0)
    k = idx0(ki);
    I = ISRC(k); J = JSRC(k);
    if I>=1 && I<=nxi_u && J>=1 && J<=neta_u
        lon_src0(ki) = lon_u(I,J);
        lat_src0(ki) = lat_u(I,J);
        fm_src0(ki)  = mask_u(I,J);
    end
end

% Separar válidos (face=0) y problemáticos (face=1 o NaN)
ok0  = fm_src0 == 0;
bad0 = fm_src0 == 1;
nan0 = isnan(fm_src0);

if any(ok0)
    scatter(lon_src0(ok0), lat_src0(ok0), 70, ...
            [0.00 0.45 0.70], 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Valido face=0 (%d)', sum(ok0)))
end
if any(bad0)
    scatter(lon_src0(bad0), lat_src0(bad0), 90, ...
            [0.85 0.10 0.15], '^', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Mar abierto face=1 (%d)', sum(bad0)))
end
if any(nan0)
    scatter(lon_src0(nan0), lat_src0(nan0), 90, ...
            [0.5 0.5 0.5], 'x', 'LineWidth', 1.5, ...
            'DisplayName', sprintf('Fuera de grilla (%d)', sum(nan0)))
end

% Flechas de dirección
for ki = 1:numel(idx0)
    if isnan(lon_src0(ki)), continue; end
    k   = idx0(ki);
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    dl  = 0.02;
    quiver(lon_src0(ki), lat_src0(ki), sgn*dl, 0, 0, ...
           'Color',[0.1 0.1 0.1], 'LineWidth',0.9, ...
           'MaxHeadSize',2, 'HandleVisibility','off')
end

% Etiquetas de índice
for ki = 1:numel(idx0)
    if isnan(lon_src0(ki)), continue; end
    k = idx0(ki);
    text(lon_src0(ki)+0.015, lat_src0(ki)+0.015, ...
         sprintf('(%d,%d)', ISRC(k), JSRC(k)), ...
         'FontSize', 6.5, 'Color', [0.1 0.1 0.1])
end

pad = 0.3;
xlim([min(lon_src0(~isnan(lon_src0)))-pad, max(lon_src0(~isnan(lon_src0)))+pad])
ylim([min(lat_src0(~isnan(lat_src0)))-pad, max(lat_src0(~isnan(lat_src0)))+pad])
xlabel('Longitud (°E)', 'FontSize', 11)
ylabel('Latitud (°N)',  'FontSize', 11)
title({'mask\_u  —  fuentes dsrc=0  (u-face, flujo en xi)', ...
       'Ocre=tierra  Azul=mar  Flecha=dirección flujo'}, ...
      'FontSize', 11, 'FontWeight', 'bold')
%legend('Location','SouthWest','FontSize',9)
colorbar('off')
grid on; box on

%% 5. GRAFICO mask_v  — fuentes dsrc=1

idx1 = find(DSRC == 1);    % fuentes en v-face

figure('Color','w','Position',[900 100 800 680])

pcolor(lon_v', lat_v', mask_v')
shading flat
colormap([0.82 0.65 0.43
          0.65 0.85 0.94])
hold on

[nxi_v, neta_v] = size(mask_v);
lon_src1 = NaN(numel(idx1),1);
lat_src1 = NaN(numel(idx1),1);
fm_src1  = NaN(numel(idx1),1);

for ki = 1:numel(idx1)
    k = idx1(ki);
    I = ISRC(k); J = JSRC(k);
    if I>=1 && I<=nxi_v && J>=1 && J<=neta_v
        lon_src1(ki) = lon_v(I,J);
        lat_src1(ki) = lat_v(I,J);
        fm_src1(ki)  = mask_v(I,J);
    end
end

ok1  = fm_src1 == 0;
bad1 = fm_src1 == 1;
nan1 = isnan(fm_src1);

if any(ok1)
    scatter(lon_src1(ok1), lat_src1(ok1), 70, ...
            [0.00 0.45 0.70], 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Valido face=0 (%d)', sum(ok1)))
end
if any(bad1)
    scatter(lon_src1(bad1), lat_src1(bad1), 90, ...
            [0.85 0.10 0.15], '^', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.8, ...
            'DisplayName', sprintf('Mar abierto face=1 (%d)', sum(bad1)))
end
if any(nan1)
    scatter(lon_src1(nan1), lat_src1(nan1), 90, ...
            [0.5 0.5 0.5], 'x', 'LineWidth', 1.5, ...
            'DisplayName', sprintf('Fuera de grilla (%d)', sum(nan1)))
end

% Flechas verticales (flujo en eta)
for ki = 1:numel(idx1)
    if isnan(lon_src1(ki)), continue; end
    k   = idx1(ki);
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    dl  = 0.02;
    quiver(lon_src1(ki), lat_src1(ki), 0, sgn*dl, 0, ...
           'Color',[0.1 0.1 0.1], 'LineWidth',0.9, ...
           'MaxHeadSize',2, 'HandleVisibility','off')
end

for ki = 1:numel(idx1)
    if isnan(lon_src1(ki)), continue; end
    k = idx1(ki);
    text(lon_src1(ki)+0.015, lat_src1(ki)+0.015, ...
         sprintf('(%d,%d)', ISRC(k), JSRC(k)), ...
         'FontSize', 6.5, 'Color', [0.1 0.1 0.1])
end

pad = 0.3;
xlim([min(lon_src1(~isnan(lon_src1)))-pad, max(lon_src1(~isnan(lon_src1)))+pad])
ylim([min(lat_src1(~isnan(lat_src1)))-pad, max(lat_src1(~isnan(lat_src1)))+pad])
xlabel('Longitud (°E)', 'FontSize', 11)
ylabel('Latitud (°N)',  'FontSize', 11)
title({'mask\_v  —  fuentes dsrc=1  (v-face, flujo en eta)', ...
       'Ocre=tierra  Azul=mar  Flecha=dirección flujo'}, ...
      'FontSize', 11, 'FontWeight', 'bold')
%legend('Location','SouthWest','FontSize',9)
colorbar('off')
grid on; box on
