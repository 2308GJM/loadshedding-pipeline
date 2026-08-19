"""
Load-shedding & weather pipeline DAG.

Stages:
  ingest_loadshedding  ─┐
                         ├─▶ validate_transform (per source) ─▶ join_enrich ─▶ load_to_store
  ingest_weather       ─┘

Each stage is implemented as a separate module under src/ so it can be
unit tested independently of Airflow. This file only wires them together.
"""
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "gj",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


def _ingest_loadshedding(**context):
    from src.ingestion.ingest_loadshedding import run
    run(execution_date=context["ds"])


def _ingest_weather(**context):
    from src.ingestion.ingest_weather import run
    run(execution_date=context["ds"])


def _validate_transform_loadshedding(**context):
    from src.transform.validate_transform_loadshedding import run
    run(execution_date=context["ds"])


def _validate_transform_weather(**context):
    from src.transform.validate_transform_weather import run
    run(execution_date=context["ds"])


def _join_enrich(**context):
    from src.transform.join_enrich import run
    run(execution_date=context["ds"])


def _load_to_store(**context):
    from src.load.load_to_store import run
    run(execution_date=context["ds"])


with DAG(
    dag_id="loadshedding_weather_pipeline",
    description="Ingest, validate, join and load Eskom load-shedding + weather data",
    default_args=default_args,
    schedule_interval="@daily",
    start_date=datetime(2026, 8, 17),
    catchup=False,
    tags=["data-engineering", "elective"],
) as dag:

    ingest_loadshedding = PythonOperator(
        task_id="ingest_loadshedding",
        python_callable=_ingest_loadshedding,
    )

    ingest_weather = PythonOperator(
        task_id="ingest_weather",
        python_callable=_ingest_weather,
    )

    validate_transform_loadshedding = PythonOperator(
        task_id="validate_transform_loadshedding",
        python_callable=_validate_transform_loadshedding,
    )

    validate_transform_weather = PythonOperator(
        task_id="validate_transform_weather",
        python_callable=_validate_transform_weather,
    )

    join_enrich = PythonOperator(
        task_id="join_enrich",
        python_callable=_join_enrich,
    )

    load_to_store = PythonOperator(
        task_id="load_to_store",
        python_callable=_load_to_store,
    )

    ingest_loadshedding >> validate_transform_loadshedding
    ingest_weather >> validate_transform_weather

    [validate_transform_loadshedding, validate_transform_weather] >> join_enrich >> load_to_store
