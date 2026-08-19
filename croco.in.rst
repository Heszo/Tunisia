title:
        TUNISIA MODEL — RESTART Y2020M02 desde paso 121441 (2020-02-07 16:00 UTC)
!
! ============================================================
! RESTART desde RST:  CROCO_FILES/croco_rst.nc
!   scrum_time RST  = 7342.6667 días  →  2020-02-07 16:00 UTC
!   scrum_time FIN  = 7365.0000 días  →  2020-03-01 00:00 UTC
!   Δt pendiente    = 1 929 600 s     =  22.33 días
!
! dt=20s (RECOMENDADO — 3 blowups previos con dt≥40s)
!   NTIMES = 96 479    NRST = 4320    NAVG = 2880
!
! Para usar dt=40s (más rápido, riesgo de blowup):
!   NTIMES = 48 239    NRST = 2160    NAVG = 1440    NDTFAST = 40
! ============================================================
!
time_stepping: NTIMES   dt[sec]  NDTFAST  NINFO
               96479      20       20       1
!
time_stepping_nbq: NDTNBQ    CSOUND_NBQ    VISC2_NBQ
                     1         1000         0.01
!
S-coord: THETA_S,   THETA_B,    Hc (m)
           7.0d0     2.0d0      200.0d0

grid:  filename
    CROCO_FILES/croco_grd.nc
forcing: filename
    CROCO_FILES/croco_frc.nc
bulk_forcing: filename
    CROCO_FILES/croco_blk.nc
climatology: filename
    CROCO_FILES/croco_clm.nc
boundary: filename
    CROCO_FILES/croco_bry.nc
!
! *** CLAVE: leer desde RST, NRREC=-1 = último registro ***
initial: NRREC / filename
          -1
    CROCO_FILES/croco_rst.nc
!
! NRST=4320 → escribe RST cada 1 día (4320 × 20s = 86400s)
! NRPFRST=-1 → un solo registro (sobrescribe, protege el último estado)
restart:          NRST, NRPFRST / filename
                  4320      -1
    CROCO_FILES/croco_rst.nc
!
! *** LDEFHIS=T → crea archivo nuevo (evita corrupción del his anterior) ***
! NWRT=4320 → escribe HIS cada 1 día
history: LDEFHIS, NWRT, NRPFHIS / filename
            T    4320     0
    CROCO_FILES/croco_his_rst.nc
!
! NAVG=2880 → promedios cada 16 h (2880 × 20s = 57600s)
averages: NTSAVG, NAVG, NRPFAVG / filename
            1    2880    0
    CROCO_FILES/croco_avg_rst.nc

primary_history_fields: zeta UBAR VBAR  U  V   wrtT(1:NT)
                          T    T   T   T  T  T  T  50*F
auxiliary_history_fields:   rho Omega  W  Akv  Akt  Aks  Bvf  Visc3d Diff3d  HBL HBBL Bostr Bustr Bvstr Wstr Ustr Vstr Shfl Swfl rsw rlw lat sen HEL
                             50*F   F     T   F    T    F   F    F       F       T   T    T     F      F     T    T    T    T    T   30*T
gls_history_fields:   TKE  GLS  Lscale
                       T     T    T

primary_averages: zeta UBAR VBAR  U  V   wrtT(1:NT)
                   T    T    T    T  T T T   50*F
auxiliary_averages: rho Omega  W  Akv  Akt  Aks  Bvf Visc3d Diff3d HBL HBBL Bostr Bustr Bvstr Wstr Ustr Vstr Shfl Swfl rsw rlw lat sen HEL
                     50*F   T     T   F    T    F    F    F     F      T   T    T     F     F     T   T    T     T    T   30*T
gls_averages:   TKE  GLS  Lscale
                 T     T    T

rho0:
      1025.d0

lateral_visc:   VISC2,    VISC4    [m^2/sec for all]
                 0.       0.

