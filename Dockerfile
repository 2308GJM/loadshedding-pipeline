# Custom Airflow image with PySpark baked in at build time.
# _PIP_ADDITIONAL_REQUIREMENTS in docker-compose.yml, which installs
# PySpark fresh in every Airflow container on every cold start

FROM apache/airflow:2.9.3-python3.11

USER airflow
RUN pip install --no-cache-dir pyspark==3.5.1 requests python-dotenv