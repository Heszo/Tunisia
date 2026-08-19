%% ============================================================
%  psource_plot.m
%  Plot de fuentes de ríos CROCO sobre batimetría (pcolor)
%  Ejecutar sección por sección con F9
% =============================================================

%% 1. PARAMETROS — editar aquí
croco_in = 'croco.in';
grd_file = 'croco_grd.nc';

%% 2. LEER croco_grd.nc
lon_rho  = ncread(grd_file, 'lon_rho');    % (xi_rho, eta_rho)
lat_rho  = ncread(grd_file, 'lat_rho');
mask_rho = double(ncread(grd_file, 'mask_rho'));
mask_u   = double(ncread(grd_file, 'mask_u'));
mask_v   = double(ncread(grd_file, 'mask_v'));
lon_u    = ncread(grd_file, 'lon_u');
lat_u    = ncread(grd_file, 'lat_u');
lon_v    = ncread(grd_file, 'lon_v');
lat_v    = ncread(grd_file, 'lat_v');
h        = double(ncread(grd_file, 'h'));

% fill_value → NaN; para máscaras tierra=0 puede ser fill_value → restaurar
mask_rho(isnan(mask_rho)) = 0;
mask_u(isnan(mask_u))     = 0;
mask_v(isnan(mask_v))     = 0;

disp('Grid cargado OK')
disp(size(mask_rho))   % debe ser (xi_rho, eta_rho)

%% 3. LEER PSOURCE de croco.in
fid   = fopen(croco_in, 'r');
lines = {};
while ~feof(fid)
    lines{end+1} = fgetl(fid);
end
fclose(fid);

% Buscar línea "psource:" (no psource_ncfile)
start_idx = 0;
for i = 1:numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^psource\s*:','once')) && isempty(strfind(ln,'ncfile'))
        start_idx = i;
        break
    end
end

% Leer nsrc
nsrc = 0; data_start = 0;
for i = start_idx+1 : numel(lines)
    ln = strtrim(lines{i});
    if ~isempty(regexp(ln,'^\d+$','once'))
        nsrc = str2double(ln);
        data_start = i + 1;
        break
    end
end
fprintf('nsrc = %d\n', nsrc)

% Leer las nsrc líneas de datos
% Formato: Isrc Jsrc Dsrc Qbar Lsrc1 Lsrc2 Tsrc1(lon) Tsrc2(lat)
ISRC = zeros(nsrc,1);
JSRC = zeros(nsrc,1);
DSRC = zeros(nsrc,1);
QBAR = zeros(nsrc,1);
LON  = zeros(nsrc,1);
LAT  = zeros(nsrc,1);

count = 0;
for i = data_start : numel(lines)
    ln = strtrim(lines{i});
    if isempty(ln), continue; end
    p = strsplit(ln);
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
ISRC = ISRC(1:count);
JSRC = JSRC(1:count);
DSRC = DSRC(1:count);
QBAR = QBAR(1:count);
LON  = LON(1:count);
LAT  = LAT(1:count);
fprintf('Leídas %d fuentes\n', count)

%% 4. DIAGNOSTICO: face_mask y rho_recv
% MATLAB base-1, ncread devuelve (xi, eta)
% dsrc=0 → mask_u(I, J)     entre rho(I,J) y rho(I+1,J)
% dsrc=1 → mask_v(I, J)     entre rho(I,J) y rho(I,J+1)

[nxi_rho, neta_rho] = size(mask_rho);
[nxi_u,   neta_u  ] = size(mask_u);
[nxi_v,   neta_v  ] = size(mask_v);

FACE_MASK = NaN(count,1);
RHO_RECV  = NaN(count,1);
LON_FACE  = NaN(count,1);
LAT_FACE  = NaN(count,1);
STATUS    = repmat({'indefinido'}, count, 1);