tracer_diff2: TNU2(1:NT)           [m^2/sec for all]
               50*0.d0

tracer_diff4: TNU4(1:NT)           [m^4/sec for all]
               50*0.d11

vertical_mixing: Akv_bak, Akt_bak [m^2/sec]
                   1.d-5    1.d-6

bottom_drag:     RDRG [m/s],  RDRG2,  Zob [m],  Cdb_min, Cdb_max
                 0.0d-04      0.d-3   1.d-2     1.d-4    1.d-1

gamma2:
                 1.d0

sponge:          X_SPONGE [m],    V_SPONGE [m^2/sec]
                    XXX               XXX

nudg_cof:    TauT_in, TauT_out, TauM_in, TauM_out  [days for all]
                1.      360.      3.      360.

diagnostics:   ldefdia   nwrtdia    nrpfdia /filename
                  T        72         0
    CROCO_FILES/croco_dia.nc

diag_avg: ldefdia_avg  ntsdia_avg  nwrtdia_avg  nprfdia_avg /filename
               T          1           72            0
    CROCO_FILES/croco_dia_avg.nc

diag_mld_crit_threshold: CRT1 (Dens [kg/m3]), CRT2 (Temp [Celsius]), CRT3 (Temp [Celsius])
                         3.d-2                2.d-1                  5.d-1

diag_mld_depth_ref: [m]
                10

diag3D_history_fields:    diag_tracers3D(1:NT)
                            50*T

diag2D_history_fields:    diag_tracers2D(1:NT)
                            50*T

diag3D_average_fields:    diag_tracers3D_avg(1:NT)
                            50*T

diag2D_average_fields:    diag_tracers2D_avg(1:NT)
                            50*T

diagnosticsM:   ldefdiaM   nwrtdiaM    nrpfdiaM /filename
                   T          72          0
    CROCO_FILES/croco_diaM.nc

diagM_avg: ldefdiaM_avg  ntsdiaM_avg  nwrtdiaM_avg  nprfdiaM_avg /filename
               T          1           72            0
    CROCO_FILES/croco_diaM_avg.nc

diagM_history_fields: diag_momentum(1:2)
                            T T

diagM_average_fields: diag_momentum_avg(1:2)
                            T T


diags_vrt:   ldefdiags_vrt, nwrtdiags_vrt, nrpfdiags_vrt /filename
                   T          72        0
    CROCO_FILES/croco_diags_vrt.nc

diags_vrt_avg: ldefdiags_vrt_avg  ntsdiags_vrt_avg  nwrtdiags_vrt_avg  nprfdiags_vrt_avg /filename
               T          1          72          0
    CROCO_FILES/croco_diags_vrt_avg.nc

diags_vrt_history_fields: diags_vrt
                            T

diags_vrt_average_fields: diags_vrt_avg
                            T


diags_ek:   ldefdiags_ek, nwrtdiags_ek, nrpfdiags_ek /filename
                   T          72        0
    CROCO_FILES/croco_diags_ek.nc

diags_ek_avg: ldefdiags_ek_avg  ntsdiags_ek_avg  nwrtdiags_ek_avg  nprfdiags_ek_avg /filename
               T          1           72          0
    CROCO_FILES/croco_diags_ek_avg.nc

diags_ek_history_fields: diags_ek
                            T

diags_ek_average_fields: diags_ek_avg
                            T

surf:   ldefsurf, nwrtsurf, nrpfsurf /filename
                   T          1        0
    CROCO_FILES/croco_surf.nc

surf_avg: ldefsurf_avg  ntssurf_avg  nwrtsurf_avg  nprfsurf_avg /filename
               F          1           4          0
    CROCO_FILES/croco_surf_avg.nc

surf_history_fields: surf
                            T

surf_average_fields: surf_avg
                            F


diags_pv:   ldefdiags_pv, nwrtdiags_pv, nrpfdiags_pv /filename
                   T          72        0
    CROCO_FILES/croco_diags_pv.nc

