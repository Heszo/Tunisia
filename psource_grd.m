function psource_grd(croco_in, grd_file)
% PSOURCE_GRD  Diagnóstico de fuentes de ríos CROCO con croco_grd.nc
%
% FÍSICA DEL PSOURCE (staggered grid CROCO/ROMS):
%   dsrc=0  → flujo cruza u-face entre rho(I,J) y rho(I+1,J)
%             Verificar: mask_u(I, J)  [Fortran base-1]
%               = 0  borde tierra-mar  OK
%               = 1  mar abierto       ERROR
%
%   dsrc=1  → flujo cruza v-face entre rho(I,J) y rho(I,J+1)
%             Verificar: mask_v(I, J)
%               = 0  borde tierra-mar  OK
%               = 1  mar abierto       ERROR
%
%   Celda receptora según signo de Qbar:
%     dsrc=0, Qbar>0: rho(I+1, J) → mask_rho(I+1, J)   debe ser 1
%     dsrc=0, Qbar<0: rho(I,   J) → mask_rho(I,   J)   debe ser 1
%     dsrc=1, Qbar>0: rho(I, J+1) → mask_rho(I, J+1)   debe ser 1
%     dsrc=1, Qbar<0: rho(I, J  ) → mask_rho(I, J  )   debe ser 1
%
%   NOTA INDICES:
%     Fortran/MATLAB : base-1  → mask_u(I, J)
%     NetCDF en disco: base-0, transpuesto → ncread devuelve (xi, eta)
%     Así:  mask_u_mat = ncread(...)  tiene size (xi_u, eta_u)
%           mask_u_mat(I, J) equivale al Fortran mask_u(I, J)  ← directo
%
%   FILL_VALUE:
%     ncread() en MATLAB reemplaza fill_value con NaN automáticamente.
%     Para mask_u/mask_v, tierra=0 puede estar almacenada como fill_value.
%     Usamos: mask_u(isnan(mask_u)) = 0;  para restaurar tierra=0.
%
% Uso:
%   psource_grd('croco.in', 'croco_grd.nc')
%
% Genera:
%   psource_grd.png  – figura diagnóstico (3 paneles)
%   psource_grd.csv  – tabla completa con estado de cada fuente
%
% Requiere: MATLAB R2019b o superior (no necesita toolboxes adicionales)

    if nargin < 1, croco_in  = 'croco.in';     end
    if nargin < 2, grd_file  = 'croco_grd.nc'; end

    fprintf('\n[1/4] Leyendo ''%s'' ...\n', croco_in);
    src = parse_psource(croco_in);
    fprintf('  %d fuentes  (dsrc=0: %d, dsrc=1: %d)\n', ...
            height(src), sum(src.dsrc==0), sum(src.dsrc==1));

    fprintf('\n[2/4] Cargando ''%s'' ...\n', grd_file);
    grd = load_grid(grd_file);

    fprintf('\n[3/4] Diagnóstico con mask_u / mask_v ...\n');
    src = diagnose(src, grd);

    % Resumen
    estados = unique(src.status);
    for k = 1:numel(estados)
        n = sum(strcmp(src.status, estados{k}));
        fprintf('  %-25s : %d\n', estados{k}, n);
    end

    bad_idx = ~strcmp(src.status, 'valido');
    bad = src(bad_idx, :);
    if height(bad) > 0
        fprintf('\n  Fuentes a revisar (%d):\n', height(bad));
        disp(bad(:, {'idx','isrc','jsrc','dsrc','qbar', ...
                     'face_mask','rho_recv','status'}));
    end

    % CSV
    writetable(src, 'psource_grd.csv');
    fprintf('\n  CSV -> psource_grd.csv\n');

    fprintf('\n[4/4] Generando figura ...\n');
    make_figure(src, grd);

    fprintf('\nListo!\n');
end


% =========================================================================
% 1. Parser croco.in
% =========================================================================