for k = 1:count
    I = ISRC(k);  J = JSRC(k);  D = DSRC(k);  Q = QBAR(k);

    if D == 0   % u-face
        if I>=1 && I<=nxi_u && J>=1 && J<=neta_u
            FACE_MASK(k) = mask_u(I,J);
        end
        if Q >= 0
            if I+1<=nxi_rho && J>=1 && J<=neta_rho
                RHO_RECV(k) = mask_rho(I+1,J);
            end
        else
            if I>=1 && I<=nxi_rho && J>=1 && J<=neta_rho
                RHO_RECV(k) = mask_rho(I,J);
            end
        end
        if I>=1 && I<=nxi_u && J>=1 && J<=neta_u
            LON_FACE(k) = lon_u(I,J);
            LAT_FACE(k) = lat_u(I,J);
        end

    elseif D == 1   % v-face
        if I>=1 && I<=nxi_v && J>=1 && J<=neta_v
            FACE_MASK(k) = mask_v(I,J);
        end
        if Q >= 0
            if I>=1 && I<=nxi_rho && J+1<=neta_rho
                RHO_RECV(k) = mask_rho(I,J+1);
            end
        else
            if I>=1 && I<=nxi_rho && J>=1 && J<=neta_rho
                RHO_RECV(k) = mask_rho(I,J);
            end
        end
        if I>=1 && I<=nxi_v && J>=1 && J<=neta_v
            LON_FACE(k) = lon_v(I,J);
            LAT_FACE(k) = lat_v(I,J);
        end
    end

    % Clasificar
    fm = FACE_MASK(k); rr = RHO_RECV(k);
    if isnan(fm)
        STATUS{k} = 'fuera_de_grilla';
    elseif rr==1 && fm==0
        STATUS{k} = 'valido';
    elseif fm==1
        STATUS{k} = 'mar_abierto';
    elseif rr==0
        STATUS{k} = 'tierra';
    end
end

% Resumen
u_est = unique(STATUS);
for k = 1:numel(u_est)
    fprintf('  %-20s : %d\n', u_est{k}, sum(strcmp(STATUS, u_est{k})));
end

%% 5. PCOLOR — mar/tierra + fuentes
figure('Color','w','Position',[100 100 1000 750])

% Construir imagen de 3 valores:
%   0 = tierra   → ocre
%   1 = mar      → azul (proporcional a batimetría)
% Usamos un array combinado: h normalizado en [0,1] para el mar,
% y un valor negativo (-1) para tierra, que el colormap pinta de ocre.
step = 2;
lon_s    = lon_rho(1:step:end, 1:step:end)';
lat_s    = lat_rho(1:step:end, 1:step:end)';
mask_s   = mask_rho(1:step:end, 1:step:end)';
h_s      = h(1:step:end, 1:step:end)';

% Normalizar batimetría [0,1]
h_max = prctile(h_s(:), 98);
h_norm = h_s / h_max;          % océano: 0 (somero) a 1 (profundo)
h_norm(mask_s == 0) = -0.15;   % tierra: valor negativo reservado

% pcolor único — colormap combinado: ocre para tierra, azul para mar
pcolor(lon_s, lat_s, h_norm)
shading flat

% Colormap: primer color = tierra (ocre), resto = azul claro→oscuro
n_mar   = 128;
c_tierra = [0.82 0.65 0.43];          % ocre
c_mar    = blues_cmap(n_mar);          % azul
cmap_combined = [c_tierra; c_mar];
colormap(cmap_combined)

% Colorbar solo para la parte del mar
cb = colorbar;
cb.Label.String = 'Profundidad normalizada  (0=somero  1=profundo)';
cb.Ticks = linspace(0,1,5);
cb.TickLabels = arrayfun(@(x) sprintf('%.0f m', x*h_max), ...
                          cb.Ticks, 'UniformOutput', false);
hold on

% --- Fuentes por estado ---
col_valido      = [0.00 0.47 0.71];
col_mar_abierto = [0.96 0.64 0.38];
col_tierra      = [0.84 0.10 0.16];
col_grilla      = [0.60 0.60 0.60];

idx_val  = strcmp(STATUS,'valido');
idx_mar  = strcmp(STATUS,'mar_abierto');
idx_tie  = strcmp(STATUS,'tierra');
idx_fgr  = strcmp(STATUS,'fuera_de_grilla');

