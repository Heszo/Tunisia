function c = src_color(status, C_VAL, C_MAR, C_TIE, C_OUT)
    switch status
        case 'valido',      c = C_VAL;
        case 'mar_abierto', c = C_MAR;
        case 'tierra',      c = C_TIE;
        otherwise,          c = C_OUT;
    end
end