function src = parse_psource(croco_in)
% Lee el bloque psource: de croco.in y devuelve una table.

    fid = fopen(croco_in, 'r');
    if fid < 0
        error('No se pudo abrir: %s', croco_in);
    end

    lines = {};
    while ~feof(fid)
        lines{end+1} = fgetl(fid); %#ok<AGROW>
    end
    fclose(fid);

    % Buscar línea "psource:" (no "psource_ncfile:")
    start_idx = 0;
    for i = 1:numel(lines)
        ln = strtrim(lines{i});
        if ~isempty(regexp(ln, '^psource\s*:', 'once')) && ...
           isempty(strfind(ln, 'ncfile'))
            start_idx = i;
            break;
        end
    end
    if start_idx == 0
        error('No se encontro bloque psource: en %s', croco_in);
    end

    % Buscar nsrc (primera línea con solo dígitos)
    nsrc = 0; data_start = 0;
    for i = start_idx+1 : numel(lines)
        ln = strtrim(lines{i});
        if ~isempty(regexp(ln, '^\d+$', 'once'))
            nsrc = str2double(ln);
            data_start = i + 1;
            break;
        end
    end
    if nsrc == 0
        error('No se encontro nsrc en el bloque psource');
    end

    % Leer nsrc líneas de datos
    % Formato: Isrc Jsrc Dsrc Qbar Lsrc1 Lsrc2 Tsrc1 Tsrc2
    idx_v    = zeros(nsrc,1);
    isrc_v   = zeros(nsrc,1);
    jsrc_v   = zeros(nsrc,1);
    dsrc_v   = zeros(nsrc,1);
    qbar_v   = zeros(nsrc,1);
    lon_v    = zeros(nsrc,1);
    lat_v    = zeros(nsrc,1);

    count = 0;
    for i = data_start : numel(lines)
        ln = strtrim(lines{i});
        if isempty(ln), continue; end
        parts = strsplit(ln);
        if numel(parts) < 8, break; end

        % Verificar que empiece con enteros
        v1 = str2double(parts{1});
        if isnan(v1), break; end

        count = count + 1;
        idx_v(count)  = count;
        isrc_v(count) = str2double(parts{1});
        jsrc_v(count) = str2double(parts{2});
        dsrc_v(count) = str2double(parts{3});
        qbar_v(count) = str2double(parts{4});
        % parts{5} = Lsrc1 (T/F), parts{6} = Lsrc2 (T/F)
        lon_v(count)  = str2double(parts{7});   % Tsrc1 / lon referencia
        lat_v(count)  = str2double(parts{8});   % Tsrc2 / lat referencia

        if count >= nsrc, break; end
    end

    % Recortar al tamaño real
    idx_v  = idx_v(1:count);
    isrc_v = isrc_v(1:count);
    jsrc_v = jsrc_v(1:count);
    dsrc_v = dsrc_v(1:count);
    qbar_v = qbar_v(1:count);
    lon_v  = lon_v(1:count);
    lat_v  = lat_v(1:count);

    src = table(idx_v, isrc_v, jsrc_v, dsrc_v, qbar_v, lon_v, lat_v, ...
        'VariableNames', {'idx','isrc','jsrc','dsrc','qbar','lon','lat'});
end


% =========================================================================
% 2. Lectura croco_grd.nc
% =========================================================================

function grd = load_grid(grd_file)
% Carga variables del grid NetCDF.
% ncread() devuelve arrays con dimensión (xi, eta) — Fortran/MATLAB order.
% fill_value → NaN en MATLAB; para masks usamos NaN→0 (tierra=0).

    function A = rd(var)
        A = double(ncread(grd_file, var));
        % Para masks: fill_value representa tierra=0, restaurar como 0
        if contains(var, 'mask')
            A(isnan(A)) = 0;
        end
    end

    grd.lon_rho  = rd('lon_rho');    % (xi_rho, eta_rho)
    grd.lat_rho  = rd('lat_rho');
    grd.mask_rho = rd('mask_rho');   % 0=tierra, 1=agua
    grd.mask_u   = rd('mask_u');     % (xi_u, eta_u)
    grd.mask_v   = rd('mask_v');     % (xi_v, eta_v)
    grd.lon_u    = rd('lon_u');
    grd.lat_u    = rd('lat_u');
    grd.lon_v    = rd('lon_v');
    grd.lat_v    = rd('lat_v');
    grd.h        = rd('h');

    [nxi, neta] = size(grd.mask_rho);
    n_tierra = sum(grd.mask_rho(:) == 0);
    n_agua   = sum(grd.mask_rho(:) == 1);
    fprintf('  mask_rho : (%d, %d)  tierra=%d  agua=%d\n', ...
            nxi, neta, n_tierra, n_agua);
    fprintf('  mask_u   : (%d, %d)   mask_v: (%d, %d)\n', ...
            size(grd.mask_u,1), size(grd.mask_u,2), ...
            size(grd.mask_v,1), size(grd.mask_v,2));
