"""Script to download cds-satellite-albedo from the Climate Data Store(CDS)"""

from dateutil import relativedelta

from esmvaltool.cmorizers.obs.downloaders.ftp import CCIDownloader


def download_dataset(config, dataset, start_date, end_date):
    """Download dataset cds-satellite-albedo."""
    loop_date = start_date

    downloader = CCIDownloader(
        config=config,
        dataset=dataset
    )
    downloader.connect()

    downloader.set_cwd('burned_area/MERIS/grid/v4.1/')
    while loop_date <= end_date:
        year = loop_date.year
        downloader.download_year(f'{year}')