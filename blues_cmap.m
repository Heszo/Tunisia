function cmap = blues_cmap(n)
% Colormap azul claro → azul oscuro (reemplaza 'Blues' de Matplotlib)
    t = linspace(0,1,n)';
    r = 0.97 - 0.72*t;
    g = 0.94 - 0.60*t;
    b = 1.00 - 0.25*t;
    cmap = [r, g, b];
end