end


% =========================================================================
% 3. Diagnóstico
% =========================================================================

function src = diagnose(src, grd)
% Clasifica cada fuente según face_mask y rho_recv.
%
% INDEXACION MATLAB (base-1, ncread devuelve (xi, eta)):
%   dsrc=0: mask_u(I, J)  — directo en Fortran base-1
%           recv (Qbar>0): mask_rho(I+1, J)
%           recv (Qbar<0): mask_rho(I,   J)
%   dsrc=1: mask_v(I, J)
%           recv (Qbar>0): mask_rho(I, J+1)
%           recv (Qbar<0): mask_rho(I, J  )

    n = height(src);
    face_mask_v = NaN(n,1);
    rho_recv_v  = NaN(n,1);
    rho_send_v  = NaN(n,1);
    lon_face_v  = NaN(n,1);
    lat_face_v  = NaN(n,1);
    status_v    = repmat({'indefinido'}, n, 1);

    mask_rho = grd.mask_rho;   % (xi_rho, eta_rho)
    mask_u   = grd.mask_u;     % (xi_u,   eta_u  )
    mask_v   = grd.mask_v;     % (xi_v,   eta_v  )

    [nxi_rho, neta_rho] = size(mask_rho);
    [nxi_u,   neta_u  ] = size(mask_u);
    [nxi_v,   neta_v  ] = size(mask_v);

    for k = 1:n
        I    = src.isrc(k);   % Fortran xi,  base-1
        J    = src.jsrc(k);   % Fortran eta, base-1
        D    = src.dsrc(k);
        Qbar = src.qbar(k);

        if D == 0
            % u-face: mask_u(I, J), entre rho(I,J) y rho(I+1,J)
            face_mask_v(k) = safe_get(mask_u, I, J, nxi_u, neta_u);
            if Qbar >= 0
                rho_recv_v(k) = safe_get(mask_rho, I+1, J, nxi_rho, neta_rho);
                rho_send_v(k) = safe_get(mask_rho, I,   J, nxi_rho, neta_rho);
            else
                rho_recv_v(k) = safe_get(mask_rho, I,   J, nxi_rho, neta_rho);
                rho_send_v(k) = safe_get(mask_rho, I+1, J, nxi_rho, neta_rho);
            end
            lon_face_v(k) = safe_get(grd.lon_u, I, J, nxi_u, neta_u);
            lat_face_v(k) = safe_get(grd.lat_u, I, J, nxi_u, neta_u);

        elseif D == 1
            % v-face: mask_v(I, J), entre rho(I,J) y rho(I,J+1)
            face_mask_v(k) = safe_get(mask_v, I, J, nxi_v, neta_v);
            if Qbar >= 0
                rho_recv_v(k) = safe_get(mask_rho, I, J+1, nxi_rho, neta_rho);
                rho_send_v(k) = safe_get(mask_rho, I, J,   nxi_rho, neta_rho);
            else
                rho_recv_v(k) = safe_get(mask_rho, I, J,   nxi_rho, neta_rho);
                rho_send_v(k) = safe_get(mask_rho, I, J+1, nxi_rho, neta_rho);
            end
            lon_face_v(k) = safe_get(grd.lon_v, I, J, nxi_v, neta_v);
            lat_face_v(k) = safe_get(grd.lat_v, I, J, nxi_v, neta_v);
        end

        % Clasificación
        fm = face_mask_v(k);
        rr = rho_recv_v(k);
        if isnan(fm)
            status_v{k} = 'fuera_de_grilla';
        elseif rr == 1 && fm == 0
            status_v{k} = 'valido';
        elseif fm == 1
            status_v{k} = 'mar_abierto';
        elseif rr == 0
            status_v{k} = 'tierra';
        else
            status_v{k} = 'indefinido';
        end
    end

    src.face_mask = face_mask_v;
    src.rho_recv  = rho_recv_v;
    src.rho_send  = rho_send_v;
    src.lon_face  = lon_face_v;
    src.lat_face  = lat_face_v;
    src.status    = status_v;
end


function v = safe_get(arr, I, J, nxi, neta)
% Acceso seguro a arr(I, J) con chequeo de bounds (base-1).
    if I < 1 || J < 1 || I > nxi || J > neta
        v = NaN;
    else
        v = double(arr(I, J));
    end