if any(idx_val)
    plot(LON_FACE(idx_val), LAT_FACE(idx_val), 'o', ...
         'Color', col_valido, 'MarkerFaceColor', col_valido, ...
         'MarkerSize', 9, 'LineWidth', 1, 'DisplayName', ...
         sprintf('Valido (%d)', sum(idx_val)))
end
if any(idx_mar)
    plot(LON_FACE(idx_mar), LAT_FACE(idx_mar), 's', ...
         'Color', col_mar_abierto, 'MarkerFaceColor', col_mar_abierto, ...
         'MarkerSize', 9, 'LineWidth', 1, 'DisplayName', ...
         sprintf('Mar abierto (%d)', sum(idx_mar)))
end
if any(idx_tie)
    plot(LON_FACE(idx_tie), LAT_FACE(idx_tie), '^', ...
         'Color', col_tierra, 'MarkerFaceColor', col_tierra, ...
         'MarkerSize', 10, 'LineWidth', 1.2, 'DisplayName', ...
         sprintf('Tierra (%d)', sum(idx_tie)))
end
if any(idx_fgr)
    plot(LON_FACE(idx_fgr), LAT_FACE(idx_fgr), 'x', ...
         'Color', col_grilla, 'MarkerSize', 10, 'LineWidth', 1.5, ...
         'DisplayName', sprintf('Fuera de grilla (%d)', sum(idx_fgr)))
end

% --- Flechas de dirección del flujo ---
for k = 1:count
    if isnan(LON_FACE(k)), continue; end
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    dl  = 0.025;
    if DSRC(k)==0,  dlon=sgn*dl; dlat=0;
    else,           dlon=0;      dlat=sgn*dl;
    end
    c = col_valido;
    if strcmp(STATUS{k},'mar_abierto'), c = col_mar_abierto; end
    if strcmp(STATUS{k},'tierra'),      c = col_tierra;      end
    if strcmp(STATUS{k},'fuera_de_grilla'), c = col_grilla;  end
    quiver(LON_FACE(k), LAT_FACE(k), dlon, dlat, 0, ...
           'Color', c, 'LineWidth', 1.0, 'MaxHeadSize', 1.5, ...
           'HandleVisibility','off')
end

% --- Etiquetas de problemáticos ---
bad_idx = find(idx_mar | idx_tie | idx_fgr);
for k = 1:numel(bad_idx)
    ki = bad_idx(k);
    if isnan(LON_FACE(ki)), continue; end
    text(LON_FACE(ki)+0.02, LAT_FACE(ki)+0.02, ...
         sprintf('#%d (%d,%d)', ki, ISRC(ki), JSRC(ki)), ...
         'FontSize', 7, 'Color', [0.7 0 0], ...
         'BackgroundColor','w', 'EdgeColor',[0.7 0 0])
end

% Zoom a región de fuentes
pad = 0.35;
xlim([min(LON)-pad, max(LON)+pad])
ylim([min(LAT)-pad, max(LAT)+pad])
xlabel('Longitud (°E)', 'FontSize', 11)
ylabel('Latitud (°N)',  'FontSize', 11)
title('Salidas de ríos CROCO  —  pcolor batimetría + mask diagnostico', ...
      'FontSize', 12, 'FontWeight', 'bold')
legend('Location','SouthWest','FontSize',8)
grid on; box on

%% 6. FIGURA 2 — espacio I,J con pcolor de mask_rho
figure('Color','w','Position',[150 80 850 700])

% pcolor de mask_rho en índices (submuestreado)
% 0 = tierra (ocre)   1 = mar (azul)
step3 = 3;
[XI, EJ] = meshgrid(1:step3:size(mask_rho,1), 1:step3:size(mask_rho,2));
M_sub = mask_rho(1:step3:end, 1:step3:end);

