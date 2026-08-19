%% ============================================================
%  psource_psi.m
%  pcolor en grilla PSI con fuentes dsrc=0 (u) y dsrc=1 (v)
%  Ejecutar sección por sección con F9
% =============================================================

%% 1. PARAMETROS
croco_in = 'croco.in';
grd_file = 'croco_grd.nc';

%% 2. LEER GRID PSI
mask_psi = double(ncread(grd_file, 'mask_psi'));  % (xi_psi, eta_psi)
lon_psi  = ncread(grd_file, 'lon_psi');
lat_psi  = ncread(grd_file, 'lat_psi');

% También necesitamos lon/lat de u y v para posicionar las fuentes
mask_u  = double(ncread(grd_file, 'mask_u'));
mask_v  = double(ncread(grd_file, 'mask_v'));
lon_u   = ncread(grd_file, 'lon_u');
lat_u   = ncread(grd_file, 'lat_u');
lon_v   = ncread(grd_file, 'lon_v');
lat_v   = ncread(grd_file, 'lat_v');

mask_psi(isnan(mask_psi)) = 0;
mask_u(isnan(mask_u))     = 0;
mask_v(isnan(mask_v))     = 0;

fprintf('mask_psi: %d x %d\n', size(mask_psi,1), size(mask_psi,2))

%% 3. LEER PSOURCE
fid   = fopen(croco_in,'r');
lines = {};
while ~feof(fid), lines{end+1} = fgetl(fid); end
fclose(fid);

start_idx = 0;
for i = 1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^psource\s*:','once')) && isempty(strfind(ln,'ncfile'))
        start_idx = i; break
    end
end

nsrc = 0; data_start = 0;
for i = start_idx+1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^\d+$','once'))
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
ISRC=ISRC(1:count); JSRC=JSRC(1:count);
DSRC=DSRC(1:count); QBAR=QBAR(1:count);
fprintf('%d fuentes (dsrc=0: %d  dsrc=1: %d)\n', count, sum(DSRC==0), sum(DSRC==1))

%% 4. OBTENER lon/lat y face_mask de cada fuente
[nxi_u, neta_u] = size(mask_u);
[nxi_v, neta_v] = size(mask_v);

LON_FACE  = NaN(count,1);
LAT_FACE  = NaN(count,1);
FACE_MASK = NaN(count,1);

for k = 1:count
    I = ISRC(k); J = JSRC(k);
    if DSRC(k) == 0   % u-face
        if I>=1 && I<=nxi_u && J>=1 && J<=neta_u
            LON_FACE(k)  = lon_u(I,J);
            LAT_FACE(k)  = lat_u(I,J);
            FACE_MASK(k) = mask_u(I,J);
        end
    elseif DSRC(k) == 1   % v-face
        if I>=1 && I<=nxi_v && J>=1 && J<=neta_v
            LON_FACE(k)  = lon_v(I,J);
            LAT_FACE(k)  = lat_v(I,J);
            FACE_MASK(k) = mask_v(I,J);
        end
    end
end

%% 5. PCOLOR PSI — un solo grafico con ambas direcciones

figure('Color','w','Position',[100 80 950 750])

% --- fondo: mask_psi  0=tierra(ocre)  1=mar(azul) ---
pcolor(lon_psi', lat_psi', mask_psi')
shading flat
colormap([0.82 0.65 0.43    % 0 → tierra ocre
          0.65 0.85 0.94])  % 1 → mar azul
hold on

% --- dsrc=0  u-face  (circulo) ---
idx0    = DSRC == 0;
ok0     = idx0 & FACE_MASK == 0;
bad0    = idx0 & FACE_MASK == 1;
nan0    = idx0 & isnan(FACE_MASK);

if any(ok0)
    scatter(LON_FACE(ok0), LAT_FACE(ok0), 75, ...
            [0.00 0.45 0.70], 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.7, ...
            'DisplayName', sprintf('dsrc=0 valido (%d)', sum(ok0)))
end
if any(bad0)
    scatter(LON_FACE(bad0), LAT_FACE(bad0), 90, ...
            [0.85 0.10 0.15], 'o', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.7, ...
            'DisplayName', sprintf('dsrc=0 mar abierto (%d)', sum(bad0)))
end
if any(nan0)
    scatter(LON_FACE(nan0), LAT_FACE(nan0), 80, ...
            [0.5 0.5 0.5], 'o', ...
            'LineWidth', 1.2, ...
            'DisplayName', sprintf('dsrc=0 fuera grilla (%d)', sum(nan0)))
end

% --- dsrc=1  v-face  (diamante) ---
idx1    = DSRC == 1;
ok1     = idx1 & FACE_MASK == 0;
bad1    = idx1 & FACE_MASK == 1;
nan1    = idx1 & isnan(FACE_MASK);

if any(ok1)
    scatter(LON_FACE(ok1), LAT_FACE(ok1), 75, ...
            [0.00 0.45 0.70], 'd', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.7, ...
            'DisplayName', sprintf('dsrc=1 valido (%d)', sum(ok1)))
end
if any(bad1)
    scatter(LON_FACE(bad1), LAT_FACE(bad1), 90, ...
            [0.85 0.10 0.15], 'd', 'filled', ...
            'MarkerEdgeColor','w', 'LineWidth',0.7, ...
            'DisplayName', sprintf('dsrc=1 mar abierto (%d)', sum(bad1)))
end
if any(nan1)
    scatter(LON_FACE(nan1), LAT_FACE(nan1), 80, ...
            [0.5 0.5 0.5], 'd', ...
            'LineWidth', 1.2, ...
            'DisplayName', sprintf('dsrc=1 fuera grilla (%d)', sum(nan1)))
end

% --- flechas de dirección ---
dl = 0.018;
for k = 1:count
    if isnan(LON_FACE(k)), continue; end
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    if DSRC(k)==0, du=sgn*dl; dv=0;
    else,          du=0;      dv=sgn*dl;
    end
    quiver(LON_FACE(k), LAT_FACE(k), du, dv, 0, ...
           'Color',[0.15 0.15 0.15], 'LineWidth',0.8, ...
           'MaxHeadSize',2, 'HandleVisibility','off')
end

% --- etiquetas I,J ---
for k = 1:count
    if isnan(LON_FACE(k)), continue; end
    text(LON_FACE(k)+0.012, LAT_FACE(k)+0.012, ...
         sprintf('(%d,%d)', ISRC(k), JSRC(k)), ...
         'FontSize', 6, 'Color', [0.1 0.1 0.1])
end

pad = 0.3;
lon_ok = LON_FACE(~isnan(LON_FACE));
lat_ok = LAT_FACE(~isnan(LAT_FACE));
xlim([min(lon_ok)-pad, max(lon_ok)+pad])
ylim([min(lat_ok)-pad, max(lat_ok)+pad])
xlabel('Longitud (°E)', 'FontSize', 11)
ylabel('Latitud (°N)',  'FontSize', 11)
title({'Grilla PSI  —  fuentes psource CROCO', ...
       'Ocre=tierra  Azul=mar  ○=dsrc0(u)  ◇=dsrc1(v)  Flecha=dir flujo'}, ...
      'FontSize', 11, 'FontWeight', 'bold')
%legend('Location','SouthWest','FontSize',9)
grid on; box on