end


% =========================================================================
% 4. Figura (3 paneles)
% =========================================================================

function make_figure(src, grd)

    % Colores por estado
    col = struct();
    col.valido          = [0.0,  0.47, 0.71];   % azul
    col.mar_abierto     = [0.96, 0.64, 0.38];   % naranja
    col.tierra          = [0.84, 0.10, 0.16];   % rojo
    col.fuera_de_grilla = [0.68, 0.71, 0.74];   % gris
    col.indefinido      = [0.42, 0.46, 0.44];

    marker_map = struct();
    marker_map.valido          = 'o';
    marker_map.mar_abierto     = 's';
    marker_map.tierra          = '^';
    marker_map.fuera_de_grilla = 'x';
    marker_map.indefinido      = 'd';

    label_map = struct();
    label_map.valido          = 'Valido (borde tierra-mar)';
    label_map.mar_abierto     = 'Mar abierto (face=1)';
    label_map.tierra          = 'Tierra (recv=0)';
    label_map.fuera_de_grilla = 'Fuera de grilla';
    label_map.indefinido      = 'Indefinido';

    estados = {'valido','mar_abierto','tierra','fuera_de_grilla','indefinido'};

    mask_rho = grd.mask_rho;
    lon_rho  = grd.lon_rho;
    lat_rho  = grd.lat_rho;
    [nxi, neta] = size(mask_rho);

    % Submuestreo para rendimiento
    step = max(1, floor(min(nxi,neta)/250));
    ii_s = 1:step:nxi;
    jj_s = 1:step:neta;
    lon_s  = lon_rho(ii_s, jj_s);
    lat_s  = lat_rho(ii_s, jj_s);
    msk_s  = mask_rho(ii_s, jj_s);
    h_s    = grd.h(ii_s, jj_s);
    h_s(msk_s == 0) = NaN;   % tierra → NaN para batimetría

    fig = figure('Color', [0.94 0.96 0.97], 'Position', [50 50 1600 700]);

    % ── Panel 1: Mapa geográfico ──────────────────────────────────────────
    ax1 = subplot(1,3,1);
    hold(ax1,'on');

    % Batimetría (océano)
    pcolor(ax1, lon_s', lat_s', h_s');
    shading(ax1, 'flat');
    colormap(ax1, flipud(parula(128)));   % azul profundo = hondo
    cb = colorbar(ax1);
    cb.Label.String = 'Profundidad h (m)';
    clim(ax1, [0, prctile(h_s(~isnan(h_s)), 98)]);

    % Tierra
    land_mask = msk_s;
    land_mask(land_mask == 1) = NaN;
    land_mask(land_mask == 0) = 1;
    % Dibujar tierra con parche marrón
    [lon_land, lat_land] = meshgrid(lon_s(1,:)', lat_s(:,1)');
    % Usar contourf para tierra
    contourf(ax1, lon_s', lat_s', double(msk_s' == 0), [0.5 0.5], ...
             'FaceColor', [0.83 0.65 0.42], 'EdgeColor', 'none');

    % Línea de costa fina
    contour(ax1, lon_rho(1:2:end,1:2:end)', lat_rho(1:2:end,1:2:end)', ...
            mask_rho(1:2:end,1:2:end)', [0.5 0.5], ...
            'Color', [0.15 0.27 0.33], 'LineWidth', 0.7);

    % Fuentes por estado
    for ke = 1:numel(estados)
        est = estados{ke};
        idx_e = strcmp(src.status, est);
        if ~any(idx_e), continue; end
        sub = src(idx_e, :);
        c = col.(est);
        mk = marker_map.(est);
        lbl = label_map.(est);
        plot(ax1, sub.lon_face, sub.lat_face, mk, ...
             'Color', c, 'MarkerFaceColor', c, ...
             'MarkerSize', 8, 'LineWidth', 1.2, ...
             'DisplayName', sprintf('%s (%d)', lbl, sum(idx_e)));
    end

    % Etiquetas de problemáticos
    bad_est = {'tierra','mar_abierto','fuera_de_grilla'};
    for kb = 1:numel(bad_est)
        est = bad_est{kb};
        idx_b = strcmp(src.status, est);
        if ~any(idx_b), continue; end
        sub_b = src(idx_b,:);
        for kk = 1:height(sub_b)
            text(ax1, sub_b.lon_face(kk)+0.02, sub_b.lat_face(kk)+0.02, ...
                 sprintf('#%d', sub_b.idx(kk)), ...
                 'FontSize', 6, 'Color', col.(est), ...
                 'BackgroundColor', 'w', 'EdgeColor', col.(est));
        end
    end

    pad = 0.4;
    xlim(ax1, [min(src.lon)-pad, max(src.lon)+pad]);
    ylim(ax1, [min(src.lat)-pad, max(src.lat)+pad]);
    xlabel(ax1, 'Longitud (°E)'); ylabel(ax1, 'Latitud (°N)');
    title(ax1, {'Mapa geográfico','(posición real de u/v-face)'}, ...
          'FontWeight', 'bold');
    grid(ax1, 'on'); box(ax1, 'on');
    legend(ax1, 'Location', 'SouthWest', 'FontSize', 7);
    set(ax1, 'Color', [0.79 0.94 0.97]);

    % ── Panel 2: Espacio I-J ──────────────────────────────────────────────
    ax2 = subplot(1,3,2);
    hold(ax2, 'on');

    % Fondo con mask_rho en índices
    step2 = max(1, floor(min(nxi,neta)/350));
    [II, JJ] = meshgrid(1:step2:nxi, 1:step2:neta);
    M2 = mask_rho(1:step2:nxi, 1:step2:neta);

    % Océano
    sea_ii = II(M2' == 1);  sea_jj = JJ(M2' == 1);
    plot(ax2, sea_ii, sea_jj, '.', 'Color', [0.79 0.94 0.97], ...
         'MarkerSize', 2, 'HandleVisibility', 'off');
    % Tierra
    lnd_ii = II(M2' == 0);  lnd_jj = JJ(M2' == 0);
    plot(ax2, lnd_ii, lnd_jj, '.', 'Color', [0.83 0.65 0.42], ...
         'MarkerSize', 2, 'HandleVisibility', 'off');

    % Fuentes
    for ke = 1:numel(estados)
        est = estados{ke};
        idx_e = strcmp(src.status, est);
        if ~any(idx_e), continue; end
        sub = src(idx_e, :);
        c = col.(est); mk = marker_map.(est);
        lbl = label_map.(est);
        plot(ax2, sub.isrc, sub.jsrc, mk, ...
             'Color', c, 'MarkerFaceColor', c, ...
             'MarkerSize', 8, 'LineWidth', 1.2, ...
             'DisplayName', sprintf('%s (%d)', lbl, sum(idx_e)));
    end

    % Etiquetas índice
    for k = 1:height(src)
        text(ax2, src.isrc(k)+1, src.jsrc(k)+1, ...
             sprintf('#%d', src.idx(k)), ...
             'FontSize', 5, 'Color', col.(src.status{k}));
    end

    % Flechas de dirección del flujo
    for k = 1:height(src)
        sgn = sign(src.qbar(k)); if sgn==0, sgn=1; end
        if src.dsrc(k) == 0
            dx = sgn*4; dy = 0;
        elseif src.dsrc(k) == 1
            dx = 0; dy = sgn*4;
        else
            continue;
        end
        c = col.(src.status{k});
        quiver(ax2, src.isrc(k), src.jsrc(k), dx, dy, 0, ...
               'Color', c, 'LineWidth', 0.8, 'MaxHeadSize', 0.8, ...
               'HandleVisibility', 'off');
    end

    xlim(ax2, [min(src.isrc)-15, max(src.isrc)+15]);
    ylim(ax2, [min(src.jsrc)-15, max(src.jsrc)+15]);
    xlabel(ax2, 'I (Fortran xi, base-1)  →  MATLAB col = I');
    ylabel(ax2, 'J (Fortran eta, base-1)  →  MATLAB row = J');
    title(ax2, {'Espacio de grilla (I, J Fortran)', ...
                'Azul=oceano  Ocre=tierra  Flecha=direccion flujo'}, ...
          'FontWeight', 'bold');
    grid(ax2, 'on'); box(ax2, 'on');
    legend(ax2, 'Location', 'Best', 'FontSize', 7);

    % Caja de referencia
    annotation('textbox', [0.67 0.08 0.13 0.10], ...
        'String', {'dsrc=0 -> mask\_u(I,J)', ...
                   'dsrc=1 -> mask\_v(I,J)', ...
                   'face=0 OK  face=1 mar abierto', ...
                   'rho\_recv=1 OK  rho\_recv=0 tierra'}, ...
        'FitBoxToText', 'on', 'BackgroundColor', [1 1 0.87], ...
        'EdgeColor', [0.7 0.7 0.7], 'FontSize', 7.5);

    % ── Panel 3: Tabla de sospechosos ────────────────────────────────────
    ax3 = subplot(1,3,3);
    axis(ax3, 'off');

    bad_mask = ~strcmp(src.status, 'valido');
    bad_tbl  = src(bad_mask, :);
    n_ok     = sum(~bad_mask);

    title(ax3, sprintf('Fuentes a revisar: %d / %d', height(bad_tbl), height(src)), ...
          'FontWeight', 'bold', 'FontSize', 11);

    if height(bad_tbl) == 0
        text(0.5, 0.5, 'Todas las fuentes son validas', ...
             'Units', 'normalized', 'HorizontalAlignment', 'center', ...
             'FontSize', 13, 'Color', col.valido, 'Parent', ax3);
    else
        % Construir tabla como texto
        col_names = {'#','I','J','dsrc','Qbar','Lon','Lat', ...
                     'face','recv','Estado'};
        col_w = [4, 5, 5, 6, 7, 8, 8, 6, 6, 16];
        header = '';
        for kc = 1:numel(col_names)
            header = [header, sprintf('%-*s ', col_w(kc), col_names{kc})]; %#ok
        end

        rows = {header, repmat('-', 1, length(header))};
        for k = 1:height(bad_tbl)
            r = bad_tbl(k,:);
            fm_s = num2str(r.face_mask, '%.0f');
            rv_s = num2str(r.rho_recv,  '%.0f');
            if isnan(r.face_mask), fm_s = '?'; end
            if isnan(r.rho_recv),  rv_s = '?'; end
            row_str = sprintf('%-4d %-5d %-5d %-6d %-7.0f %-8.3f %-8.3f %-6s %-6s %-s', ...
                r.idx, r.isrc, r.jsrc, r.dsrc, r.qbar, ...
                r.lon, r.lat, fm_s, rv_s, r.status{1});
            rows{end+1} = row_str; %#ok
        end

        % Calcular posición vertical para cada fila
        n_rows   = numel(rows);
        y_start  = 0.92;
        y_step   = min(0.06, 0.85 / n_rows);
        mono_font = 'Courier New';

        for kr = 1:n_rows
            ypos = y_start - (kr-1)*y_step;
            if kr <= 2
                fw = 'bold'; fs = 8;
            else
                fw = 'normal'; fs = 7.5;
                % Colorear según estado
                est_k = bad_tbl.status{kr-2};
                fc = col.(est_k);
            end
            if kr > 2
                text(0.02, ypos, rows{kr}, ...
                     'Units', 'normalized', 'Parent', ax3, ...
                     'FontName', mono_font, 'FontSize', fs, ...
                     'FontWeight', fw, 'Color', fc, ...
                     'Interpreter', 'none');
            else
                text(0.02, ypos, rows{kr}, ...
                     'Units', 'normalized', 'Parent', ax3, ...
                     'FontName', mono_font, 'FontSize', fs, ...
                     'FontWeight', fw, 'Color', [0 0 0], ...
                     'Interpreter', 'none');
            end
        end
    end

    % Resumen numérico debajo
    resumen = sprintf('OK: %d  |  Revisar: %d  |  Total: %d', ...
                      n_ok, height(bad_tbl), height(src));
    annotation('textbox', [0.68 0.03 0.29 0.05], ...
        'String', resumen, 'HorizontalAlignment', 'center', ...
        'FitBoxToText', 'on', 'BackgroundColor', 'white', ...
        'EdgeColor', [0.7 0.7 0.7], 'FontSize', 9, 'FontWeight', 'bold');

    % ── Título global ─────────────────────────────────────────────────────
    n_bad = height(bad_tbl);
    sgtitle(sprintf('Diagnostico psource CROCO  |  %d fuentes  |  OK: %d  Revisar: %d', ...
                    height(src), n_ok, n_bad), ...
            'FontWeight', 'bold', 'FontSize', 12);

    % Guardar
    saveas(fig, 'psource_grd.png');
    fprintf('  PNG -> psource_grd.png\n');
    % Para mayor calidad (si se tiene print):
    % print(fig, 'psource_grd', '-dpng', '-r150');
end