diags_pv_avg: ldefdiags_pv_avg  ntsdiags_pv_avg  nwrtdiags_pv_avg  nprfdiags_pv_avg /filename
               T          1           72          0
    CROCO_FILES/croco_diags_pv_avg.nc

diags_pv_history_fields: diags_pv(1:NT)
                            50*T

diags_pv_average_fields: diags_pv_avg(1:NT)
                            50*T


diags_eddy:   ldefdiags_eddy, nwrtdiags_eddy, nrpfdiags_eddy /filename
                   T          72        0
    CROCO_FILES/croco_diags_eddy.nc

diags_eddy_avg: ldefdiags_eddy_avg  ntsdiags_eddy_avg  nwrtdiags_eddy_avg  nprfdiags_eddy_avg /filename
               T          1           72          0
    CROCO_FILES/croco_diags_eddy_avg.nc

diags_eddy_history_fields: diags_eddy
                            T

diags_eddy_average_fields: diags_eddy_avg
                            T


diagnostics_bio:   ldefdiabio   nwrtdiabio    nrpfdiabio /filename
                        T          72             0
    CROCO_FILES/croco_diabio.nc

diagbio_avg: ldefdiabio_avg  ntsdiabio_avg  nwrtdiabio_avg  nprfdiabio_avg /filename
                  T              1              72              0
    CROCO_FILES/croco_diabio_avg.nc

diagbioFlux_history_fields:    wrtdiabioFlux
                                 50*T

diagbioVSink_history_fields:   wrtdiabioVSink
                                 50*T

diagbioGasExc_history_fields:  wrtdiabioGasExc
                                 50*T

diagbioFlux_average_fields:    wrtdiabioFlux_avg
                                 50*T

diagbioVSink_average_fields:   wrtdiabioVSink_avg
                                 50*T

diagbioGasExc_average_fields:  wrtdiabioGasExc_avg
                                 50*T

biology:   forcing file
             CROCO_FILES/croco_frcbio.nc

wkb_boundary: filename
             CROCO_FILES/croco_wkb.nc
wkb_wwave:  amp [m], ang [deg], prd [s], tide [m], B_tg, gamma_tg
            0.25     190.        8.      -2.       1.3    0.38
wkb_roller:  roller_sinb  roller_fraction
                  0.1         0.5

wave_history_fields: hrm  frq  action  k_xi  k_eta  eps_b  eps_d Erol eps_r
                      20*F
wave_average_fields: hrm  frq  action  k_xi  k_eta  eps_b  eps_d Erol eps_r
                      20*F
wci_history_fields:  SUP UST2D VST2D UST VST WST AKB AKW KVF CALP KAPS
                      20*F
wci_average_fields:  SUP UST2D VST2D UST VST WST AKB AKW KVF CALP KAPS
                      20*F

sediments: input file
           sediment.in
sediment_history_fields: bed_thick bed_poros bed_fra(sand,silt)
                            20*F

bbl_history_fields: Abed Hripple Lripple Zbnot Zbapp Bostrw
                     T      F       F      T     F     T

floats: LDEFFLT, NFLT, NRPFFLT / inpname, hisname
           T      6      0
                                   floats.in
    CROCO_FILES/floats.nc
float_fields:  Grdvar Temp Salt Rho Vel
                T     T    T    T   T

stations: LDEFSTA, NSTA, NRPFSTA / inpname, hisname
             T      400      0
                                    stations.in
    CROCO_FILES/stations.nc
station_fields:  Grdvar Temp Salt Rho Vel
                   T     T    T    T   T

psource:   Nsrc  Isrc  Jsrc  Dsrc  Qbar [m3/s]    Lsrc        Tsrc
            77
