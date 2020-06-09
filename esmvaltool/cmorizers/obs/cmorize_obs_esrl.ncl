; ######################################################################
;  ESMValTool CMORizer for ESRL observational data
; ######################################################################
;
; Tier
;    Tier 2: other freely-available dataset.
;
; Source
;    http://www.esrl.noaa.gov/gmd/dv/data/index.php
;
; Last access
;    20140115
;
; Download and processing instructions
;    Select the following filters:
;        Category: Greenhouse Gases.
;        Parameter name: Carbon Dioxide.
;        Type: Insitu.
;        Frequency: Monthly Averages.
;        Site: BRW, MLO, SMO, SPO.
;    Convert the data to unix format using dos2unix.
;    Get the list of stations at:
;        http://www.esrl.noaa.gov/gmd/obop/
;    This list must be manually formatted in a comma-separated table,
;    given as
;   FILE_STAT below.
;    Check the period covered by the data and give it below as YEAR1 and
;    YEAR2.
;
; Modification history
;    20200508-zechlau_sabrina: adapted to v2.
;    20140122-righi_mattia: written.
;
; ######################################################################
loadscript(getenv("esmvaltool_root") + \
           "/esmvaltool/cmorizers/obs/interface.ncl")

begin

  ; Script name (for logger)
  DIAG_SCRIPT = "cmorize_obs_esrl.ncl"

  ; Source name
  OBSNAME = "ESRL"

  ; Tier
  TIER = 2

  ; Period
  YEAR1 = 1973
  YEAR2 = 2014

  ; Selected variable (standard name)
  VAR = "co2s"

  ; Field
  MIP = "Amon"

  ; Frequency
  FREQ = "mon"

  ; CMOR table
  CMOR_TABLE = getenv("cmor_tables") + "/custom/CMOR_co2s.dat"

  ; Type
  TYPE = "ground"

  ; Stations list
  FILE_STAT = input_dir_path + OBSNAME + "_stations.csv"

  ; Global attributes
  SOURCE = "http://www.esrl.noaa.gov/gmd/dv/data/index.php"
  REF = "Dr. Pieter Tans, NOAA/ESRL " + \
        "(www.esrl.noaa.gov/gmd/ccgg/trends/) and " + \
        "Dr. Ralph Keeling, Scripps Institution of Oceanography " + \
        "(scrippsco2.ucsd.edu/)"
  COMMENT = ""

end

begin

  ; Create time coordinate
  timec = create_timec(YEAR1, YEAR2)
  datec = cd_calendar(timec, 1)

  ; Read station info
  stat = asciiread(FILE_STAT, -1, "string")
  st_code = str_squeeze(str_get_field(stat(:), 1, ","))
  st_name = str_squeeze(str_get_field(stat(:), 2, ","))
  st_lat  = tofloat(str_get_field(stat(:), 3, ","))
  st_lon  = tofloat(str_get_field(stat(:), 4, ","))
  st_alt  = toint(str_get_field(stat(:), 5, ","))
  nstats  = dimsizes(st_code)
  delete(stat)

  ; Loop over stations
  do stID = 0, nstats - 1

    infile = input_dir_path + "co2_" + str_lower(st_code(stID)) + \
             "_surface-insitu_1_ccgg_month.txt"

    if (fileexists(infile)) then

      raw = asciiread(infile, -1, "string")
      head = str_get_field(raw(0), 3, " ")
      data = raw(toint(head):)
      delete([/head, raw/])

      ; Read site name
      tmp = str_get_field(data(:), 1, " ")
      if (.not.all(tmp(0).eq.tmp)) then
          log_info("Inconsistent site name in " + infiles(ii))
      else
        site = tmp(0)
      end if
      delete(tmp)

      ; Read time and extract full years only
      year = str_squeeze(str_get_field(data(:), 2, " "))
      month = str_squeeze(str_get_field(data(:), 3, " "))
      date = toint(year + month)
      var = tofloat(str_get_field(data(:), 4, " "))
      delete(data)

      ; Check time range
      if (min(toint(year)).lt.YEAR1 .or. max(toint(year)).gt.YEAR2) then
        error_msg("f", DIAG_SCRIPT, "", "given time range (" + \
                  YEAR1 + "-" + YEAR2 + ")" + \
                  " not consistent with data (" + \
                  min(toint(year)) + "-" + max(toint(year)) + ")")
      end if
      delete(year)
      delete(month)

      ; Create output variable
      output = new((/dimsizes(timec), 1, 1/), float)
      output!0 = "time"
      output&time = timec
      output!1 = "lon"
      output&lon = st_lon(stID)
      output!2 = "lat"
      output&lat = st_lat(stID)
      output@_FillValue = FILL

      do ii = 0, dimsizes(var) - 1
        output(ind(datec.eq.date(ii)),0 ,0) = (/var(ii)/)
      end do
      delete(var)
      delete(date)
      output = where(output.lt.0., output@_FillValue, output)

      ; Format coordinates
      format_coords(output, YEAR1 + "0101", YEAR2 + "1231", FREQ)
      
      ; Set variable attributes (CMOR)
      tmp = format_variable(output, VAR, CMOR_TABLE)
      delete(output)
      output = tmp
      delete(tmp)

      ; Calculate coordinate bounds
      ;bounds = guess_coord_bounds(output, FREQ)
      bounds = NewList("fifo")
      time_bnds = guess_bounds_time(output&time, FREQ)
      ListPush(bounds, time_bnds)

      lat_bnds = new((/1, 2/), double)
      lat_bnds!0 = "lat"
      lat_bnds&lat = output&lat
      lat_bnds!1 = "bnds"
      lat_bnds(0, 0) = -90.
      lat_bnds(0, 1) = 90.
      ListPush(bounds, lat_bnds)

      lon_bnds = new((/1, 2/), double)
      lon_bnds!0 = "lon"
      lon_bnds&lon = output&lon
      lon_bnds!1 = "bnds"
      lon_bnds(0, 0) = 0.
      lon_bnds(0, 1) = 360.
      ListPush(bounds, lon_bnds)

      ; Set global attributes
      gAtt = set_global_atts(OBSNAME, TIER, SOURCE, REF, COMMENT)

      ; Outfile
      VERSION = st_code(stID)
      DATESTR = YEAR1 + "01-" + YEAR2 + "12"

      fout = output_dir_path + \
             str_join((/"OBS", OBSNAME, TYPE, VERSION, \
                       MIP, VAR, DATESTR/), "_") + ".nc"

      ; Write variable
      write_nc(fout, VAR, output, bounds, gAtt)
      delete(gAtt)
      delete(output)

    end if

  end do

end