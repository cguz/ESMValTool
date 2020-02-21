import os
import logging

import iris
import iris.cube
import iris.analysis
from iris.analysis import stats
import iris.util

from esmvalcore.preprocessor import regrid, mask_landsea, extract_season

import esmvaltool.diag_scripts.shared
import esmvaltool.diag_scripts.shared.names as n
from esmvaltool.diag_scripts.shared import group_metadata
from esmvaltool.diag_scripts.shared._base import ProvenanceLogger

logger = logging.getLogger(os.path.basename(__file__))


class LandAtmosInteractions(object):
    def __init__(self, config):
        self.cfg = config
        self.filenames = esmvaltool.diag_scripts.shared.Datasets(self.cfg)
        self.output_name = None
        self.target_grid = self.cfg.get('target_grid')
        self.sftlf = None

    def compute(self):
        data = group_metadata(self.cfg['input_data'].values(), 'alias')
        for alias in data:
            var = group_metadata(data[alias], 'short_name')
            hfls = iris.load_cube(var['hfls'][0]['filename'])
            hfss = iris.load_cube(var['hfss'][0]['filename'])
            rsds = iris.load_cube(var['rsds'][0]['filename'])
            rlds = iris.load_cube(var['rlds'][0]['filename'])
            clt = iris.load_cube(var['clt'][0]['filename'])
            tas = iris.load_cube(var['tas'][0]['filename'])
            mrso = iris.load_cube(var['mrso'][0]['filename'])
            self.sftlf = [var['sftlf'][0]['filename']]

            clim_ef, stdv_ef = self.evaporative_fraction_stats(hfls, hfss)

            if 'detrend' in self.cfg[n.SCRIPT]:
                self.output_name = 'detrended_evaporative_fraction_statistics'
            else:
                self.output_name = 'evaporative_fraction_statistics'
            self.save([clim_ef, stdv_ef], alias, data)

            metrics = self.compute_correlation_metrics(
                hfls, rsds, rlds, clt, tas, mrso)
            if 'detrend' in self.cfg[n.SCRIPT]:
                self.output_name = 'detrended_correlation_metrics'
            else:
                self.output_name = 'correlation_metrics'
            self.save(metrics, alias, data)

    def save(self, cubelist, alias, data):
        if self.output_name:
            project = data[alias][0]['project']
            dataset = data[alias][0]['dataset']
            experiment = data[alias][0]['exp']
            start_year = data[alias][0]['start_year']
            end_year = data[alias][0]['end_year']
            filename = '{project}_' \
                       '{dataset}_' \
                       '{experiment}_' \
                       '{output}_' \
                       '{start_year}_' \
                       '{end_year}.nc'.format(project=project,
                                              dataset=dataset,
                                              experiment=experiment,
                                              output=self.output_name,
                                              start_year=start_year,
                                              end_year=end_year)

            iris.save(cubelist, os.path.join(self.cfg[n.WORK_DIR], filename))
            caption = ("{script} between {start} and {end}"
                       "according to {dataset}").format(
                           script=self.output_name.split('_'),
                           start=start_year,
                           end=end_year,
                           dataset=dataset)
            ancestors = []
            for i in range(len(data[alias])):
                ancestors.append(data[alias][i]['filename'])
            record = {
                'caption': caption,
                'domains': ['global'],
                'autors': ['boe_julien'],
                'references': ['acknow_project'],
                'ancestors': ancestors}
            with ProvenanceLogger(self.cfg) as provenance_logger:
                provenance_logger.log(
                    os.path.join(self.cfg[n.WORK_DIR], filename), record)

#            for cube in cubelist:
#                plotname = '{project}_' \
#                           '{dataset}_' \
#                           '{experiment}_' \
#                           '{longname}_' \
#                           '{start_year}_' \
#                           '{end_year}'.format(project=project,
#                                               dataset=dataset,
#                                               experiment=experiment,
#                                               longname=cube.long_name,
#                                               start_year=start_year,
#                                               end_year=end_year)

#                pm = plotmap.PlotMap()
#                pm.plot_cube(cube,
#                             outdir=self.cfg[n.PLOT_DIR],
#                             file_format=self.cfg[n.OUTPUT_FILE_TYPE],
#                             img_template=plotname)
    def compute_correlation_metrics(self, hfls, rsds, rlds, clt, tas, mrso):
        corr_hfls_rad = self.heat_radiation_stats(hfls, rsds, rlds)
        corr_clt_tas = self.cloud_temperature_stats(clt, tas)
        corr_hfls_mrso, corr_mrso_mam_jja = self.heat_soil_stats(hfls, mrso)
        return [corr_hfls_rad, corr_clt_tas,
                corr_hfls_mrso, corr_mrso_mam_jja]

    def evaporative_fraction_stats(self, hfls, hfss):
        hftotal = hfls + hfss
        evaporative_frac = hfls / hftotal
        clim = evaporative_frac.collapsed('time', iris.analysis.MEAN)
        clim = self.mask_and_regrid(clim)
        clim.long_name = 'climatological_evaporative_fraction'
        stdv = evaporative_frac.collapsed('time', iris.analysis.STD_DEV)
        stdv = self.mask_and_regrid(stdv)
        stdv.long_name = ('interannual_standard_deviation_'
                          'of_evaporative_fraction')
        return clim, stdv

    def heat_radiation_stats(self, hfls, rsds, rlds):
        rtotal = rsds + rlds
        correlation = stats.pearsonr(hfls, rtotal, 'time')
        correlation = self.mask_and_regrid(correlation)
        correlation.long_name = ('interannual_correlation_between'
                                 '_latent_heat_flux_and_total_radiation'
                                 '_at_surface')
        return correlation

    def cloud_temperature_stats(self, clt, tas):
        correlation = stats.pearsonr(clt, tas, 'time')
        correlation = self.mask_and_regrid(correlation)
        correlation.long_name = ('interannual_correlation_between'
                                 '_temperature_and_cloud_cover')
        return correlation

    def heat_soil_stats(self, hfls, mrso):
        mrso_mam = extract_season(mrso, 'MAM')
        mrso_jja = extract_season(mrso, 'JJA')
        # Avoid Iris complaints about metadata
        dummy = mrso_jja.copy(mrso_mam.lazy_data())
        try:
            correlation = stats.pearsonr(hfls, mrso_jja, 'time')
        except ValueError:
            dim_coord = hfls.coord_dims('latitude')
            mrso_jja.remove_coord('latitude')
            mrso_jja.add_dim_coord(hfls.coord('latitude'), dim_coord[0])
            correlation = stats.pearsonr(hfls, mrso_jja, 'time')

        correlation = self.mask_and_regrid(correlation)
        correlation.long_name = ('interannual_correlation_between'
                                 '_latent_heat_flux_and_soil_moisture')
        mrso_correlation = stats.pearsonr(dummy, mrso_jja, 'time')
        mrso_correlation = self.mask_and_regrid(mrso_correlation)
        mrso_correlation.long_name = ('interannual_correlation'
                                      '_between_soil_moisture_'
                                      'in_spring_and_soil_moisture'
                                      '_in_summer')
        return correlation, mrso_correlation

    def mask_and_regrid(self, var):
        var = mask_landsea(var, self.sftlf, 'sea')
        var = regrid(var,
                     self.target_grid,
                     scheme='area_weighted')
        return var


def main():
    with esmvaltool.diag_scripts.shared.run_diagnostic() as config:
        LandAtmosInteractions(config).compute()


if __name__ == '__main__':
    main()