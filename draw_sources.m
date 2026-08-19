    function draw_sources(ax, LON_F, LAT_F, DSRC, QBAR, STATUS, ...
                          idx_val, idx_mar, idx_tie, idx_out, ...
                          C_VAL, C_MAR, C_TIE, C_OUT, dl, count)
        axes(ax); hold on
        if any(idx_val)
            scatter(LON_F(idx_val), LAT_F(idx_val), 52, C_VAL, 'o','filled', ...
                    'MarkerEdgeColor','w','LineWidth',0.5)
        end
        if any(idx_mar)
            scatter(LON_F(idx_mar), LAT_F(idx_mar), 62, C_MAR, 's','filled', ...
                    'MarkerEdgeColor','w','LineWidth',0.5)
        end
        if any(idx_tie)
            scatter(LON_F(idx_tie), LAT_F(idx_tie), 68, C_TIE, '^','filled', ...
                    'MarkerEdgeColor','w','LineWidth',0.6)
        end
        if any(idx_out)
            scatter(LON_F(idx_out), LAT_F(idx_out), 58, C_OUT, 'x','LineWidth',1.4)
        end
        for k = 1:count
            if isnan(LON_F(k)), continue; end
            sgn = sign(QBAR(k)); if sgn==0, sgn=1; end
            if DSRC(k)==0, du=sgn*dl; dv=0;
            else,          du=0;      dv=sgn*dl; end
            c = sc(STATUS{k}, C_VAL, C_MAR, C_TIE, C_OUT);
            quiver(LON_F(k), LAT_F(k), du, dv, 0, ...
                   'Color',c,'LineWidth',0.85,'MaxHeadSize',2.5, ...
                   'HandleVisibility','off')
        end
    end