121 412 0 1 T T 9.873 37.289
135 409 0 1 T T 10.083 37.245
146 401 0 1 T T 10.219 37.155
141 392 0 1 T T 10.181 37.034
143 387 0 1 T T 10.205 36.983
144 384 0 1 T T 10.249 36.944
150 383 0 1 T T 10.311 36.921
148 370 0 1 T T 10.298 36.765
151 369 0 1 T T 10.326 36.74
153 368 1 1 T T 10.375 36.719
156 368 0 1 T T 10.431 36.72
163 373 0 1 T T 10.561 36.797
191 394 0 1 T T 10.976 37.051
198 374 1 -1 T T 11.086 36.831
195 372 1 -1 T T 11.033 36.797
193 368 1 -1 T T 10.998 36.757
184 352 1 -1 T T 10.856 36.553
181 346 1 -1 T T 10.811 36.47
179 344 1 -1 T T 10.795 36.453
175 343 1 -1 T T 10.726 36.44
161 333 0 1 T T 10.505 36.308
161 333 0 1 T T 10.503 36.306
164 307 0 1 T T 10.539 35.965
165 306 0 1 T T 10.546 35.953
169 299 0 1 T T 10.606 35.873
162 308 0 1 T T 10.533 35.976
188 284 1 1 T T 10.87 35.683
198 269 0 1 T T 11.059 35.49
178 208 0 1 T T 10.753 34.725
137 145 0 1 T T 10.113 33.895
138 144 0 1 T T 10.122 33.883
140 141 0 1 T T 10.154 33.844
151 131 1 1 T T 10.331 33.708
155 129 1 1 T T 10.385 33.68
157 127 1 1 T T 10.416 33.664
122 411 1 1 T T 9.89 37.275
123 411 1 1 T T 9.893 37.264
135 409 1 1 T T 10.095 37.238
186 391 1 1 T T 10.907 37.022
184 352 0 1 T T 10.859 36.568
172 295 0 1 T T 10.649 35.813
175 292 1 1 T T 10.714 35.774
198 269 0 1 T T 11.06 35.495
198 268 0 1 T T 11.059 35.491
201 248 1 1 T T 11.156 35.229
195 240 0 1 T T 11.03 35.122
194 233 0 1 T T 11.013 35.029
179 209 0 1 T T 10.778 34.73
177 205 0 1 T T 10.746 34.68
176 204 0 1 T T 10.739 34.671
171 201 0 1 T T 10.65 34.635
170 200 0 1 T T 10.643 34.63
170 200 0 1 T T 10.641 34.627
168 198 0 1 T T 10.601 34.578
167 194 0 1 T T 10.593 34.54
147 185 1 -1 T T 10.284 34.429
136 148 0 1 T T 10.093 33.928
136 147 0 1 T T 10.096 33.921
176 131 0 1 T T 10.743 33.721
201 113 0 1 T T 11.117 33.491
146 388 0 1 T T 10.264 37.004
197 390 0 1 T T 11.058 37.009
178 344 0 1 T T 10.768 36.45
172 342 0 1 T T 10.682 36.425
183 287 0 1 T T 10.819 35.729
198 266 0 1 T T 11.032 35.161
194 233 0 1 T T 11.054 35.16
196 236 0 1 T T 10.922 34.799
168 198 0 1 T T 10.493 34.516
160 192 0 1 T T 10.581 34.596
208 206 0 1 T T 11.158 34.737
176 133 0 -1 T T 10.729 33.768
182 146 1 1 T T 10.839 33.892
191 131 0 1 T T 10.941 33.698
199 122 0 1 T T 11.077 33.595
201 113 0 1 T T 11.115 33.478
201 99 0 1 T T 11.065 33.315

psource_ncfile:   Nsrc  Isrc  Jsrc  Dsrc qbardir  Lsrc  Tsrc   runoff file name
    CROCO_FILES/croco_runoff.nc
                 77