pcolor(XI, EJ, M_sub')
shading flat
colormap([0.82 0.65 0.43; 0.79 0.94 0.97])   % 0=tierra ocre, 1=mar azul
clim([-0.01 1.01])   % asegura que 0 y 1 caen en los extremos del colormap
hold on

% Fuentes
if any(idx_val)
    plot(ISRC(idx_val), JSRC(idx_val), 'o', ...
         'Color', col_valido, 'MarkerFaceColor', col_valido, ...
         'MarkerSize', 9, 'DisplayName', 'Valido')
end
if any(idx_mar)
    plot(ISRC(idx_mar), JSRC(idx_mar), 's', ...
         'Color', col_mar_abierto, 'MarkerFaceColor', col_mar_abierto, ...
         'MarkerSize', 9, 'DisplayName', 'Mar abierto')
end
if any(idx_tie)
    plot(ISRC(idx_tie), JSRC(idx_tie), '^', ...
         'Color', col_tierra, 'MarkerFaceColor', col_tierra, ...
         'MarkerSize', 10, 'DisplayName', 'Tierra')
end
if any(idx_fgr)
    plot(ISRC(idx_fgr), JSRC(idx_fgr), 'x', ...
         'Color', col_grilla, 'MarkerSize', 10, 'LineWidth', 1.5, ...
         'DisplayName', 'Fuera de grilla')
end

% Etiquetas
for k = 1:count
    c = col_valido;
    if strcmp(STATUS{k},'mar_abierto'), c = col_mar_abierto; end
    if strcmp(STATUS{k},'tierra'),      c = col_tierra;      end
    if strcmp(STATUS{k},'fuera_de_grilla'), c = col_grilla;  end
    text(ISRC(k)+1, JSRC(k)+1, sprintf('%d', k), ...
         'FontSize', 6, 'Color', c)
end

% Flechas
for k = 1:count
    sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
    if DSRC(k)==0,  di=sgn*4; dj=0;
    else,           di=0;     dj=sgn*4;
    end
    c = col_valido;
    if strcmp(STATUS{k},'mar_abierto'), c = col_mar_abierto; end
    if strcmp(STATUS{k},'tierra'),      c = col_tierra;      end
    quiver(ISRC(k), JSRC(k), di, dj, 0, 'Color', c, ...
           'LineWidth', 0.9, 'MaxHeadSize', 0.8, 'HandleVisibility','off')
end

xlim([min(ISRC)-10, max(ISRC)+10])
ylim([min(JSRC)-10, max(JSRC)+10])
xlabel('I (Fortran xi, base-1)', 'FontSize', 11)
ylabel('J (Fortran eta, base-1)', 'FontSize', 11)
title({'Espacio de grilla  (I, J  Fortran base-1)', ...
       'Ocre=tierra  Azul=oceano  Flecha=dir flujo'}, ...
      'FontSize', 11, 'FontWeight', 'bold')
legend('Location','Best','FontSize',8)
grid on; box on

%% 7. IMPRIMIR TABLA DE PROBLEMATICOS
fprintf('\n====== FUENTES A REVISAR ======\n')
fprintf('%-4s %-5s %-5s %-5s %-8s %-8s %-8s %-6s %-6s  %s\n', ...
        '#','I','J','dsrc','Qbar','Lon','Lat','fMask','recv','Status')
for k = 1:count
    if strcmp(STATUS{k},'valido'), continue; end
    if isnan(FACE_MASK(k)), fm_s=sprintf('?');
    else, fm_s=sprintf('%.0f',FACE_MASK(k)); end
    if isnan(RHO_RECV(k)), rv_s=sprintf('?');
    else, rv_s=sprintf('%.0f',RHO_RECV(k)); end
    fprintf('%-4d %-5d %-5d %-5d %-8.0f %-8.3f %-8.3f %-6s %-6s  %s\n', ...
            k, ISRC(k), JSRC(k), DSRC(k), QBAR(k), LON(k), LAT(k), ...
            fm_s, rv_s, STATUS{k})
end

%% -- función interna de colormap azul (no requiere toolbox) ---------------
function cmap = blues_cmap(n)
% Colormap azul claro → azul oscuro (reemplaza 'Blues' de Matplotlib)
    t = linspace(0,1,n)';
    r = 0.97 - 0.72*t;
    g = 0.94 - 0.60*t;
    b = 1.00 - 0.25*t;
    cmap = [r, g, b];
end
