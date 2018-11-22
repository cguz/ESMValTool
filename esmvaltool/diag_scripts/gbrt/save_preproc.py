"""Save preproc files in work to use them for GBRT models."""

import logging
import os

import iris

from esmvaltool.diag_scripts.shared import run_diagnostic, gbrt

logger = logging.getLogger(os.path.basename(__file__))


def main(cfg):
    """Run the diagnostic."""
    logger.info("Running save_preproc.py diagnostic.")

    # Save preproc files in work directory
    if cfg['write_netcdf']:
        for (path, data) in cfg['input_data'].items():
            cube = iris.load_cube(path)

            # Average if desired
            if cfg.get('global_average'):
                weights = iris.analysis.cartography.area_weights(cube)
                cube = cube.collapsed(['latitude', 'longitude'],
                                      iris.analysis.MEAN,
                                      weights=weights)
            if cfg.get('temporal_average'):
                cube = cube.collapsed('time', iris.analysis.MEAN)

            # Save new cube
            new_path = os.path.join(cfg['work_dir'], os.path.basename(path))
            data['filename'] = new_path
            gbrt.write_cube(cube, data, new_path, cfg)


# Run main function when this script is called
if __name__ == '__main__':
    with run_diagnostic() as config:
        main(config)