121 412 0 1 T T 9.873 37.289
135 409 0 1 T T 10.083 37.245
146 401 0 1 T T 10.219 37.155
141 392 0 1 T T 10.181 37.034
143 387 0 1 T T 10.205 36.983
144 384 0 1 T T 10.249 36.944
150 383 0 1 T T 10.311 36.921
148 370 0 1 T T 10.298 36.765
151 369 0 1 T T 10.326 36.74
153 368 1 1 T T 10.375 36.719
156 368 0 1 T T 10.431 36.72
163 373 0 1 T T 10.561 36.797
191 394 0 1 T T 10.976 37.051
198 374 1 -1 T T 11.086 36.831
195 372 1 -1 T T 11.033 36.797
193 368 1 -1 T T 10.998 36.757
184 352 1 -1 T T 10.856 36.553
181 346 1 -1 T T 10.811 36.47
179 344 1 -1 T T 10.795 36.453
175 343 1 -1 T T 10.726 36.44
161 333 0 1 T T 10.505 36.308
161 333 0 1 T T 10.503 36.306
164 307 0 1 T T 10.539 35.965
165 306 0 1 T T 10.546 35.953
169 299 0 1 T T 10.606 35.873
162 308 0 1 T T 10.533 35.976
188 284 1 1 T T 10.87 35.683
198 269 0 1 T T 11.059 35.49
178 208 0 1 T T 10.753 34.725
137 145 0 1 T T 10.113 33.895
138 144 0 1 T T 10.122 33.883
140 141 0 1 T T 10.154 33.844
151 131 1 1 T T 10.331 33.708
155 129 1 1 T T 10.385 33.68
157 127 1 1 T T 10.416 33.664
122 411 1 1 T T 9.89 37.275
123 411 1 1 T T 9.893 37.264
135 409 1 1 T T 10.095 37.238
186 391 1 1 T T 10.907 37.022
184 352 0 1 T T 10.859 36.568
172 295 0 1 T T 10.649 35.813
175 292 1 1 T T 10.714 35.774
198 269 0 1 T T 11.06 35.495
198 268 0 1 T T 11.059 35.491
201 248 1 1 T T 11.156 35.229
195 240 0 1 T T 11.03 35.122
194 233 0 1 T T 11.013 35.029
179 209 0 1 T T 10.778 34.73
177 205 0 1 T T 10.746 34.68
176 204 0 1 T T 10.739 34.671
171 201 0 1 T T 10.65 34.635
170 200 0 1 T T 10.643 34.63
170 200 0 1 T T 10.641 34.627
168 198 0 1 T T 10.601 34.578
167 194 0 1 T T 10.593 34.54
147 185 1 -1 T T 10.284 34.429
136 148 0 1 T T 10.093 33.928
136 147 0 1 T T 10.096 33.921
176 131 0 1 T T 10.743 33.721
201 113 0 1 T T 11.117 33.491
146 388 0 1 T T 10.264 37.004
197 390 0 1 T T 11.058 37.009
178 344 0 1 T T 10.768 36.45
172 342 0 1 T T 10.682 36.425
183 287 0 1 T T 10.819 35.729
198 266 0 1 T T 11.032 35.161
194 233 0 1 T T 11.054 35.16
196 236 0 1 T T 10.922 34.799
168 198 0 1 T T 10.493 34.516
160 192 0 1 T T 10.581 34.596
208 206 0 1 T T 11.158 34.737
176 133 0 -1 T T 10.729 33.768
182 146 1 1 T T 10.839 33.892
191 131 0 1 T T 10.941 33.698
199 122 0 1 T T 11.077 33.595
201 113 0 1 T T 11.115 33.478
201 99 0 1 T T 11.065 33.315

! bmonth=2 → ERA5 empieza desde febrero (datos disponibles desde Feb 2020)
online:    byear  bmonth recordsperday byearend bmonthend / data path
           2020   2      24             2020     6
/data1/matlab/croco-v2.1.0/Tunisia/DATA/ERA5_Tunisia/
