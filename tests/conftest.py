import pytest

from itibar import paths


def _have_parquet() -> bool:
    return (paths.PARQUET_DIR / "sanad_rawis.parquet").exists()


@pytest.fixture(scope="session")
def con():
    if not _have_parquet():
        pytest.skip(f"no Parquet data at {paths.PARQUET_DIR} (run `make data` or `make fixture-test`)")
    from itibar import data
    return data.views()


@pytest.fixture(scope="session")
def corpus(con):
    from itibar import load
    return load.corpus(con)


@pytest.fixture(scope="session")
def records():
    if not paths.records_path().exists():
        pytest.skip(f"no {paths.records_path()} (run `make bundles`)")
    import pandas as pd
    return pd.read_parquet(paths.records_path())


@pytest.fixture(scope="session")
def chains_table():
    if not paths.chains_path().exists():
        pytest.skip(f"no {paths.chains_path()} (run `make bundles`)")
    import pandas as pd
    return pd.read_parquet(paths.chains_path())
